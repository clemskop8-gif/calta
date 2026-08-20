"""
Обновляет data/news.json — новости с golos.tj, logistan.info, inform.kz.
Ровно 6 новостей (по 2 с каждого сайта).
Фильтр: логистика + страны ЦА.
БЕЗ ДЕМО-ЗАГЛУШЕК.
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
    """Проверяет: логистика + страна ЦА"""
    if not title:
        return False
    full_text = (title + " " + summary).lower()
    
    # Должна быть логистика
    has_log = any(root in full_text for root in LOGISTICS_ROOTS)
    if not has_log:
        return False
    
    # Должна быть страна ЦА
    has_country = any(country in full_text for country in CENTRAL_ASIA)
    if not has_country:
        return False
    
    return True

# ============================================================
# 2. КАРТИНКИ
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
# 3. ПАРСИНГ САЙТОВ (без демо-заглушек)
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
        print(f"    ✅ inform.kz: {title[:40]}...")
        if len(out) >= 2:
            break
    return out

# ============================================================
# 4. СБОР (без демо-заглушек)
# ============================================================
def collect():
    print("\n🔍 Сбор новостей (только логистика + страны ЦА)...")
    items = []

    items.extend(collect_golos())
    items.extend(collect_logistan())
    items.extend(collect_inform())

    # Убираем дубликаты
    seen = set()
    unique = []
    for item in items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # Сортируем по дате (свежие сверху)
    unique.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)

    # Берем ровно 6 (если меньше — будет меньше, без заглушек)
    return unique[:MAX_ITEMS]

# ============================================================
# 5. MAIN
# ============================================================
def main():
    print("🚀 Сбор новостей (ровно 6, без заглушек)...")
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

if __name__ == "__main__":
    main()
