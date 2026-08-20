"""
Обновляет data/news.json — новости с golos.tj, logistan.info, inform.kz.
Ровно 6 новостей (по 2 с каждого сайта).
Фильтр: логистика + страны ЦА.
БЕЗ ДЕМО-ЗАГЛУШЕК.
Каждая новость имеет УНИКАЛЬНУЮ ВЫЖИМКУ (автоматический рерайт без копирования).
"""
import html
import json
import os
import re
import random
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
# 1. ФИЛЬТР: логистика + страны ЦА
# ============================================================

CENTRAL_ASIA = [
    "казахстан", "узбекистан", "кыргызстан", "таджикистан", "туркменистан",
    "каракалпакстан", "центральная азия", "средняя азия",
    "астана", "алматы", "ташкент", "бишкек", "душанбе", "ашхабад",
]

LOGISTICS_ROOTS = [
    "логист", "транспорт", "перевоз", "груз", "контейнер",
    "порт", "терминал", "склад", "железнодорож", "коридор",
    "экспорт", "импорт", "фрахт", "транзит", "инфраструктур",
]

def is_relevant(title, summary):
    if not title:
        return False
    full_text = (title + " " + summary).lower()
    
    has_log = any(root in full_text for root in LOGISTICS_ROOTS)
    if not has_log:
        return False
    
    has_country = any(country in full_text for country in CENTRAL_ASIA)
    if not has_country:
        return False
    
    return True

# ============================================================
# 2. АВТОМАТИЧЕСКАЯ ГЕНЕРАЦИЯ УНИКАЛЬНОЙ ВЫЖИМКИ (РЕРАЙТ)
# ============================================================

# Словарь синонимов для рерайта
SYNONYMS = {
    "логистика": ["транспорт", "грузоперевозки", "перевозки", "транспортная сфера"],
    "транспорт": ["логистика", "перевозки", "транспортная система"],
    "груз": ["товар", "продукция", "контейнеры"],
    "перевозки": ["транспортировка", "доставка", "грузоперевозки"],
    "порт": ["гавань", "морской терминал", "причал"],
    "контейнер": ["грузовой модуль", "контейнерный модуль", "тара"],
    "терминал": ["хаб", "распределительный центр", "логистический центр"],
    "склад": ["хранилище", "складской комплекс"],
    "железная дорога": ["ЖД", "ж/д", "рельсовый путь"],
    "коридор": ["маршрут", "направление", "трасса"],
    "инвестиция": ["вложение", "финансирование", "капитал"],
    "проект": ["программа", "инициатива", "объект"],
    "развитие": ["рост", "прогресс", "совершенствование"],
    "строительство": ["возведение", "создание", "постройка"],
    "открытие": ["запуск", "введение в эксплуатацию", "старт"],
    "крупный": ["масштабный", "значительный", "внушительный"],
    "новый": ["современный", "перспективный", "инновационный"],
    "важный": ["ключевой", "значимый", "существенный"],
    "успешный": ["результативный", "эффективный", "плодотворный"],
}

def rewrite_text(text):
    """Заменяет слова на синонимы"""
    if not text:
        return text
    words = text.split()
    new_words = []
    for word in words:
        clean_word = re.sub(r'[^\w\s]', '', word).lower()
        replaced = False
        for key, synonyms in SYNONYMS.items():
            if clean_word == key.lower() or clean_word in key.lower():
                new_word = random.choice(synonyms)
                if word[0].isupper():
                    new_word = new_word.capitalize()
                new_words.append(new_word)
                replaced = True
                break
        if not replaced:
            new_words.append(word)
    return ' '.join(new_words)

def shuffle_sentence_parts(text):
    """Перемешивает части предложения для уникальности"""
    if not text or len(text) < 30:
        return text
    
    # Разбиваем по запятым и союзам
    separators = [' и ', ',', ';', ' — ']
    parts = [text]
    for sep in separators:
        new_parts = []
        for p in parts:
            if sep in p and len(p.split(sep)) >= 2:
                new_parts.extend(p.split(sep))
            else:
                new_parts.append(p)
        parts = new_parts
    
    # Если есть части — перемешиваем
    if len(parts) >= 2:
        first = parts[0]
        rest = parts[1:]
        random.shuffle(rest)
        result = first
        for i, part in enumerate(rest):
            if part.strip():
                sep = random.choice(separators)
                result += sep + part.strip()
        return result
    
    return text

def generate_unique_summary(title, original_summary):
    """
    Генерирует УНИКАЛЬНУЮ выжимку (2-4 предложения) без копирования оригинала.
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
    
    # 2. Замена слов на синонимы
    text = rewrite_text(text)
    
    # 3. Разбиваем на предложения
    sentences = re.split(r'[.!?]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    
    # 4. Если мало предложений — создаем из заголовка
    if len(sentences) < 2:
        clean_title = re.sub(r'^(Казахстан|Узбекистан|Кыргызстан|Таджикистан|Туркменистан)\s+', '', title)
        clean_title = rewrite_text(clean_title)
        if sentences:
            return f"{clean_title}. {sentences[0]}"
        else:
            return f"{clean_title}. Подробнее в источнике."
    
    # 5. Перемешиваем части предложений
    processed_sentences = []
    for s in sentences[:3]:
        s = shuffle_sentence_parts(s)
        processed_sentences.append(s)
    
    # 6. Убираем повторы
    seen = set()
    unique_sentences = []
    for s in processed_sentences:
        key = s[:30].lower()
        if key not in seen:
            seen.add(key)
            unique_sentences.append(s)
    
    # 7. Собираем результат (2-3 предложения)
    result = '. '.join(unique_sentences[:3])
    
    # 8. Добавляем точку в конце
    if result and not result.endswith('.'):
        result += '.'
    
    # 9. Если получилось слишком коротко — используем заголовок
    if len(result) < 30:
        clean_title = rewrite_text(title)
        return f"{clean_title}. Подробнее в источнике."
    
    return result

# ============================================================
# 3. КАРТИНКИ
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
        "Логистика": ["логист", "транспорт", "перевоз", "груз", "контейнер", "фрахт", "транзит", "коридор"],
        "Инфраструктура": ["строительств", "дорог", "терминал", "склад", "хаб", "инфраструктур"],
        "Железная дорога": ["жд", "железнодорож", "поезд", "вагон", "локомотив"],
        "Порты": ["порт", "причал", "судно", "морской"],
        "Экономика": ["экономик", "инвестиц", "торговл", "рынок", "финанс"],
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
    print("\n🔍 Сбор новостей (с уникальной выжимкой)...")
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
    print("🚀 Сбор новостей (автоматический рерайт)...")
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
