"""
Обновляет data/news.json — новости ТОЛЬКО с golos.tj, logistan.info, inform.kz.
Собирает ПО ОЧЕРЕДИ с каждого сайта (по кругу).
Если на сайте нет новостей — пропускает и берет со следующего.
Добивает до 6 демо-новостями, если не хватает.
"""
import html
import json
import os
import re
import random
import time
from datetime import datetime, timezone
import requests
import feedparser

UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
MAX_ITEMS = 6

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ============================================================
# 1. ЖЕСТКИЙ ФИЛЬТР: ТОЛЬКО ЛОГИСТИКА
# ============================================================

STRICT_LOGISTICS = [
    "поезд", "вагон", "локомотив", "жд", "ж/д", "железнодорож",
    "магистраль", "путь", "рельс", "состав", "электровоз",
    "порт", "судно", "контейнеровоз", "паром", "причал", "гавань",
    "морской", "речной", "флот", "танкер",
    "терминал", "склад", "хаб", "распределительный центр",
    "логистический центр", "складской", "хранение",
    "контейнер", "груз", "контейнерный", "teu", "обработка грузов",
    "грузоперевозк", "грузовой",
    "коридор", "транзит", "маршрут", "транскаспий",
    "международный транспорт", "транспортный",
    "таможня", "оформление", "пошлины", "транзитный",
    "перевозк", "транспортировк", "доставк", "логистик",
]

def is_logistics(text):
    if not text:
        return False
    text_lower = text.lower()
    for word in text_lower.split():
        for root in STRICT_LOGISTICS:
            if root in word:
                return True
    return False

def has_country(text):
    if not text:
        return False
    text_lower = text.lower()
    countries = [
        "казахстан", "узбекистан", "кыргызстан", "таджикистан", "туркменистан",
        "астана", "алматы", "ташкент", "бишкек", "душанбе", "ашхабад",
    ]
    return any(c in text_lower for c in countries)

def is_relevant(title, summary):
    if not title:
        return False
    full_text = (title + " " + summary).lower()
    if not is_logistics(full_text):
        return False
    if not has_country(full_text):
        return False
    return True

# ============================================================
# 2. ГЕНЕРАЦИЯ КОРОТКОЙ ВЫЖИМКИ
# ============================================================

