"""
Обновляет data/news.json — логистические новости со всего мира,
с автоматическим переводом на русский язык.
Новости о странах ЦА получают приоритет.
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

# ============================================================
# 1. СТРАНЫ ЦА (для приоритета)
# ============================================================
CENTRAL_ASIA = [
    "казахстан", "kazakhstan", "kz",
    "узбекистан", "uzbekistan", "uz",
    "кыргызстан", "kyrgyzstan", "kg",
    "таджикистан", "tajikistan", "tj",
    "туркменистан", "turkmenistan", "tm",
    "central asia", "центральная азия",
    "астана", "astana", "алматы", "almaty",
    "ташкент", "tashkent", "бишкек", "bishkek",
    "душанбе", "dushanbe", "ашхабад", "ashgabat",
]

# ============================================================
# 2. ЛОГИСТИЧЕСКИЕ КЛЮЧЕВЫЕ СЛОВА
# ============================================================
LOGISTICS_WORDS = [
    "logist", "freight", "cargo", "shipping", "rail", "railway",
    "port", "container", "customs", "truck", "warehous",
    "transport", "corridor", "export", "import", "carrier",
    "vessel", "intermodal", "supply chain", "logistics",
    "логист", "груз", "перевозк", "транспорт", "порт",
    "контейнер", "таможен", "склад", "жд", "железнодорож",
    "коридор", "экспорт", "импорт", "фрахт",
]


def is_logistics(text):
    text = text.lower()
    return any(w in text for w in LOGISTICS_WORDS)


def is_central_asia(text):
    text = text.lower()
    return any(c in text for c in CENTRAL_ASIA)


def translate_text(text, target_lang='ru'):
    """Перевод текста через бесплатный Google Translate"""
    if not text or len(text.strip()) < 3:
        return text
    
    try:
        # Проверяем, есть ли кириллица (уже русский)
        cyrillic = sum(1 for c in text if 'а' <= c <= 'я' or 'ё' == c)
        if cyrillic > len(text) * 0.3:
            return text  # уже русский
        
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": target_lang,
            "dt": "t",
            "q": text[:500]  # ограничиваем длину
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        
        data = r.json()
        if data and len(data) > 0 and data[0]:
            translated = ''.join([part[0] for part in data[0] if part[0]])
            return translated.strip()
    except Exception as e:
        print(f"Translation error: {e}")
    
    return text


# ============================================================
# 3. ИСТОЧНИКИ
# ============================================================
FEEDS = [
    {"url": "https://www.inform.kz/tag/logistika_t11100", "tag": "Казинформ", "query": "kazakhstan logistics", "type": "kazinform", "cap": 4},
    {"url": "https://www.inform.kz/tag/transport_t11012", "tag": "Казинформ", "query": "kazakhstan transport", "type": "kazinform", "cap": 2},
    {"url": "https://kun.uz/ru/news/feed", "tag": "Kun.uz", "query": "uzbekistan logistics", "type": "rss", "cap": 2},
    {"url": "https://24.kg/feed/", "tag": "24.kg", "query": "kyrgyzstan transport", "type": "rss", "cap": 2},
    {"url": "https://asiaplustj.info/ru/rss", "tag": "Азия-Плюс", "query": "tajikistan logistics", "type": "rss", "cap": 2},
    {"url": "https://turkmenportal.com/rss", "tag": "Туркменпортал", "query": "turkmenistan transport", "type": "rss", "cap": 2},
    {"url": "https://www.railfreight.com/feed", "tag": "RailFreight", "query": "rail freight", "type": "rss", "cap": 2},
    {"url": "https://theloadstar.com/feed/", "tag": "The Loadstar", "query": "logistics shipping", "type": "rss", "cap": 2},
    {"url": "https://www.supplychaindive.com/feeds/news/", "tag": "SupplyChainDive", "query": "supply chain", "type": "rss", "cap": 2},
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
        summary = strip_html(entry.get("summary") or "")[:300]
        
        # Пропускаем только если нет логистических слов
        if not is_logistics(title + " " + summary):
            continue
        
        # ПЕРЕВОД на русский
        title_ru = translate_text(title)
        summary_ru = translate_text(summary)
        
        # Определяем приоритет (есть ли страны ЦА)
        ca_score = 2 if is_central_asia(title + " " + summary) else 0
        
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
            "title": title_ru,
            "summary": summary_ru or "Подробности — по ссылке на источник.",
            "sourceUrl": entry.get("link", ""),
            "publishedAt": entry.get("published", ""),
            "photo": photo,
            "_ca_score": ca_score,
            "_original_title": title,  # сохраняем оригинал для отладки
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
        summary = _meta_tag(article_html, "og:description")[:300]
        image_url = _meta_tag(article_html, "og:image")
        published = _meta_tag(article_html, "article:published_time")

        if not is_logistics(title + " " + summary):
            continue

        # Определяем приоритет (есть ли страны ЦА)
        ca_score = 2 if is_central_asia(title + " " + summary) else 1

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
            "_ca_score": ca_score,
        })
    return out


def collect():
    items = []
    seen_titles = set()
    
    for feed in FEEDS:
        if len(items) >= MAX_ITEMS * 2:
            break
        feed_type = feed.get("type", "rss")
        new_items = collect_from_kazinform(feed) if feed_type == "kazinform" else collect_from_rss(feed)
        cap = feed.get("cap", MAX_ITEMS)
        for it in new_items[:cap]:
            title_key = it["title"][:50].lower()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            items.append(it)
    
    # Сортируем: сначала новости о странах ЦА
    items.sort(key=lambda x: x.get("_ca_score", 0), reverse=True)
    
    # Удаляем временные поля
    for item in items:
        item.pop("_ca_score", None)
        item.pop("_original_title", None)
    
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
    
    # Показываем заголовки для проверки
    for i, item in enumerate(items):
        print(f"{i+1}. {item['title'][:60]}...")


if __name__ == "__main__":
    main()
