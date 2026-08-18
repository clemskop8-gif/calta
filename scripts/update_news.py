"""
Обновляет data/news.json карточками новостей строго по теме логистики.

Источники — специализированные логистические RSS-ленты (не общие
новостные, чтобы не попадала политика/спорт и т.п.). При желании
поменяйте/добавьте свои в FEEDS ниже — ключ не нужен, RSS всегда бесплатно.

Дополнительно каждая новость проверяется функцией is_relevant() по
списку ключевых слов LOGISTICS_KEYWORDS — даже если в ленте случайно
окажется нерелевантный материал, он будет отброшен и на сайт не попадёт.

Фото: Unsplash API, бесплатный тариф (до 50 запросов/час).
Ключ берётся из переменной окружения UNSPLASH_ACCESS_KEY (GitHub Secrets),
в коде не хранится. Если не задан/запрос не удался — photo: null,
сайт покажет плейсхолдер вместо фото.
"""
import json
import os
from datetime import datetime, timezone
import feedparser
import requests

UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
MAX_ITEMS = 8

# Специализированные логистические ленты.
# type: "rss" (по умолчанию) или "jsonfeed" (формат jsonfeed.org — как у Politepol).
# skip_filter: True — не прогонять через LOGISTICS_KEYWORDS (лента и так
# уже отфильтрована источником по теме, доп. фильтр может ошибочно
# отбросить материал, который не содержит ключевых слов дословно).
FEEDS = [
    {"url": "https://www.railfreight.com/feed", "tag": "Логистика", "query": "cargo logistics shipping"},
    {"url": "https://theloadstar.com/feed/", "tag": "Логистика", "query": "freight shipping port"},
    {"url": "https://www.supplychaindive.com/feeds/news/", "tag": "Логистика", "query": "supply chain freight"},
    {
        "url": "https://politepaul.com/fd/bMbNMuk48rmc.json",
        "tag": "Казинформ",
        "query": "kazakhstan logistics transport",
        "type": "jsonfeed",
        "skip_filter": True,
    },
]

# Новость должна содержать хотя бы одно из этих слов (в заголовке или
# кратком описании), иначе отбрасывается — даже если пришла из
# "логистической" ленты. Поддержаны русские и английские варианты.
LOGISTICS_KEYWORDS = [
    "logist", "freight", "cargo", "shipping", "supply chain", "rail", "railway",
    "port ", "container", "customs", "truck", "warehous", "transport", "corridor",
    "export", "import", "carrier", "vessel", "intermodal",
    "логист", "груз", "перевозк", "транспорт", "порт", "контейнер", "таможен",
    "склад", "жд", "железнодорож", "коридор", "экспорт", "импорт", "фрахт",
    "судоходств", "автоперевоз", "грузопоток",
]


def is_relevant(title, summary):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in LOGISTICS_KEYWORDS)


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


def collect_from_rss(feed):
    out = []
    try:
        parsed = feedparser.parse(feed["url"])
    except Exception as e:
        print("Не удалось прочитать ленту", feed["url"], e)
        return out
    for entry in parsed.entries[:8]:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        summary = (entry.get("summary") or "")[:220].strip()

        if not feed.get("skip_filter") and not is_relevant(title, summary):
            continue

        out.append({
            "topic": feed["tag"],
            "title": title,
            "summary": summary,
            "sourceUrl": entry.get("link", ""),
            "publishedAt": entry.get("published", ""),
            "photo": pick_photo(feed["query"]),
        })
    return out


def collect_from_jsonfeed(feed):
    out = []
    try:
        r = requests.get(feed["url"], timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("Не удалось прочитать JSON-ленту", feed["url"], e)
        return out

    for entry in (data.get("items") or [])[:8]:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        summary = (entry.get("content_text") or entry.get("summary") or "").strip()[:220]

        if not feed.get("skip_filter") and not is_relevant(title, summary):
            continue

        # используем настоящее фото из статьи, если оно есть и это не
        # техническая заглушка источника (например их "plug.png")
        image_url = entry.get("image") or ""
        photo = None
        if image_url and "plug.png" not in image_url:
            photo = {
                "url": image_url,
                "credit": feed["tag"],
                "creditUrl": entry.get("url") or entry.get("id") or feed["url"],
            }
        else:
            photo = pick_photo(feed["query"])

        out.append({
            "topic": feed["tag"],
            "title": title,
            "summary": summary,
            "sourceUrl": entry.get("url") or entry.get("id", ""),
            "publishedAt": entry.get("date_published", ""),
            "photo": photo,
        })
    return out


def collect():
    items = []
    for feed in FEEDS:
        if len(items) >= MAX_ITEMS:
            break
        feed_type = feed.get("type", "rss")
        new_items = collect_from_jsonfeed(feed) if feed_type == "jsonfeed" else collect_from_rss(feed)
        for it in new_items:
            items.append(it)
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