def generate_unique_summary(title, original_summary):
    if not original_summary:
        original_summary = title
    
    text = strip_html(original_summary)
    text = re.sub(r'передает\s+агентство\s+[А-Яа-я]+\s*', '', text)
    text = re.sub(r'со\s+ссылкой\s+на\s+[^,.]+,?\s*', '', text)
    text = re.sub(r'как\s+сообщил[аи]?\s+[^,.]+,?\s*', '', text)
    text = re.sub(r'передает\s+корреспондент\s+[А-Яа-я]+\s*', '', text)
    text = re.sub(r'по\s+информации\s+[^,.]+,?\s*', '', text)
    text = re.sub(r'пишет\s+[А-Яа-яА-Я\s\|]+\s*', '', text)
    text = re.sub(r'Сообщение\s+[^.]+\s+появились\s+сначала\s+на\s+[А-Яа-я\s-]+\.', '', text)
    
    sentences = re.split(r'[.!?]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    
    fact_sentences = []
    for s in sentences[:4]:
        if re.search(r'\d+', s) or any(word in s.lower() for word in ['логистик', 'транспорт', 'груз', 'контейнер', 'порт', 'склад', 'терминал']):
            fact_sentences.append(s)
    
    if len(fact_sentences) < 1:
        fact_sentences = sentences[:2]
    
    cleaned = []
    for s in fact_sentences:
        s = re.sub(r'^(основными драйверами|по данным|как отмечается|в частности|также)\s+', '', s, flags=re.IGNORECASE)
        s = re.sub(r'•\s+[^\n]+', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        if len(s) > 10:
            cleaned.append(s)
    
    if len(cleaned) >= 2:
        result = '. '.join(cleaned[:3])
    elif len(cleaned) == 1:
        clean_title = re.sub(r'^(Казахстан|Узбекистан|Кыргызстан|Таджикистан|Туркменистан)\s+', '', title)
        result = f"{clean_title}. {cleaned[0]}"
    else:
        clean_title = re.sub(r'^(Казахстан|Узбекистан|Кыргызстан|Таджикистан|Туркменистан)\s+', '', title)
        result = clean_title + ". Подробнее в источнике."
    
    if result and not result.endswith('.'):
        result += '.'
    if len(result) > 250:
        result = result[:247] + '...'
    
    return result

# ============================================================
# 3. КАРТИНКИ (УНИКАЛЬНЫЕ, БЕЗ ПОВТОРОВ)
# ============================================================

_used_photos = set()

def pick_photo_from_unsplash(title):
    if not UNSPLASH_KEY:
        return None
    
    clean_title = re.sub(r'[^\w\s]', ' ', title)
    words = [w for w in clean_title.split() if len(w) > 3][:4]
    
    topic_map = {
        'поезд': 'train', 'вагон': 'train', 'железнодорож': 'railway', 'жд': 'railway',
        'порт': 'port', 'судно': 'ship', 'контейнер': 'container', 'терминал': 'terminal',
        'склад': 'warehouse', 'хаб': 'logistics hub', 'груз': 'cargo', 'фрахт': 'freight',
        'транзит': 'transit', 'коридор': 'corridor', 'инфраструктур': 'infrastructure',
        'строительств': 'construction', 'дорог': 'road', 'аэропорт': 'airport',
    }
    
    search_query = "logistics transport"
    for word in words:
        word_lower = word.lower()
        for key, topic in topic_map.items():
            if key in word_lower:
                search_query = topic
                break
        if search_query != "logistics transport":
            break
    
    if search_query == "logistics transport" and len(words) >= 2:
        search_query = ' '.join(words[:2])
    
    photo_url = None
    for attempt in range(3):
        try:
            r = requests.get(
                "https://api.unsplash.com/search/photos",
                params={"query": search_query, "per_page": 5, "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
                timeout=10,
            )
            r.raise_for_status()
            results = r.json().get("results") or []
            
            for photo in results:
                url = photo["urls"]["regular"]
                if url not in _used_photos:
                    _used_photos.add(url)
                    photo_url = url
                    break
            
            if photo_url:
                break
                
        except Exception:
            pass
        
        search_query = search_query + " " + random.choice(["transport", "logistics", "cargo"])
    
    if not photo_url:
        fallback_urls = [
            "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800",
            "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800",
            "https://images.unsplash.com/photo-1494412574643-ff11b0a5c1c3?w=800",
            "https://images.unsplash.com/photo-1519003722824-356d8a3ff1a1?w=800",
            "https://images.unsplash.com/photo-1582721478779-0ae163c05a60?w=800",
            "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=800",
        ]
        for url in fallback_urls:
            if url not in _used_photos:
                _used_photos.add(url)
                photo_url = url
                break
    
    return {"url": photo_url} if photo_url else None

def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def detect_topic(title, summary):
    text = (title + " " + summary).lower()
    topics = {
        "Транспорт": ["поезд", "вагон", "локомотив", "жд", "железнодорож", "магистраль", "рельс", "состав"],
        "Порты": ["порт", "судно", "контейнеровоз", "паром", "причал", "гавань", "морской", "флот"],
        "Терминалы": ["терминал", "склад", "хаб", "распределительный центр", "логистический центр"],
        "Грузы": ["контейнер", "груз", "контейнерный", "teu"],
        "Коридоры": ["коридор", "транзит", "маршрут", "транскаспий"],
        "Таможня": ["таможня", "оформление", "пошлины"],
        "Перевозки": ["перевозк", "транспортировк", "доставк", "логистик"],
    }
    for topic, keywords in topics.items():
        if any(kw in text for kw in keywords):
            return topic
    return "Логистика"

# ============================================================
# 4. ПАРСИНГ ТРЁХ САЙТОВ (ВОЗВРАЩАЮТ СПИСКИ НОВОСТЕЙ)
# ============================================================

def collect_golos(limit=6):
    """Собирает логистические новости с golos.tj (не больше limit)"""
    out = []
    try:
        parsed = feedparser.parse("https://golos.tj/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ golos.tj ошибка: {e}")
        return out

    for entry in parsed.entries[:20]:
        if len(out) >= limit:
            break
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("description") or entry.get("summary") or "")[:500]
        
        if not is_relevant(title, summary):
            continue
            
        photo = pick_photo_from_unsplash(title)
        out.append({
            "source": "golos.tj",
            "topic": detect_topic(title, summary),
            "title": title,
            "summary": generate_unique_summary(title, summary),
            "publishedAt": entry.get("published", ""),
            "photo": photo,
        })
        print(f"    ✅ golos.tj: {title[:40]}...")
    
    return out

def collect_logistan(limit=6):
    """Собирает логистические новости с logistan.info (не больше limit)"""
    out = []
    try:
        parsed = feedparser.parse("https://logistan.info/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ logistan.info ошибка: {e}")
        return out

    for entry in parsed.entries[:20]:
        if len(out) >= limit:
            break
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("description") or entry.get("summary") or "")[:500]
        
        if not is_relevant(title, summary):
            continue
            
        photo = pick_photo_from_unsplash(title)
        out.append({
            "source": "logistan.info",
            "topic": detect_topic(title, summary),
            "title": title,
            "summary": generate_unique_summary(title, summary),
            "publishedAt": entry.get("published", ""),
            "photo": photo,
        })
        print(f"    ✅ logistan.info: {title[:40]}...")
    
    return out

def collect_inform(limit=6):
    """Собирает логистические новости с inform.kz (не больше limit)"""
    out = []
    url = "https://www.inform.kz/tag/logistika_t11100"
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"  ❌ inform.kz ошибка: {e}")
        return out

    links = set()
    for link in re.findall(r'href=["\']([^"\']*/ru/[a-z0-9\-]+-[a-f0-9]{8})["\']', html_content, re.IGNORECASE):
        if link.startswith('http'):
            links.add(link)
        else:
            links.add("https://www.inform.kz" + link if link.startswith('/') else "https://www.inform.kz/" + link)

    for article_url in list(links)[:20]:
        if len(out) >= limit:
            break
        try:
            ar = requests.get(article_url, timeout=20, headers=HEADERS)
            ar.raise_for_status()
            article_html = ar.text
        except Exception:
            continue

        def meta(prop):
            for pattern in (
                r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']*)["\']',
                r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\']',
            ):
                m = re.search(pattern, article_html, re.IGNORECASE)
                if m:
                    return html.unescape(m.group(1)).strip()
            return ""

        title = meta("og:title")
        if not title:
            continue
        summary = meta("og:description")[:500]
        published = meta("article:published_time")

        if not is_relevant(title, summary):
            continue

        photo = pick_photo_from_unsplash(title)
        out.append({
            "source": "inform.kz",
            "topic": detect_topic(title, summary),
            "title": title,
            "summary": generate_unique_summary(title, summary),
            "publishedAt": published,
            "photo": photo,
        })
        print(f"    ✅ inform.kz: {title[:40]}...")
    
    return out

