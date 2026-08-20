"""
Обновляет data/news.json — новости ТОЛЬКО с logistan.info/logistics/.
Без рерайта. Картинки из Unsplash.
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ============================================================
# 1. КАРТИНКИ ИЗ UNSPLASH
# ============================================================
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
# 2. ПАРСИНГ logistan.info/logistics/
# ============================================================
def collect_logistan():
    out = []
    url = "https://logistan.info/logistics/"
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"Logistan ошибка: {e}")
        return out

    # Ищем все ссылки на статьи
    links = set()
    for link in re.findall(r'href=["\'](https?://logistan\.info/[^"\']+)["\']', html_content, re.IGNORECASE):
        if '/logistics/' in link or '/news/' in link:
            links.add(link)

    print(f"Logistan: найдено {len(links)} ссылок")

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

        photo = pick_photo_from_unsplash(title)
        out.append({
            "title": title,
            "summary": summary or "Подробнее в источнике.",
            "publishedAt": published,
            "photo": photo,
        })
        print(f"  ✅ Logistan: {title[:50]}...")

    return out

# ============================================================
# 3. СБОР
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
    return unique[:MAX_ITEMS]

# ============================================================
# 4. MAIN
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
