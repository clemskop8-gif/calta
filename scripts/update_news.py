"""
Обновляет data/news.json — новости ТОЛЬКО о логистике с asiaplus.news/novosti/ и 24.kg.
Без рерайта. Картинки из Unsplash.
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
MAX_ITEMS = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Только логистические ключевые слова
LOGISTICS_KEYWORDS = [
    "логист", "транспорт", "перевозк", "груз", "контейнер",
    "порт", "терминал", "склад", "жд", "железнодорож",
    "коридор", "экспорт", "импорт", "фрахт", "автоперевоз",
    "транзит", "вагон", "локомотив", "магистраль",
    "логистик", "инфраструктур", "транспортн",
]

def is_logistics(text):
    """Проверяет, есть ли в тексте логистические слова"""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in LOGISTICS_KEYWORDS)

def pick_photo_from_unsplash(title):
    """Берет картинку из Unsplash по заголовку"""
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
    # Запасные картинки
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

def _meta_tag(html, prop):
    for pattern in (
        r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\']',
    ):
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""

# ============================================================
# 1. ПАРСИНГ asiaplus.news/novosti/
# ============================================================
def collect_asiaplus():
    out = []
    url = "https://asiaplus.news/novosti/"
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"asiaplus ошибка: {e}")
        return out

    # Ищем все ссылки на статьи
    links = set()
    for link in re.findall(r'href=["\'](https?://asiaplus\.news/[^"\']+\.html)["\']', html_content, re.IGNORECASE):
        links.add(link)

    print(f"asiaplus: найдено {len(links)} ссылок")

    for article_url in list(links)[:10]:
        try:
            ar = requests.get(article_url, timeout=20, headers=HEADERS)
            ar.raise_for_status()
            article_html = ar.text
        except Exception:
            continue

        title = _meta_tag(article_html, "og:title")
        if not title:
            continue
        summary = _meta_tag(article_html, "og:description")[:300]
        published = _meta_tag(article_html, "article:published_time")

        # ФИЛЬТР: только логистика
        if not is_logistics(title + " " + summary):
            print(f"  ⏭ пропущено (не логистика): {title[:40]}...")
            continue

        photo = pick_photo_from_unsplash(title)
        out.append({
            "title": title,
            "summary": summary or "Подробнее в источнике.",
            "publishedAt": published,
            "photo": photo,
        })
        print(f"  ✅ asiaplus: {title[:50]}...")

    return out

# ============================================================
# 2. ПАРСИНГ 24.kg (RSS)
# ============================================================
def collect_24kg():
    out = []
    url = "https://24.kg/feed/"
    try:
        parsed = feedparser.parse(url, request_headers=HEADERS)
    except Exception as e:
        print(f"24.kg ошибка: {e}")
        return out

    print(f"24.kg: найдено {len(parsed.entries)} записей")

    for entry in parsed.entries[:10]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("summary") or "")[:300]

        # ФИЛЬТР: только логистика
        if not is_logistics(title + " " + summary):
            print(f"  ⏭ пропущено (не логистика): {title[:40]}...")
            continue

        photo = pick_photo_from_unsplash(title)
        out.append({
            "title": title,
            "summary": summary or "Подробнее в источнике.",
            "publishedAt": entry.get("published", ""),
            "photo": photo,
        })
        print(f"  ✅ 24.kg: {title[:50]}...")

    return out

# ============================================================
# 3. СБОР
# ============================================================
def collect():
    items = []
    print("\n🔍 Парсинг asiaplus.news/novosti/...")
    items.extend(collect_asiaplus())
    print("\n🔍 Парсинг 24.kg...")
    items.extend(collect_24kg())

    # Убираем дубликаты
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
# 4. MAIN
# ============================================================
def main():
    print("🚀 Сбор новостей о логистике...")
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
    for i, item in enumerate(items[:3]):
        print(f"  {i+1}. {item['title'][:60]}...")

if __name__ == "__main__":
    main()
