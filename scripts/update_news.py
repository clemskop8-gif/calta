"""
Обновляет data/news.json — новости из RSS-ленты logistan.info.
RSS: https://logistan.info/feed/
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

# ============================================================
# 1. ПАРСИНГ RSS ЛЕНТЫ LOGISTAN
# ============================================================
def collect_logistan_rss():
    out = []
    rss_url = "https://logistan.info/feed/"

    try:
        print(f"  Загружаю RSS: {rss_url}...")
        parsed = feedparser.parse(rss_url, request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ Ошибка загрузки RSS: {e}")
        return out

    print(f"  Найдено записей: {len(parsed.entries)}")

    for entry in parsed.entries[:10]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue

        summary = strip_html(entry.get("description") or entry.get("summary") or "")[:300]
        link = entry.get("link", "")
        published = entry.get("published", "")

        # Пробуем найти картинку в RSS
        photo = None
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('url'):
                    photo = {"url": media['url']}
                    break

        # Если картинки нет — Unsplash
        if not photo:
            photo = pick_photo_from_unsplash(title)

        out.append({
            "title": title,
            "summary": summary or "Подробнее в источнике.",
            "publishedAt": published,
            "photo": photo,
        })
        print(f"  ✅ Добавлено: {title[:50]}...")

    return out

# ============================================================
# 2. СБОР
# ============================================================
def collect():
    items = []
    print("\n🔍 Парсинг RSS Logistan...")
    items.extend(collect_logistan_rss())

    # Убираем дубликаты
    seen = set()
    unique = []
    for item in items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    unique.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)

    # Если новостей нет — демо
    if len(unique) == 0:
        print("⚠️ Новостей не найдено! Добавляем демо-новости.")
        demo_items = [
            {
                "title": "Белоруссия отправила первый сквозной грузовой поезд в Узбекистан",
                "summary": "Первый сквозной грузовой поезд «Славянский караван» отправили 30 июля 2026 года со станции Орша-Восточная.",
                "publishedAt": "2026-07-31",
                "photo": {"url": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800"},
            },
            {
                "title": "Логистический хаб открылся в Центральной Азии",
                "summary": "Новый транспортный центр начал работу, что улучшит грузоперевозки в регионе.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1494412574643-ff11b0a5c1c3?w=800"},
            },
        ]
        unique = demo_items

    return unique[:MAX_ITEMS]

# ============================================================
# 3. MAIN
# ============================================================
def main():
    print("🚀 Сбор новостей из RSS Logistan...")
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
