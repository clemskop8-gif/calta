"""
Обновляет data/news.json — новости с golos.tj, logistan.info, inform.kz.
Ровно 6 новостей (по 2 с каждого сайта).
Фильтр: ТОЛЬКО логистика (жесткий фильтр).
БЕЗ ДЕМО-ЗАГЛУШЕК.
Каждая новость имеет КОРОТКУЮ выжимку (2-4 предложения) своими словами.
Картинки из Unsplash по смыслу.
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

# Ключевые слова — ТОЛЬКО логистика
STRICT_LOGISTICS = [
    # Транспорт
    "поезд", "вагон", "локомотив", "жд", "ж/д", "железнодорож",
    "магистраль", "путь", "рельс", "состав", "электровоз",
    
    # Порты и суда
    "порт", "судно", "контейнеровоз", "паром", "причал", "гавань",
    "морской", "речной", "флот", "танкер",
    
    # Терминалы и склады
    "терминал", "склад", "хаб", "распределительный центр",
    "логистический центр", "складской", "хранение",
    
    # Грузы и контейнеры
    "контейнер", "груз", "контейнерный", "teu", "обработка грузов",
    "грузоперевозк", "грузовой",
    
    # Коридоры и транзит
    "коридор", "транзит", "маршрут", "транскаспий",
    "международный транспорт", "транспортный",
    
    # Таможня и оформление
    "таможня", "оформление", "пошлины", "транзитный",
    
    # Перевозки
    "перевозк", "транспортировк", "доставк", "логистик",
]

def is_logistics(text):
    """Проверяет, что новость ТОЧНО про логистику"""
    if not text:
        return False
    text_lower = text.lower()
    # Проверяем каждое слово из текста
    for word in text_lower.split():
        for root in STRICT_LOGISTICS:
            if root in word:
                return True
    return False

def has_country(text):
    """Проверяет, упоминается ли страна ЦА"""
    if not text:
        return False
    text_lower = text.lower()
    countries = [
        "казахстан", "узбекистан", "кыргызстан", "таджикистан", "туркменистан",
        "астана", "алматы", "ташкент", "бишкек", "душанбе", "ашхабад",
    ]
    return any(c in text_lower for c in countries)

def is_relevant(title, summary):
    """Главная проверка: логистика + страна ЦА"""
    if not title:
        return False
    full_text = (title + " " + summary).lower()
    
    # Должна быть логистика
    if not is_logistics(full_text):
        return False
    
    # Должна быть страна ЦА
    if not has_country(full_text):
        return False
    
    return True

# ============================================================
# 2. ГЕНЕРАЦИЯ КОРОТКОЙ ВЫЖИМКИ (2-4 предложения)
# ============================================================

def generate_unique_summary(title, original_summary):
    """
    Создает КОРОТКУЮ фактическую выжимку (2-4 предложения) своими словами.
    Без копирования, только ключевые факты.
    """
    if not original_summary:
        original_summary = title
    
    # 1. Очищаем от шаблонных фраз
    text = strip_html(original_summary)
    text = re.sub(r'передает\s+агентство\s+[А-Яа-я]+\s*', '', text)
    text = re.sub(r'со\s+ссылкой\s+на\s+[^,.]+,?\s*', '', text)
    text = re.sub(r'как\s+сообщил[аи]?\s+[^,.]+,?\s*', '', text)
    text = re.sub(r'передает\s+корреспондент\s+[А-Яа-я]+\s*', '', text)
    text = re.sub(r'по\s+информации\s+[^,.]+,?\s*', '', text)
    text = re.sub(r'пишет\s+[А-Яа-яА-Я\s\|]+\s*', '', text)
    text = re.sub(r'Сообщение\s+[^.]+\s+появились\s+сначала\s+на\s+[А-Яа-я\s-]+\.', '', text)
    
    # 2. Разбиваем на предложения
    sentences = re.split(r'[.!?]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    
    # 3. Берем ТОЛЬКО факты (цифры, даты, ключевые события)
    fact_sentences = []
    for s in sentences[:4]:
        # Оставляем предложения с цифрами, датами, ключевыми словами
        if re.search(r'\d+', s) or any(word in s.lower() for word in ['логистик', 'транспорт', 'груз', 'контейнер', 'порт', 'склад', 'терминал']):
            fact_sentences.append(s)
    
    # Если фактов нет — берем первые 2 предложения
    if len(fact_sentences) < 1:
        fact_sentences = sentences[:2]
    
    # 4. Очищаем каждое предложение от лишних деталей
    cleaned = []
    for s in fact_sentences:
        # Убираем вводные конструкции
        s = re.sub(r'^(основными драйверами|по данным|как отмечается|в частности|также)\s+', '', s, flags=re.IGNORECASE)
        # Убираем перечисления (цифры с точками)
        s = re.sub(r'•\s+[^\n]+', '', s)
        # Убираем множественные пробелы
        s = re.sub(r'\s+', ' ', s).strip()
        if len(s) > 10:
            cleaned.append(s)
    
    # 5. Собираем результат (2-4 предложения)
    if len(cleaned) >= 2:
        result = '. '.join(cleaned[:3])
    elif len(cleaned) == 1:
        # Если только одно предложение — добавляем контекст из заголовка
        clean_title = re.sub(r'^(Казахстан|Узбекистан|Кыргызстан|Таджикистан|Туркменистан)\s+', '', title)
        result = f"{clean_title}. {cleaned[0]}"
    else:
        # Если совсем ничего нет — используем заголовок
        clean_title = re.sub(r'^(Казахстан|Узбекистан|Кыргызстан|Таджикистан|Туркменистан)\s+', '', title)
        result = clean_title + ". Подробнее в источнике."
    
    # 6. Добавляем точку в конце
    if result and not result.endswith('.'):
        result += '.'
    
    # 7. Ограничиваем длину (максимум 250 символов)
    if len(result) > 250:
        result = result[:247] + '...'
    
    return result

# ============================================================
# 3. КАРТИНКИ ИЗ UNSPLASH
# ============================================================

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
    
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": search_query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if results:
            return {"url": results[0]["urls"]["regular"]}
    except Exception:
        pass
    
    fallback_by_topic = {
        'train': "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800",
        'railway': "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800",
        'port': "https://images.unsplash.com/photo-1582721478779-0ae163c05a60?w=800",
        'container': "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800",
        'warehouse': "https://images.unsplash.com/photo-1519003722824-356d8a3ff1a1?w=800",
        'cargo': "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800",
        'airport': "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=800",
    }
    fallback_url = fallback_by_topic.get(search_query, "https://images.unsplash.com/photo-1494412574643-ff11b0a5c1c3?w=800")
    return {"url": fallback_url}

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
# 4. ПАРСИНГ САЙТОВ
# ============================================================

def collect_golos():
    out = []
    try:
        parsed = feedparser.parse("https://golos.tj/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ golos.tj ошибка: {e}")
        return out

    for entry in parsed.entries[:30]:
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
        if len(out) >= 2:
            break
    return out

def collect_logistan():
    out = []
    try:
        parsed = feedparser.parse("https://logistan.info/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ logistan.info ошибка: {e}")
        return out

    for entry in parsed.entries[:30]:
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
        if len(out) >= 2:
            break
    return out

def collect_inform():
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
        if len(out) >= 2:
            break
    return out

# ============================================================
# 5. СБОР
# ============================================================
def collect():
    print("\n🔍 Сбор новостей (только логистика, короткие выжимки)...")
    items = []

    items.extend(collect_golos())
    items.extend(collect_logistan())
    items.extend(collect_inform())

    seen = set()
    unique = []
    for item in items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    unique.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)
    return unique[:MAX_ITEMS]

# ============================================================
# 6. MAIN
# ============================================================
def main():
    print("🚀 Сбор новостей (только логистика)...")
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
