"""
Получает новости из JSON-ленты PolitePaul
и сохраняет их в data/news.json.

Источник:
https://politepaul.com/fd/bMbNMuk48rmc.json

Лента уже содержит:
- название новости
- картинку
- описание
- дату
- ссылку на новость
"""

import json
import os
from datetime import datetime, timezone

import requests


# JSON-лента PolitePaul
FEED_URL = "https://politepaul.com/fd/bMbNMuk48rmc.json"

# Куда сохраняем новости
OUT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "news.json"
)

# Сколько новостей показывать на сайте
MAX_ITEMS = 10


def get_news():
    """Получает новости из JSON-ленты."""

    try:
        response = requests.get(
            FEED_URL,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        data = response.json()

        print("JSON успешно получен.")

        return data

    except Exception as e:
        print("Ошибка получения JSON:", e)
        return None


def collect():
    """Преобразует JSON PolitePaul в формат нашего сайта."""

    data = get_news()

    if not data:
        return []

    # PolitePaul может вернуть список или объект
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        # Ищем возможный массив новостей
        entries = (
            data.get("items")
            or data.get("entries")
            or data.get("news")
            or data.get("feed")
            or []
        )
    else:
        entries = []

    items = []

    for entry in entries:

        if not isinstance(entry, dict):
            continue

        # Заголовок
        title = (
            entry.get("title")
            or entry.get("name")
            or entry.get("Название")
            or ""
        ).strip()

        if not title:
            continue

        # Описание
        summary = (
            entry.get("description")
            or entry.get("summary")
            or entry.get("Описание")
            or ""
        ).strip()

        # Ссылка на оригинальную новость
        source_url = (
            entry.get("link")
            or entry.get("url")
            or entry.get("sourceUrl")
            or entry.get("Ссылка")
            or ""
        ).strip()

        # Картинка
        photo = (
            entry.get("image")
            or entry.get("photo")
            or entry.get("picture")
            or entry.get("Картинка")
            or ""
        ).strip()

        # Дата
        published_at = (
            entry.get("published")
            or entry.get("publishedAt")
            or entry.get("date")
            or entry.get("Дата")
            or ""
        ).strip()

        items.append({
            "topic": "Логистика",
            "title": title,
            "summary": summary,
            "sourceUrl": source_url,
            "publishedAt": published_at,
            "photo": photo if photo else None,
        })

        if len(items) >= MAX_ITEMS:
            break

    return items


def main():

    items = collect()

    data = {
        "isDemo": len(items) == 0,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }

    os.makedirs(
        os.path.dirname(OUT_PATH),
        exist_ok=True
    )

    with open(
        OUT_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        "Записано:",
        OUT_PATH,
        "→ карточек:",
        len(items)
    )


if __name__ == "__main__":
    main()
