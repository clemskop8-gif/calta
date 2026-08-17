import json
import os
from datetime import datetime, timezone

import requests


# ==========================================
# НАСТРОЙКИ
# ==========================================

# Ссылка берётся из GitHub:
# Settings → Secrets and variables → Actions → Variables
FEED_URL = os.environ.get("NEWS_FEED_URL", "").strip()

# news.json находится в той же папке, что и этот файл
OUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "news.json"
)

# Максимальное количество новостей
MAX_ITEMS = 10


# ==========================================
# ПОЛУЧЕНИЕ НОВОСТЕЙ
# ==========================================

def collect_news():
    if not FEED_URL:
        raise RuntimeError(
            "Переменная NEWS_FEED_URL не задана. "
            "Добавьте её в GitHub → Settings → Secrets and variables → Actions → Variables."
        )

    print("Получаем новости из:")
    print(FEED_URL)

    response = requests.get(
        FEED_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    data = response.json()

    # Ваша JSON-лента имеет структуру:
    #
    # {
    #   "isDemo": false,
    #   "updatedAt": "...",
    #   "items": [...]
    # }

    items = data.get("items", [])

    if not isinstance(items, list):
        raise ValueError(
            "В JSON не найден правильный массив 'items'."
        )

    news = []

    for item in items:

        if not isinstance(item, dict):
            continue

        title = str(
            item.get("title", "")
        ).strip()

        if not title:
            continue

        summary = str(
            item.get("summary", "")
        ).strip()

        source_url = str(
            item.get("sourceUrl", "")
        ).strip()

        published_at = str(
            item.get("publishedAt", "")
        ).strip()

        topic = str(
            item.get("topic", "Логистика")
        ).strip()

        photo = item.get("photo")

        # Если картинки нет, записываем null
        if not photo:
            photo = None

        news.append({
            "topic": topic,
            "title": title,
            "summary": summary,
            "sourceUrl": source_url,
            "publishedAt": published_at,
            "photo": photo
        })

        if len(news) >= MAX_ITEMS:
            break

    return news


# ==========================================
# СОХРАНЕНИЕ
# ==========================================

def save_news(items):

    result = {
        "isDemo": len(items) == 0,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": items
    }

    with open(
        OUT_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"Новости сохранены: {OUT_PATH}"
    )

    print(
        f"Количество новостей: {len(items)}"
    )


# ==========================================
# ЗАПУСК
# ==========================================

def main():

    try:

        news = collect_news()

        save_news(news)

        print("Обновление завершено успешно.")

    except Exception as error:

        print("ОШИБКА:")
        print(error)

        raise


if __name__ == "__main__":
    main()
