"""
Обновляет data/news.json — логистические новости.
Картинки: сначала из статьи (с фильтром), потом Unsplash.
Для каждого источника свои правила.
"""
import html
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
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
    "коридор", "экспорт", "импорт", "фрахт", "автоперевоз",
]


def is_logistics(text):
    text = text.lower()
    return any(w in text for w in LOGISTICS_WORDS)


def is_central_asia(text):
    text = text.lower()
    return any(c in text for c in CENTRAL_ASIA)


def translate_text(text, target_lang='ru'):
    if not text or len(text.strip()) < 3:
        return text
    try:
        cyrillic = sum(1 for c in text if 'а' <= c <= 'я' or 'ё' == c)
        if cyrillic > len(text) * 0.3:
            return text
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": target_lang,
            "dt": "t",
            "q": text[:500]
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


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ============================================================
# 3. ПОИСК КАРТИНКИ В СТАТЬЕ (УЛУЧШЕННЫЙ)
# ============================================================
def is_bad_image(img_url, img_alt=""):
    """Проверяет, является ли картинка аватаром, логотипом, иконкой или рекламой"""
    img_lower = img_url.lower()
    alt_lower = img_alt.lower() if img_alt else ""
    
    bad_patterns = [
        "avatar", "profile", "user", "author", "writer", "contributor",
        "logo", "brand", "icon", "favicon", "sprite", "badge",
        "gravatar", "profil", "author-photo", "headshot",
        "ad", "ads", "banner", "sponsor", "promo",
        "placeholder", "plug.png", "pixel", "transparent",
        "1x1", "blank", "no-image", "noimage",
    ]
    
    # Проверяем URL и alt
    for pattern in bad_patterns:
        if pattern in img_lower or pattern in alt_lower:
            return True
    
    # Проверяем расширения
    if img_lower.endswith(('.ico', '.svg')):
        return True
    
    # Проверяем размер (если есть в URL)
    size_match = re.search(r'[=/](\d+)x(\d+)[=/]', img_lower)
    if size_match:
        w = int(size_match.group(1))
        h = int(size_match.group(2))
        if w < 100 or h < 100:
            return True
    
    return False


