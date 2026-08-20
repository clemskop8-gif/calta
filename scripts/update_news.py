"""
Обновляет data/news.json — новости ТОЛЬКО с logistan.info/logistics/.
С обрабо
```ткой ошибок.
"""
import html
import json
import os
import re
import random
from datetime import datetime, timezone
import requests

UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
MAX_ITEMS = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

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
    except Exception as e:
        print(f"  Unsplash ошибка: {e}")
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
# 1. ПАРСИНГ logistan.info/logistics/
# ============================================================
def collect_logistan():
    out = []
    url = "https://logistan.info/logistics/"
    try:
        print(f"  Загружаю {url}...")
        r = requests.get(url, timeout=30, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
        print(f"  Загружено {len(html_content)} символов")
    except Exception as e:
        print(f"  ❌ Ошибка загрузки Logistan: {e}")
        return out

    # Ищем все ссылки на статьи
    links = set()
    # Ищем ссылки в href
    for link in re.findall(r'href=["\']([^"\']+)["\']', html_content, re.IGNORECASE):
        if '/logistics/' in link or '/news/' in link:
            if link.startswith('/'):
                link = 'https://logistan.info' + link
            if link.startswith('http'):
                links.add(link)

    print(f"  Найдено {len(links)} ссылок")

    for article_url in list(links)[:10]:
        try:
            print(f"  Загружаю статью: {article_url[:60]}...")
            ar = requests.get(article_url, timeout=30, headers=HEADERS)
            ar.raise_for_status()
            article_html = ar.text
        except Exception as e:
            print(f"  ❌ Ошибка загрузки статьи: {e}")
            continue

        title = _meta_tag(article_html, "og:title")
        if not title:
            # Пробуем найти title в <title>
            title_match = re.search(r'<title>([^<]+)</title>', article_html)
            if title_match:
                title = title_match.group(1).strip()
        if not title:
            print(f"  ⏭ Нет заголовка, пропускаем")
            continue

        summary = _meta_tag(article_html, "og:description")[:300]
        if not summary:
            # Пробуем найти описание в meta name="description"
            desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', article_html, re.IGNORECASE)
            if desc_match:
                summary = desc_match.group(1)[:300]

        published = _meta_tag(article_html, "article:published_time")
        if not published:
            # Пробуем найти дату
            date_match = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', article_html, re.IGNORECASE)
            if date_match:
                published = date_match.group(1)

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
    print("\n🔍 Парсинг logistan.info/logistics/...")
    items.extend(collect_logistan())

    # Убираем дубликаты
    seen = set()
    unique = []
    for item in items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    unique.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)

    # Если новостей нет — добавляем демо-новости
    if len(unique) == 0:
        print("⚠️ Новостей не найдено! Добавляем демо-новости.")
        demo_items = [
            {
                "title": "Логистический хаб открылся в Центральной Азии",
                "summary": "Новый транспортный центр начал работу, что улучшит грузоперевозки в регионе.",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "photo": {"url": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800"},
            },
            {
                "title": "Развитие транспортных коридоров в регионе",
                "summary": "Страны Центральной Азии обсуждают совместные проекты по модернизации логистики.",
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
    print("🚀 Сбор новостей с Logistan...")
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
