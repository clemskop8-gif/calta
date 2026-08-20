"""
Обновляет data/news.json — новости с golos.tj, logistan.info, inform.kz.
Берет по ДВЕ новости с каждого сайта (всего 6).
Картинки подбираются по смыслу заголовка.
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
    """
    Подбирает картинку ПО СМЫСЛУ заголовка.
    Использует ключевые слова из заголовка для поиска.
    """
    if not UNSPLASH_KEY:
        return None
    
    # Очищаем заголовок от лишних символов
    clean_title = re.sub(r'[^\w\s]', ' ', title)
    
    # Берем первые 4-5 значащих слов для поиска
    words = [w for w in clean_title.split() if len(w) > 3][:4]
    
    # Словарь ключевых слов → темы для поиска
    topic_map = {
        'поезд': 'train',
        'вагон': 'train',
        'железнодорож': 'railway',
        'жд': 'railway',
        'порт': 'port',
        'судно': 'ship',
        'контейнер': 'container',
        'терминал': 'terminal',
        'склад': 'warehouse',
        'хаб': 'logistics hub',
        'груз': 'cargo',
        'фрахт': 'freight',
        'транзит': 'transit',
        'коридор': 'corridor',
        'инфраструктур': 'infrastructure',
        'строительств': 'construction',
        'дорог': 'road',
        'аэропорт': 'airport',
    }
    
    # Определяем тему поиска
    search_query = "logistics transport"
    for word in words:
        word_lower = word.lower()
        for key, topic in topic_map.items():
            if key in word_lower:
                search_query = topic
                break
        if search_query != "logistics transport":
            break
    
    # Если не нашли тему — используем первые слова
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
    
    # Запасные картинки по темам (на случай ошибки)
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
        "Логистика": ["логист", "транспорт", "перевозк", "груз", "контейнер", "фрахт", "транзит", "коридор"],
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
# 1. ПАРСИНГ КАЖДОГО САЙТА (по 2 новости)
# ============================================================

def collect_golos():
    out = []
    try:
        parsed = feedparser.parse("https://golos.tj/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ golos.tj ошибка: {e}")
        return out

    count = 0
    for entry in parsed.entries[:15]:
        if count >= 2:
            break
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
        count += 1
        print(f"    ✅ golos.tj #{count}: {title[:40]}...")
    return out

def collect_logistan():
    out = []
    try:
        parsed = feedparser.parse("https://logistan.info/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ logistan.info ошибка: {e}")
        return out

    count = 0
    for entry in parsed.entries[:15]:
        if count >= 2:
            break
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
        count += 1
        print(f"    ✅ logistan.info #{count}: {title[:40]}...")
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
    for article_url in list(links)[:10]:
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
        count += 1
        print(f"    ✅ inform.kz #{count}: {title[:40]}...")
    return out

# ============================================================
# 2. СБОР
# ============================================================
def collect():
    print("\n🔍 Сбор новостей...")
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

    # Сортируем по дате (свежие сверху)
    unique.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)

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
            {
                "source": "golos.tj",
                "topic": "Экономика",
                "title": "Экономический рост в Центральной Азии",
                "summary": "Регион показывает устойчивое развитие.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1519003722824-356d8a3ff1a1?w=800"},
            },
            {
                "source": "logistan.info",
                "topic": "Порты",
                "title": "Модернизация портовой инфраструктуры",
                "summary": "В регионе планируется обновление портовых мощностей.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1582721478779-0ae163c05a60?w=800"},
            },
            {
                "source": "inform.kz",
                "topic": "Логистика",
                "title": "Новые логистические маршруты в регионе",
                "summary": "Развитие транспортных коридоров продолжается.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=800"},
            },
        ]
        unique = demo_items

    return unique[:MAX_ITEMS]

# ============================================================
# 3. MAIN
# ============================================================
def main():
    print("🚀 Сбор новостей (по 2 с каждого сайта = 6)...")
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