def extract_image_from_article(url, feed_tag=""):
    """Загружает статью и ищет в ней картинку"""
    try:
        r = requests.get(url, timeout=15, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        return None
    
    # Собираем все потенциальные картинки
    candidates = []
    
    # 1. og:image
    og_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    if og_match:
        candidates.append(('og:image', og_match.group(1)))
    
    # 2. twitter:image
    tw_match = re.search(r'<meta\s+name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    if tw_match:
        candidates.append(('twitter:image', tw_match.group(1)))
    
    # 3. Все img теги
    for img_tag in re.findall(r'<img[^>]*>', html_content, re.IGNORECASE):
        src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
        if src_match:
            img_url = src_match.group(1)
            img_alt = alt_match.group(1) if alt_match else ""
            # Проверяем размер
            width_match = re.search(r'width=["\'](\d+)["\']', img_tag, re.IGNORECASE)
            height_match = re.search(r'height=["\'](\d+)["\']', img_tag, re.IGNORECASE)
            width = int(width_match.group(1)) if width_match else None
            height = int(height_match.group(1)) if height_match else None
            
            candidates.append(('img', img_url, img_alt, width, height))
    
    # Фильтруем кандидатов
    for candidate in candidates:
        if candidate[0] == 'og:image' or candidate[0] == 'twitter:image':
            img_url = candidate[1]
            if not is_bad_image(img_url):
                # Делаем абсолютный URL
                if img_url.startswith('/'):
                    parsed = urlparse(url)
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    img_url = urljoin(base, img_url)
                return {"url": img_url, "credit": None, "creditUrl": None}
        else:
            img_url, img_alt, width, height = candidate[1], candidate[2], candidate[3], candidate[4]
            
            # Пропускаем маленькие картинки
            if width and width < 200:
                continue
            if height and height < 200:
                continue
            
            if not is_bad_image(img_url, img_alt):
                if img_url.startswith('/'):
                    parsed = urlparse(url)
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    img_url = urljoin(base, img_url)
                if img_url.startswith('http') and not img_url.startswith('data:'):
                    return {"url": img_url, "credit": None, "creditUrl": None}
    
    return None


# ============================================================
# 4. СПЕЦИАЛЬНЫЕ ПРАВИЛА ДЛЯ ИСТОЧНИКОВ
# ============================================================
def get_photo_for_source(url, feed_tag, title="", summary="", entry=None):
    """Ищет картинку с учетом особенностей источника"""
    
    # Для The Loadstar — часто avatar, лучше сразу искать в статье
    if 'theloadstar' in url.lower():
        # Пробуем найти картинку в статье
        photo = extract_image_from_article(url, feed_tag)
        if photo:
            return photo
        # Если нет — Unsplash
        return pick_photo_from_unsplash(title, summary)
    
    # Для SupplyChainDive — похожая ситуация
    if 'supplychaindive' in url.lower():
        photo = extract_image_from_article(url, feed_tag)
        if photo:
            return photo
        return pick_photo_from_unsplash(title, summary)
    
    # Для RailFreight — обычно есть media:content
    if entry and hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            img_url = media.get('url', '')
            if img_url and not is_bad_image(img_url):
                return {"url": img_url, "credit": feed_tag, "creditUrl": url}
    
    # Для остальных — стандартный поиск
    return get_photo_standard(url, feed_tag, title, summary, entry)


def get_photo_standard(url, feed_tag, title="", summary="", entry=None):
    """Стандартный гибридный поиск"""
    
    # 1. RSS media
    if entry and hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            img_url = media.get('url', '')
            if img_url and not is_bad_image(img_url):
                return {"url": img_url, "credit": feed_tag, "creditUrl": url}
    
    if entry and hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        for thumb in entry.media_thumbnail:
            img_url = thumb.get('url', '')
            if img_url and not is_bad_image(img_url):
                return {"url": img_url, "credit": feed_tag, "creditUrl": url}
    
    if entry and hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            img_url = enc.get('href', '')
            if img_url and enc.get('type', '').startswith('image/'):
                if not is_bad_image(img_url):
                    return {"url": img_url, "credit": feed_tag, "creditUrl": url}
    
    # 2. Из статьи
    if url:
        photo = extract_image_from_article(url, feed_tag)
        if photo:
            return photo
    
    # 3. Unsplash
    if title:
        return pick_photo_from_unsplash(title, summary)
    
    return None


# ============================================================
# 5. UNSPLASH
# ============================================================
def pick_photo_from_unsplash(title, summary):
    """Ищет картинку в Unsplash по заголовку"""
    if not UNSPLASH_KEY:
        return None
    
    clean_title = re.sub(r'[^\w\s]', ' ', title)
    words = clean_title.split()[:4]
    search_query = ' '.join(words) if len(words) >= 2 else "logistics transport"
    
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": search_query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if results:
            photo = results[0]
            return {
                "url": photo["urls"]["regular"],
                "credit": photo["user"]["name"],
                "creditUrl": photo["user"]["links"]["html"],
            }
    except Exception as e:
        pass
    
    return None


# ============================================================
# 6. ИСТОЧНИКИ
# ============================================================
FEEDS = [
    {"url": "https://www.inform.kz/tag/logistika_t11100", "tag": "Казинформ", "type": "kazinform", "cap": 4},
    {"url": "https://www.inform.kz/tag/transport_t11012", "tag": "Казинформ", "type": "kazinform", "cap": 2},
    {"url": "https://kun.uz/ru/news/feed", "tag": "Kun.uz", "type": "rss", "cap": 2},
    {"url": "https://24.kg/feed/", "tag": "24.kg", "type": "rss", "cap": 2},
    {"url": "https://asiaplustj.info/ru/rss", "tag": "Азия-Плюс", "type": "rss", "cap": 2},
    {"url": "https://turkmenportal.com/rss", "tag": "Туркменпортал", "type": "rss", "cap": 2},
    {"url": "https://www.railfreight.com/feed", "tag": "RailFreight", "type": "rss", "cap": 2},
    {"url": "https://theloadstar.com/feed/", "tag": "The Loadstar", "type": "rss", "cap": 2},
    {"url": "https://www.supplychaindive.com/feeds/news/", "tag": "SupplyChainDive", "type": "rss", "cap": 2},
]


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
        
        if not is_logistics(title + " " + summary):
            continue
        
        title_ru = translate_text(title)
        summary_ru = translate_text(summary)
        ca_score = 2 if is_central_asia(title + " " + summary) else 0
        
        link = entry.get("link", "")
        
        # Ищем картинку с учетом источника
        photo = get_photo_for_source(link, feed["tag"], title, summary, entry)
        
        out.append({
            "topic": feed["tag"],
            "title": title_ru,
            "summary": summary_ru or "Подробности — по ссылке на источник.",
            "sourceUrl": link,
            "publishedAt": entry.get("published", ""),
            "photo": photo,
            "_ca_score": ca_score,
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

        ca_score = 2 if is_central_asia(title + " " + summary) else 1

        photo = None
        if image_url and "plug.png" not in image_url and not is_bad_image(image_url):
            photo = {"url": image_url, "credit": "Казинформ", "creditUrl": url}
        else:
            photo = get_photo_for_source(url, feed["tag"], title, summary)

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
    
    items.sort(key=lambda x: x.get("_ca_score", 0), reverse=True)
    
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
    
    for i, item in enumerate(items):
        has_photo = "✅" if item.get("photo") else "❌"
        source = item.get("photo", {}).get("credit", "unsplash") if item.get("photo") else "нет"
        print(f"{i+1}. {has_photo} [{source}] {item['title'][:50]}...")


if __name__ == "__main__":
    main()
