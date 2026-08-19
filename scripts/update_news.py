"""
Обновляет data/news.json — логистические новости с приоритетом для стран ЦА
"""
import html
import json
import os
import re
from datetime import datetime, timezone
import feedparser
import requests

UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
MAX_ITEMS = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Страны Центральной Азии (для приоритета)
CENTRAL_ASIA = [
    "казахстан", "kazakhstan", "kz",
    "узбекистан", "uzbekistan", "uz",
    "кыргызстан", "kyrgyzstan", "kg",
    "таджикистан", "tajikistan", "tj",
    "туркменистан", "turkmenistan", "tm",
    "центральная азия", "central asia",
    "астана", "astana", "алматы", "almaty",
    "ташкент", "tashkent", "бишкек", "bishkek",
    "душанбе", "dushanbe", "ашхабад", "ashgabat",
]

# Логистические ключевые слова
LOGISTICS_WORDS = [
    "logist", "freight", "cargo", "shipping", "rail", "railway",
    "port", "container", "customs", "truck", "warehous", 
    "transport", "corridor", "export", "import", "carrier",
    "vessel", "intermodal", "supply chain",
    "логист", "груз", "перевозк", "транспорт", "порт",
    "контейнер", "таможен", "склад", "жд", "железнодорож",
    "коридор", "экспорт", "импорт", "фрахт",
]

FEEDS = [
    {"url": "https://www.inform.kz/tag/logistika_t11100", "tag": "Казинформ", "query": "kazakhstan logistics", "type": "kazinform", "cap": 4},
    {"url": "https://www.railfreight.com/feed", "tag": "RailFreight", "query": "rail freight", "cap": 2},
    {"url": "https://theloadstar.com/feed/", "tag": "The Loadstar", "query": "logistics shipping", "cap": 2},
    {"url": "https://www.supplychaindive.com/feeds/news/", "tag": "SupplyChainDive", "query": "supply chain", "cap": 2},
]


def is_logistics(text):
    text = text.lower()
    return any(w in text for w in LOGISTICS_WORDS)


def is_central_asia(text):
    text = text.lower()
    return any(c in text for c in CENTRAL_ASIA)


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
        print("Unsplash error:", e)
        return None


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def collect_from_rss(feed):
    out = []
    try:
        parsed = feedparser.parse(feed["url"], request_headers=HEADERS)
    except Exception as e:
        print("RSS error", feed["url"], e)
        return out
    
    for entry in parsed.entries[:10]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("summary") or "")[:220]
        
        # Пропускаем только если нет логистических слов
        if not is_logistics(title + " " + summary):
            continue
        
        photo = None
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('url'):
                    photo = {"url": media['url'], "credit": feed["tag"], "creditUrl": entry.get("link", "")}
                    break
        
        if not photo:
            photo = pick_photo(feed["query"])
        
        out.append({
            "topic": feed["tag"],
            "title": title,
            "summary": summary or "Подробности — по ссылке на источник.",
            "sourceUrl": entry.get("link", ""),
            "publishedAt": entry.get("published", ""),
            "photo": photo,
            "_ca_score": 2 if is_central_asia(title + " " + summary) else 0,
        })
    return out


KAZINFORM_ARTICLE_RE = re.compile(r'href="(https://www\.inform\.kz/ru/[a-z0-9\-]+-[a-f0-9]{8})"')


def _meta_tag(html_text, prop):
    for pattern in (
        r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\']',
    ):
        m = re.search(pattern, html_text, re.IGNORECASE)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def collect_from_kazinform(feed):
    out = []
    try:
        r = requests.get(feed["url"], timeout=20, headers=HEADERS)
        r.raise_for_status()
        listing_html = r.text
    except Exception as e:
        print("Kazinform error", feed["url"], e)
        return out

    seen = set()
    urls = []
    for m in KAZINFORM_ARTICLE_RE.finditer(listing_html):
        u = m.group(1)
        if u not in seen:
            seen.add(u)
            urls.append(u)
    urls = urls[:10]

    for url in urls:
        try:
            ar = requests.get(url, timeout=20, headers=HEADERS)
            ar.raise_for_status()
            article_html = ar.text
        except Exception as e:
            print("Article error", url, e)
            continue

        title = _meta_tag(article_html, "og:title")
        if not title:
            continue
        summary = _meta_tag(article_html, "og:description")[:220]
        image_url = _meta_tag(article_html, "og:image")
        published = _meta_tag(article_html, "article:published_time")

        if not is_logistics(title + " " + summary):
            continue

        photo = None
        if image_url and "plug.png" not in image_url:
            photo = {"url": image_url, "credit": "Казинформ", "creditUrl": url}
        else:
            photo = pick_photo("logistics transport")

        out.append({
            "topic": "Казинформ",
            "title": title,
            "summary": summary or "Подробности — по ссылке на источник.",
            "sourceUrl": url,
            "publishedAt": published,
            "photo": photo,
            "_ca_score": 2 if is_central_asia(title + " " + summary) else 0,
        })
    return out


def collect():
    items = []
    for feed in FEEDS:
        if len(items) >= MAX_ITEMS * 2:
            break
        feed_type = feed.get("type", "rss")
        new_items = collect_from_kazinform(feed) if feed_type == "kazinform" else collect_from_rss(feed)
        cap = feed.get("cap", MAX_ITEMS)
        for it in new_items[:cap]:
            items.append(it)
    
    # Сортируем: сначала новости о странах ЦА
    items.sort(key=lambda x: x.get("_ca_score", 0), reverse=True)
    
    # Удаляем временное поле
    for item in items:
        item.pop("_ca_score", None)
    
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
    print(f"Записано: {OUT_PATH} -> карточек: {len(items)}")


if __name__ == "__main__":
    main()
