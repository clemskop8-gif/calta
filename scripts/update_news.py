"""
Обновляет data/news.json карточками новостей по логистике в Центральной Азии.

Требования:
1. Только новости на РУССКОМ языке (английские отбрасываются)
2. Только новости о странах: Казахстан, Узбекистан, Кыргызстан, Таджикистан, Туркменистан
3. Только новости о ЛОГИСТИКЕ (транспорт, перевозки, грузы, порты, ж/д и т.д.)
4. Каждая новость должна иметь картинку (из источника или Unsplash)

Источники:
- inform.kz (Казинформ) — основной русскоязычный источник
- 24.kg (Кыргызстан)
- Kun.uz (Узбекистан)  
- Азия-Плюс (Таджикистан)
- Туркменпортал (Туркменистан)
- Англоязычные источники — только если новость о странах ЦА
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
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# ============================================================
# 1. СПИСОК СТРАН ЦЕНТРАЛЬНОЙ АЗИИ (на русском и английском)
# ============================================================
CENTRAL_ASIA_COUNTRIES = [
    # Казахстан
    "казахстан", "қазақстан", "kazakhstan", "kz",
    "астана", "алматы", "astana", "almaty",
    # Узбекистан
    "узбекистан", "o'zbekiston", "uzbekistan", "uz",
    "ташкент", "tashkent", "самарканд", "samarkand",
    # Кыргызстан
    "кыргызстан", "kyrgyzstan", "kg",
    "бишкек", "bishkek", "ош", "osh",
    # Таджикистан
    "таджикистан", "tojikiston", "tajikistan", "tj",
    "душанбе", "dushanbe",
    # Туркменистан
    "туркменистан", "turkmenistan", "tm",
    "ашхабад", "ashgabat",
    # Общие
    "центральная азия", "central asia", "цар",
    "средняя азия", "middle asia",
]

# ============================================================
# 2. ЛОГИСТИЧЕСКИЕ КЛЮЧЕВЫЕ СЛОВА (только русские, чтобы
#    отсеять английские новости)
# ============================================================
LOGISTICS_KEYWORDS_RU = [
    "логист", "груз", "перевозк", "транспорт", "порт",
    "контейнер", "таможен", "склад", "жд", "железнодорож",
    "коридор", "экспорт", "импорт", "фрахт", "судоходств",
    "автоперевоз", "грузопоток", "транзит", "терминал",
    "вагон", "локомотив", "путь", "магистраль", "автотрасс",
    "логистик", "перевалк", "хранени", "дистрибуци",
    "торговля", "международн", "транспортн", "инфраструктур",
    "логистический", "грузовой", "транспортный",
]

# ============================================================
# 3. ИСТОЧНИКИ НОВОСТЕЙ
# ============================================================
FEEDS = [
    # === ОСНОВНЫЕ РУССКОЯЗЫЧНЫЕ ИСТОЧНИКИ ===
    {
        "url": "https://www.inform.kz/tag/logistika_t11100",
        "tag": "Казинформ",
        "query": "kazakhstan logistics",
        "type": "kazinform",
        "cap": 4,
        "language": "ru",
    },
    {
        "url": "https://24.kg/feed/",
        "tag": "24.kg",
        "query": "kyrgyzstan transport",
        "type": "rss",
        "cap": 2,
        "language": "ru",
    },
    {
        "url": "https://kun.uz/ru/news/feed",
        "tag": "Kun.uz",
        "query": "uzbekistan logistics",
        "type": "rss",
        "cap": 2,
        "language": "ru",
    },
    {
        "url": "https://asiaplustj.info/ru/rss",
        "tag": "Азия-Плюс",
        "query": "tajikistan transport",
        "type": "rss",
        "cap": 2,
        "language": "ru",
    },
    {
        "url": "https://turkmenportal.com/rss",
        "tag": "Туркменпортал",
        "query": "turkmenistan transport",
        "type": "rss",
        "cap": 2,
        "language": "ru",
    },
    # === ЗАПАСНЫЕ АНГЛОЯЗЫЧНЫЕ ИСТОЧНИКИ ===
    # (только если новость о странах ЦА)
    {
        "url": "https://www.railfreight.com/feed",
        "tag": "RailFreight",
        "query": "central asia rail freight",
        "type": "rss",
        "cap": 1,
        "language": "en",
    },
    {
        "url": "https://theloadstar.com/feed/",
        "tag": "The Loadstar",
        "query": "central asia logistics",
        "type": "rss",
        "cap": 1,
        "language": "en",
    },
]


# ============================================================
# 4. ФУНКЦИЯ ПРОВЕРКИ РЕЛЕВАНТНОСТИ
# ============================================================
def is_relevant(title, summary, language="ru"):
    """Проверяет, что новость:
    - о странах Центральной Азии
    - о логистике
    - на русском языке (если language='ru')
    """
    text = (title + " " + summary).lower()
    
    # Проверка на русский язык (если указано)
    if language == "ru":
        # Если в тексте нет кириллицы — это английская новость
        cyrillic_chars = sum(1 for c in text if 'а' <= c <= 'я' or 'ё' == c)
        if cyrillic_chars < 5:  # очень мало русских букв
            return False
    
    # Должна быть хотя бы одна страна ЦА
    has_country = any(country in text for country in CENTRAL_ASIA_COUNTRIES)
    if not has_country:
        return False
    
    # И хотя бы одно логистическое слово
    has_logistics = any(kw in text for kw in LOGISTICS_KEYWORDS_RU)
    if not has_logistics:
        return False
    
    return True


# ============================================================
# 5. ФУНКЦИЯ ДЛЯ КАРТИНОК
# ============================================================
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
        print("Unsplash: не удалось подобрать фото для", query, "-", e)
        return None


def strip_html(text):
    """Убирает HTML-теги из текста"""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ============================================================
# 6. ПАРСИНГ RSS
# ============================================================
def collect_from_rss(feed):
    out = []
    try:
        parsed = feedparser.parse(feed["url"], request_headers=HEADERS)
    except Exception as e:
        print("Не удалось прочитать ленту", feed["url"], e)
        return out
    
    language = feed.get("language", "ru")
    
    for entry in parsed.entries[:10]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("summary") or "")[:220]
        
        # Проверяем релевантность
        if not is_relevant(title, summary, language):
            continue
        
        # Пытаемся найти картинку
        photo = None
        # Сначала пробуем взять из entry
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('url'):
                    photo = {
                        "url": media['url'],
                        "credit": feed["tag"],
                        "creditUrl": entry.get("link", ""),
                    }
                    break
        
        # Если нет — через Unsplash
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
# 7. ПАРСИНГ КАЗИНФОРМА
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
        print("Не удалось прочитать страницу Казинформа", feed["url"], e)
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
            print("Не удалось прочитать статью Казинформа", url, e)
            continue

        title = _meta_tag(article_html, "og:title")
        if not title:
            continue
        summary = _meta_tag(article_html, "og:description")[:220]
        image_url = _meta_tag(article_html, "og:image")
        published = _meta_tag(article_html, "article:published_time")

        # Проверяем релевантность
        if not is_relevant(title, summary, "ru"):
            continue

        photo = None
        if image_url and "plug.png" not in image_url:
            photo = {"url": image_url, "credit": "Казинформ", "creditUrl": url}
        else:
            photo = pick_photo("kazakhstan logistics transport")

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
# 8. СБОР ВСЕХ НОВОСТЕЙ
# ============================================================
def collect():
    items = []
    # Сначала собираем русскоязычные источники
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
            items.append(it)
            if len(items) >= MAX_ITEMS:
                break
    
    # Если мало новостей, пробуем англоязычные источники
    if len(items) < MAX_ITEMS:
        for feed in FEEDS:
            if feed.get("language") != "en":
                continue
            if len(items) >= MAX_ITEMS:
                break
            feed_type = feed.get("type", "rss")
            if feed_type == "kazinform":
                new_items = collect_from_kazinform(feed)
            else:
                new_items = collect_from_rss(feed)
            cap = feed.get("cap", MAX_ITEMS)
            for it in new_items[:cap]:
                items.append(it)
                if len(items) >= MAX_ITEMS:
                    break
    
    return items[:MAX_ITEMS]


# ============================================================
# 9. MAIN
# ============================================================
def main():
    items = collect()
    
    # Если новостей нет — используем демо
    is_demo = len(items) == 0
    
    data = {
        "isDemo": is_demo,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Записано: {OUT_PATH} -> карточек: {len(items)}")
    if is_demo:
        print("ВНИМАНИЕ: Новостей не найдено! Используются демо-данные.")


if __name__ == "__main__":
    main()
