"""
Обновляет data/news.json — новости с golos.tj, logistan.info, inform.kz.
Ровно 6 новостей (по 2 с каждого сайта).
У каждой новости своя картинка по смыслу.
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
# 1. ФИЛЬТР
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

def is_logistics(text):
    if not text:
        return False
    text_lower = text.lower()
    words = text_lower.split()
    
    log_count = 0
    for word in words:
        for root in LOGISTICS_ROOTS:
            if root in word:
                log_count += 1
                break
    
    if log_count >= 2:
        return True
    if any(root in text_lower for root in ["логистик", "транспортн"]):
        return True
    return False

def has_central_asia(text):
    if not text:
        return False
    text_lower = text.lower()
    return any(country in text_lower for country in CENTRAL_ASIA)

def is_relevant(title, summary):
    full_text = (title + " " + summary).lower()
    if not is_logistics(full_text):
        return False
    if has_central_asia(full_text):
        return True
    log_count = sum(1 for root in LOGISTICS_ROOTS if root in full_text)
    return log_count >= 3

# ============================================================
# 2. КАРТИНКИ
# ============================================================

def pick_photo_from_unsplash(title):
    """Уникальная картинка для каждой новости"""
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
# 3. ПАРСИНГ САЙТОВ (по 2 новости с каждого)
# ============================================================

def collect_golos():
    out = []
    try:
        parsed = feedparser.parse("https://golos.tj/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ golos.tj ошибка: {e}")
        return out

    count = 0
    for entry in parsed.entries[:20]:
        if count >= 2:
            break
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("description") or entry.get("summary") or "")[:300]
        
        if not is_relevant(title, summary):
            continue
            
        photo = pick_photo_from_unsplash(title)
        out.append({
            "source": "golos.tj",
            "topic": detect_topic(title, summary),
            "title": title,
            "summary": summary or "Подробнее в источнике.",
            "publishedAt": entry.get("published", ""),
            "photo": photo,
        })
        count += 1
        print(f"    ✅ golos.tj #{count}: {title[:40]}...")
    
    # Если не хватило — заполняем демо
    while len(out) < 2:
        out.append({
            "source": "golos.tj",
            "topic": "Логистика",
            "title": f"Логистические проекты в Центральной Азии (демо #{len(out)+1})",
            "summary": "Страны региона продолжают развивать транспортную инфраструктуру.",
            "publishedAt": datetime.now(timezone.utc).isoformat(),
            "photo": {"url": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800"},
        })
    return out

def collect_logistan():
    out = []
    try:
        parsed = feedparser.parse("https://logistan.info/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ logistan.info ошибка: {e}")
        return out

    count = 0
    for entry in parsed.entries[:20]:
        if count >= 2:
            break
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("description") or entry.get("summary") or "")[:300]
        
        if not is_relevant(title, summary):
            continue
            
        photo = pick_photo_from_unsplash(title)
        out.append({
            "source": "logistan.info",
            "topic": detect_topic(title, summary),
            "title": title,
            "summary": summary or "Подробнее в источнике.",
            "publishedAt": entry.get("published", ""),
            "photo": photo,
        })
        count += 1
        print(f"    ✅ logistan.info #{count}: {title[:40]}...")
    
    while len(out) < 2:
        out.append({
            "source": "logistan.info",
            "topic": "Логистика",
            "title": f"Логистические проекты в Центральной Азии (демо #{len(out)+1})",
            "summary": "Страны региона продолжают развивать транспортную инфраструктуру.",
            "publishedAt": datetime.now(timezone.utc).isoformat(),
            "photo": {"url": "https://images.unsplash.com/photo-1494412574643-ff11b0a5c1c3?w=800"},
        })
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

    count = 0
    for article_url in list(links)[:15]:
        if count >= 2:
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
        summary = meta("og:description")[:300]
        published = meta("article:published_time")

        if not is_relevant(title, summary):
            continue

        photo = pick_photo_from_unsplash(title)
        out.append({
            "source": "inform.kz",
            "topic": detect_topic(title, summary),
            "title": title,
            "summary": summary or "Подробнее в источнике.",
            "publishedAt": published,
            "photo": photo,
        })
        count += 1
        print(f"    ✅ inform.kz #{count}: {title[:40]}...")
    
    while len(out) < 2:
        out.append({
            "source": "inform.kz",
            "topic": "Логистика",
            "title": f"Логистические проекты в Центральной Азии (демо #{len(out)+1})",
            "summary": "Страны региона продолжают развивать транспортную инфраструктуру.",
            "publishedAt": datetime.now(timezone.utc).isoformat(),
            "photo": {"url": "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800"},
        })
    return out

# ============================================================
# 4. СБОР
# ============================================================
def collect():
    print("\n🔍 Сбор новостей (ровно 6)...")
    items = []

    items.extend(collect_golos())
    items.extend(collect_logistan())
    items.extend(collect_inform())

    # Убираем дубликаты по заголовку
    seen = set()
    unique = []
    for item in items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # Сортируем по дате
    unique.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)

    # Обрезаем до 6
    result = unique[:6]
    
    # Если меньше 6 — добиваем демо
    while len(result) < 6:
        result.append({
            "source": "demo",
            "topic": "Логистика",
            "title": f"Логистические проекты в Центральной Азии (демо #{len(result)+1})",
            "summary": "Страны региона продолжают развивать транспортную инфраструктуру.",
            "publishedAt": datetime.now(timezone.utc).isoformat(),
            "photo": {"url": f"https://images.unsplash.com/photo-{1494412574643 + len(result)}?w=800"},
        })

    return result[:6]

# ============================================================
# 5. MAIN
# ============================================================
def main():
    print("🚀 Сбор новостей (ровно 6, по 2 с каждого сайта)...")
    items = collect()

    data = {
        "isDemo": False,
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

if __name__ == "__main__":
    main()
