"""
Обновляет data/news.json — новости с golos.tj, logistan.info, inform.kz.
Берет по одной новости с каждого сайта по очереди (по кругу).
Только логистика.
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
MAX_ITEMS = 6  # 3 сайта × 2 круга = 6 новостей

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ============================================================
# 1. ЛОГИСТИЧЕСКИЕ КЛЮЧЕВЫЕ СЛОВА
# ============================================================
LOGISTICS_KEYWORDS = [
    "логист", "транспорт", "перевозк", "груз", "контейнер",
    "порт", "терминал", "склад", "жд", "железнодорож",
    "коридор", "экспорт", "импорт", "фрахт", "автоперевоз",
    "транзит", "вагон", "локомотив", "магистраль",
    "логистик", "инфраструктур", "транспортн", "грузоперевоз",
]

def is_logistics(text):
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in LOGISTICS_KEYWORDS)

def pick_photo_from_unsplash(title):
    if not UNSPLASH_KEY:
        return None
    try:
        clean_title = re.sub(r'[^\w\s]', ' ', title)
        words = clean_title.split()[:4]
        query = ' '.join(words) if len(words) >= 2 else "logistics"
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if results:
            return {"url": results[0]["urls"]["regular"]}
    except Exception:
        pass
    fallback = [
        "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800",
        "https://images.unsplash.com/photo-1494412574643-ff11b0a5c1c3?w=800",
        "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800",
    ]
    return {"url": random.choice(fallback)}

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
        "Логистика": ["логист", "транспорт", "перевозк", "груз", "контейнер", "фрахт", "транзит", "коридор"],
        "Инфраструктура": ["строительств", "дорог", "терминал", "склад", "хаб", "инфраструктур"],
        "Железная дорога": ["жд", "железнодорож", "поезд", "вагон", "локомотив"],
        "Порты": ["порт", "причал", "судно", "морской"],
        "Экономика": ["экономик", "инвестиц", "торговл", "рынок"],
    }
    for topic, keywords in topics.items():
        if any(kw in text for kw in keywords):
            return topic
    return "Логистика"

# ============================================================
# 2. ПАРСИНГ КАЖДОГО САЙТА
# ============================================================

# 2.1. GOLOS.TJ (RSS)
def collect_golos():
    out = []
    try:
        parsed = feedparser.parse("https://golos.tj/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ golos.tj ошибка: {e}")
        return out

    for entry in parsed.entries[:10]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("description") or entry.get("summary") or "")[:300]
        if not is_logistics(title + " " + summary):
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
        break  # берем только одну новость
    return out

# 2.2. LOGISTAN.INFO (RSS)
def collect_logistan():
    out = []
    try:
        parsed = feedparser.parse("https://logistan.info/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ logistan.info ошибка: {e}")
        return out

    for entry in parsed.entries[:10]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("description") or entry.get("summary") or "")[:300]
        if not is_logistics(title + " " + summary):
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
        break  # берем только одну новость
    return out

# 2.3. INFORM.KZ (парсинг страницы)
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

    for article_url in list(links)[:5]:
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

        if not is_logistics(title + " " + summary):
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
        break  # берем только одну новость
    return out

# ============================================================
# 3. СБОР ПО КРУГУ
# ============================================================
def collect():
    all_items = []

    # Собираем по одной новости с каждого сайта
    golos_news = collect_golos()
    logistan_news = collect_logistan()
    inform_news = collect_inform()

    print(f"\n  golos.tj: {len(golos_news)} новостей")
    print(f"  logistan.info: {len(logistan_news)} новостей")
    print(f"  inform.kz: {len(inform_news)} новостей")

    # Собираем в список
    sources = [golos_news, logistan_news, inform_news]

    # Берем по одной новости из каждого источника по кругу
    result = []
    for i in range(MAX_ITEMS):
        source_index = i % 3
        source = sources[source_index]
        if source:
            # Берем первую новость из источника (если есть)
            result.append(source[0])
            # Удаляем использованную новость
            sources[source_index] = source[1:]

    # Убираем дубликаты по заголовку
    seen = set()
    unique = []
    for item in result:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # Если новостей нет — демо
    if len(unique) == 0:
        print("⚠️ Новостей не найдено! Добавляем демо-новости.")
        demo_items = [
            {
                "source": "golos.tj",
                "topic": "Логистика",
                "title": "Развитие транспортных коридоров в Центральной Азии",
                "summary": "Страны региона обсуждают совместные проекты по модернизации логистики.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800"},
            },
            {
                "source": "logistan.info",
                "topic": "Инфраструктура",
                "title": "Новый логистический хаб открылся в регионе",
                "summary": "Объект будет способствовать развитию грузоперевозок.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1494412574643-ff11b0a5c1c3?w=800"},
            },
            {
                "source": "inform.kz",
                "topic": "Железная дорога",
                "title": "Казахстан обновляет парк пассажирских поездов",
                "summary": "За последние годы приобретено более 400 новых вагонов.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800"},
            },
        ]
        unique = demo_items

    return unique[:MAX_ITEMS]

# ============================================================
# 4. MAIN
# ============================================================
def main():
    print("🚀 Сбор новостей (по кругу: golos.tj → logistan.info → inform.kz)...")
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
        print(f"  {i+1}. [{item.get('source', '?')}] {item['title'][:60]}...")

if __name__ == "__main__":
    main()