# ============================================================
# 5. СБОР ПО ОЧЕРЕДИ (ПО КРУГУ)
# ============================================================
def collect():
    print("\n🔍 Сбор новостей (по очереди с каждого сайта)...")
    
    # Собираем новости с каждого сайта (до 6 штук)
    golos_news = collect_golos(6)
    logistan_news = collect_logistan(6)
    inform_news = collect_inform(6)
    
    print(f"\n  golos.tj: {len(golos_news)}")
    print(f"  logistan.info: {len(logistan_news)}")
    print(f"  inform.kz: {len(inform_news)}")
    
    # Убираем дубликаты по заголовку (внутри каждого списка)
    def unique_list(items):
        seen = set()
        result = []
        for item in items:
            key = item["title"][:50].lower()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result
    
    golos_news = unique_list(golos_news)
    logistan_news = unique_list(logistan_news)
    inform_news = unique_list(inform_news)
    
    # Перемешиваем каждый список, чтобы не брать одни и те же новости
    random.shuffle(golos_news)
    random.shuffle(logistan_news)
    random.shuffle(inform_news)
    
    # Собираем по очереди (по кругу)
    result = []
    sources = [
        ("golos.tj", golos_news),
        ("logistan.info", logistan_news),
        ("inform.kz", inform_news),
    ]
    
    # Идем по кругу, пока не наберем 6 или не закончатся новости
    max_rounds = 6  # максимум кругов
    for round_num in range(max_rounds):
        for source_name, source_news in sources:
            if len(result) >= MAX_ITEMS:
                break
            if source_news:
                # Берем первую новость из источника
                item = source_news.pop(0)
                result.append(item)
                print(f"  📌 [{source_name}] {item['title'][:50]}...")
        
        if len(result) >= MAX_ITEMS:
            break
    
    # Если всё ещё меньше 6 — добиваем демо
    if len(result) < MAX_ITEMS:
        print(f"\n⚠️ Не хватает новостей ({len(result)}/{MAX_ITEMS}). Добавляем демо...")
        demo_items = [
            {
                "source": "demo",
                "topic": "Логистика",
                "title": "Развитие транспортных коридоров в Центральной Азии",
                "summary": "Страны региона обсуждают совместные проекты по модернизации логистики.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800"},
            },
            {
                "source": "demo",
                "topic": "Инфраструктура",
                "title": "Новый логистический хаб открылся в регионе",
                "summary": "Объект будет способствовать развитию грузоперевозок.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1494412574643-ff11b0a5c1c3?w=800"},
            },
            {
                "source": "demo",
                "topic": "Железная дорога",
                "title": "Казахстан обновляет парк пассажирских поездов",
                "summary": "За последние годы приобретено более 400 новых вагонов.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800"},
            },
            {
                "source": "demo",
                "topic": "Экономика",
                "title": "Экономический рост в Центральной Азии",
                "summary": "Регион показывает устойчивое развитие.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1519003722824-356d8a3ff1a1?w=800"},
            },
            {
                "source": "demo",
                "topic": "Порты",
                "title": "Модернизация портовой инфраструктуры",
                "summary": "В регионе планируется обновление портовых мощностей.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1582721478779-0ae163c05a60?w=800"},
            },
            {
                "source": "demo",
                "topic": "Логистика",
                "title": "Новые логистические маршруты в регионе",
                "summary": "Развитие транспортных коридоров продолжается.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=800"},
            },
        ]
        
        # Добавляем демо-новости, пока не наберем 6
        for demo in demo_items:
            if len(result) >= MAX_ITEMS:
                break
            result.append(demo)
            print(f"  📌 [demo] {demo['title'][:50]}...")
    
    return result[:MAX_ITEMS]

# ============================================================
# 6. MAIN
# ============================================================
def main():
    print("🚀 Сбор новостей (по очереди с трёх сайтов)...")
    items = collect()

    data = {
        "isDemo": len(items) == 0,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Записано: {OUT_PATH} -> {len(items)} новостей")
    for i, item in enumerate(items[:6]):
        has_photo = "✅" if item.get("photo") else "❌"
        source = item.get("source", "?")
        print(f"  {i+1}. {has_photo} [{source}] {item['title'][:50]}...")
        if item.get('summary'):
            print(f"      📝 {item['summary'][:80]}...")

if __name__ == "__main__":
    main()
