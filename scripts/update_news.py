"""
Обновляет data/news.json свежими карточками новостей.

Источники новостей: список RSS-лент ниже (бесплатно, без ключа —
поменяйте на реальные отраслевые ленты, какие вам нужны).

Фото: Unsplash API, бесплатный тариф (до 50 запросов/час).
Получить ключ: https://unsplash.com/developers
Ключ берётся из переменной окружения UNSPLASH_ACCESS_KEY (GitHub Secrets),
в коде не хранится.

Если ключ не задан или запрос не удался — карточка получает
photo: null, и сайт покажет красивый плейсхолдер вместо фото
(как сейчас в макете).
"""
import json
import os
from datetime import datetime, timezone
import feedparser
import requests

UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
MAX_ITEMS = 5

# Замените на реальные интересующие вас RSS-ленты по логистике/торговле/ЦА
FEEDS = [
    {"url": "https://tass.ru/rss/v2.xml", "tag": "Новости"},
    {"url": "https://www.railfreight.com/feed", "tag": "Логистика"},
]


def pick_photo(query):
    if not UNSPLASH_KEY:
        return None
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
            timeout=15,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            return None
        photo = results[0]
        return {
            "url": photo["urls"]["regular"],
            "credit": photo["user"]["name"],
            "creditUrl": photo["user"]["links"]["html"],
        }
    except Exception as e:
        print("Unsplash: не удалось подобрать фото для", query, "-", e)
        return None


def collect():
    items = []
    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
        except Exception as e:
            print("Не удалось прочитать ленту", feed["url"], e)
            continue
        for entry in parsed.entries[:3]:
            title = entry.get("title", "").strip()
            if not title:
                continue
            summary = (entry.get("summary") or "")[:220].strip()
            items.append({
                "topic": feed["tag"],
                "title": title,
                "summary": summary,
                "sourceUrl": entry.get("link", ""),
                "publishedAt": entry.get("published", ""),
                "photo": pick_photo(title),
            })
        if len(items) >= MAX_ITEMS:
            break
    return items[:MAX_ITEMS]


def main():
    items = collect()
    data = {
        "isDemo": len(items) == 0,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Записано:", OUT_PATH, "-> карточек:", len(items))


if __name__ == "__main__":
    main()
