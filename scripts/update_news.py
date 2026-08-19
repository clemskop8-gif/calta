"""
Обновляет data/news.json — ТОЛЬКО новости о логистике в странах ЦА:
Казахстан, Узбекистан, Кыргызстан, Таджикистан, Туркменистан.
Языки: русский, казахский (кириллица).
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
# 1. ТОЛЬКО ЭТИ СТРАНЫ (поиск в тексте новости)
# ============================================================
COUNTRIES_PATTERNS = [
    # Казахстан
    r"казахстан|қазақстан|kazakhstan|kz",
    r"астана|astana|алматы|almaty|шығыс|shygys",
    # Узбекистан
    r"узбекистан|o'zbekiston|uzbekistan|uz",
    r"ташкент|tashkent|самарканд|samarkand",
    # Кыргызстан
    r"кыргызстан|kyrgyzstan|kg|кыргыз",
    r"бишкек|bishkek|ош|osh",
    # Таджикистан
    r"таджикистан|tojikiston|tajikistan|tj",
    r"душанбе|dushanbe",
    # Туркменистан
    r"туркменистан|turkmenistan|tm",
    r"ашхабад|ashgabat",
    # Общие
    r"центральн(?:ая|ой|ую|ые|ых) ази|central asia",
    r"средн(?:яя|ей|юю|ие|их) ази|middle asia",
]

# Объединяем в одно регулярное выражение
COUNTRIES_REGEX = re.compile("|".join(COUNTRIES_PATTERNS), re.IGNORECASE)

# ============================================================
# 2. ЛОГИСТИЧЕСКИЕ КЛЮЧЕВЫЕ СЛОВА (русский + казахский)
# ============================================================
LOGISTICS_KEYWORDS = [
    # Русские
    "логистик", "груз", "перевозк", "транспорт", "порт",
    "контейнер", "таможн", "склад", "жд", "железнодорож",
    "коридор", "экспорт", "импорт", "фрахт", "судоходств",
    "автоперевоз", "грузопоток", "транзит", "терминал",
    "вагон", "локомотив", "магистраль", "автотрасс",
    "дистрибуци", "инфраструктур", "логистический",
    "транспортный", "грузовой",
    # Казахские (кириллица)
    "логистик", "жүк", "тасымал", "көлік", "порт",
    "контейнер", "кеден", "қойма", "теміржол",
    "экспорт", "импорт", "фрахт", "транзит",
    "терминал", "вагон", "локомотив",
    # Английские (для поиска в англоязычных источниках)
    "logist", "freight", "cargo", "shipping", "rail",
    "railway", "port", "container", "customs", "truck",
    "warehous", "transport", "corridor", "export",
    "import", "carrier", "vessel", "intermodal",
]

LOGISTICS_REGEX = re.compile("|".join(LOGISTICS_KEYWORDS), re.IGNORECASE)

# ============================================================
# 3. ИСТОЧНИКИ (ТОЛЬКО РУССКОЯЗЫЧНЫЕ + КАЗАХСКИЕ)
# ============================================================
FEEDS = [
    # === КАЗАХСТАН ===
    {
        "url": "https://www.inform.kz/tag/logistika_t11100",
        "tag": "Казинформ",
        "query": "казахстан логистика",
        "type": "kazinform",
        "cap": 4,
    },
    {
        "url": "https://www.inform.kz/tag/transport_t11012",
        "tag": "Казинформ",
        "query": "казахстан транспорт",
        "type": "kazinform",
        "cap": 2,
    },
    # === УЗБЕКИСТАН ===
    {
        "url": "https://kun.uz/ru/news/feed",
        "tag": "Kun.uz",
        "query": "узбекистан логистика",
        "type": "rss",
        "cap": 2,
    },
    # === КЫРГЫЗСТАН ===
    {
        "url": "https://24.kg/feed/",
        "tag": "24.kg",
        "query": "кыргызстан транспорт",
        "type": "rss",
        "cap": 2,
    },
    # === ТАДЖИКИСТАН ===
    {
        "url": "https://asiaplustj.info/ru/rss",
        "tag": "Азия-Плюс",
        "query": "таджикистан логистика",
        "type": "rss",
        "cap": 2,
    },
    # === ТУРКМЕНИСТАН ===
    {
        "url": "https://turkmenportal.com/rss",
        "tag": "Туркменпортал",
        "query": "туркменистан транспорт",
        "type": "rss",
        "cap": 2,
    },
    # === ЗАПАСНОЙ: РОССИЙСКИЙ ИСТОЧНИК (может писать о ЦА) ===
    {
        "url": "https://www.rzd-partner.ru/export/rss-news/",
        "tag": "РЖД Партнер",
        "query": "центральная азия логистика",
        "type": "rss",
        "cap": 2,
    },
]


# ============================================================
# 4. ФУНКЦИЯ ПРОВЕРКИ — НОВОСТЬ ДОЛЖНА БЫТЬ О СТРАНАХ ЦА + ЛОГИСТИКА
# ============================================================
def is_relevant(title, summary):
    """Проверяет, что новость:
    1. Упоминает одну из стран ЦА
    2. Связана с логистикой
    """
    text = (title + " " + summary)
    
    # Проверка на страны ЦА
    if not COUNTRIES_REGEX.search(text):
        return False
    
    # Проверка на логистику
    if not LOGISTICS_REGEX.search(text):
        return False
    
    return True


def pick_photo(query):
    """Получает картинку из Unsplash"""
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


# ============================================================
# 5. ПАРСИНГ RSS
# ============================================================
def collect_from_rss(feed):
    out = []
    try:
        parsed = feedparser.parse(feed["url"], request_headers=HEADERS)
    except Exception as e:
        print("RSS error", feed["url"], e)
        return out
    
    for entry in parsed.entries[:15]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("summary") or "")[:300]
        
        # ЖЕСТКИЙ ФИЛЬТР: только страны ЦА + логистика
        if not is_relevant(title, summary):
            continue
        
        # Пытаемся найти картинку
        photo = None
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('url'):
                    photo = {
                        "url": media['url'],
                        "credit": feed["tag"],
                        "creditUrl": entry.get("link", ""),
                    }
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
        })
    return out


# ============================================================
# 6. ПАРСИНГ КАЗИНФОРМА
# ============================================================
KAZINFORM_ARTICLE_RE = re.compile(
    r'href="(https://www\.inform\.kz/ru/[a-z0-9\-]+-[a-f0-9]{8})"'
)


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
    urls = urls[:15]

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

        # ЖЕСТКИЙ ФИЛЬТР
        if not is_relevant(title, summary):
            continue

        photo = None
        if image_url and "plug.png" not in image_url:
            photo = {"url": image_url, "credit": "Казинформ", "creditUrl": url}
        else:
            photo = pick_photo(feed["query"])

        out.append({
            "topic": "Казинформ",
            "title": title,
            "summary": summary or "Подробности — по ссылке на источник.",
            "sourceUrl": url,
            "publishedAt": published,
            "photo": photo,
        })
    return out


# ============================================================
# 7. СБОР
# ============================================================
def collect():
    items = []
    seen_titles = set()
    
    for feed in FEEDS:
        if len(items) >= MAX_ITEMS:
            break
        
        feed_type = feed.get("type", "rss")
        if feed_type == "kazinform":
            new_items = collect_from_kazinform(feed)
        else:
            new_items = collect_from_rss(feed)
        
        cap = feed.get("cap", MAX_ITEMS)
        for it in new_items[:cap]:
            # Убираем дубликаты по заголовку
            title_key = it["title"][:50].lower()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            items.append(it)
            if len(items) >= MAX_ITEMS:
                break
    
    return items[:MAX_ITEMS]


# ============================================================
# 8. MAIN
# ============================================================
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
    if len(items) == 0:
        print("ВНИМАНИЕ: Новостей о логистике в странах ЦА не найдено!")


if __name__ == "__main__":
    main()
