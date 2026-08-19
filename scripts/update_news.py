"""
Обновляет data/news.json карточками новостей строго по теме логистики.

Источники — специализированные логистические RSS-ленты (не общие
новостные, чтобы не попадала политика/спорт и т.п.) плюс прямой парсинг
страницы тега «Логистика» на Казинформе (inform.kz) — без посредников
вроде сторонних RSS-генераторов: скрипт сам ходит на inform.kz и читает
HTML. При желании поменяйте/добавьте свои источники в FEEDS ниже.

Дополнительно каждая новость (кроме источников с skip_filter) проверяется
функцией is_relevant() по списку ключевых слов LOGISTICS_KEYWORDS — даже
если в ленте случайно окажется нерелевантный материал, он будет отброшен.

Фото: Unsplash API, бесплатный тариф (до 50 запросов/час), используется
только когда у источника нет своей картинки (Казинформ обычно даёт свою).
Ключ берётся из переменной окружения UNSPLASH_ACCESS_KEY (GitHub Secrets),
в коде не хранится. Если не задан/запрос не удался — photo: null,
сайт покажет плейсхолдер вместо фото.
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

# Некоторые сайты (в т.ч. inform.kz) не любят запросы без "браузерного"
# User-Agent — с ним запрос выглядит как обычный визит через браузер.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Специализированные логистические источники.
# type: "rss" (по умолчанию) или "kazinform" (прямой парсинг inform.kz).
# skip_filter: True — не прогонять через LOGISTICS_KEYWORDS (источник и так
# уже отфильтрован по теме — например это официальный тег «Логистика» на
# Казинформе, доп. фильтр по словам мог бы ошибочно отбросить материал,
# который не содержит ключевых слов дословно).
FEEDS = [
    {
        "url": "https://www.inform.kz/tag/logistika_t11100",
        "tag": "Казинформ",
        "query": "kazakhstan logistics transport",
        "type": "kazinform",
        "skip_filter": True,
        "cap": 6,  # столько максимум карточек берём из этого источника
    },
    {"url": "https://www.railfreight.com/feed", "tag": "Логистика", "query": "cargo logistics shipping", "cap": 2},
    {"url": "https://theloadstar.com/feed/", "tag": "Логистика", "query": "freight shipping port", "cap": 2},
    {"url": "https://www.supplychaindive.com/feeds/news/", "tag": "Логистика", "query": "supply chain freight", "cap": 2},
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


def strip_html(text):
    """Убирает HTML-теги (<p>, <br />, ссылки и т.п.) из текста RSS-описания
    и разворачивает HTML-сущности (&amp; -> & и т.д.)."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def collect_from_rss(feed):
    out = []
    try:
        parsed = feedparser.parse(feed["url"], request_headers=HEADERS)
    except Exception as e:
        print("Не удалось прочитать ленту", feed["url"], e)
        return out
    for entry in parsed.entries[:8]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("summary") or "")[:220]

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


# Ссылки на статьи в списке тега всегда вида .../ru/<слаг>-<8-символьный хэш>
KAZINFORM_ARTICLE_RE = re.compile(
    r'href="(https://www\.inform\.kz/ru/[a-z0-9\-]+-[a-f0-9]{8})"'
)


def _meta_tag(html_text, prop):
    """Достаёт content нужного <meta property="..."> / <meta name="...">,
    независимо от порядка атрибутов внутри тега."""
    for pattern in (
        r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\']',
    ):
        m = re.search(pattern, html_text, re.IGNORECASE)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def collect_from_kazinform(feed):
    """Прямой парсинг inform.kz: сначала список статей со страницы тега,
    затем у каждой статьи читаются её собственные <meta> og:title/
    og:description/og:image/article:published_time. Никаких сторонних
    сервисов — только requests + встроенный re."""
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
    urls = urls[:8]

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

        if not feed.get("skip_filter") and not is_relevant(title, summary):
            continue

        photo = None
        if image_url and "plug.png" not in image_url:
            photo = {"url": image_url, "credit": feed["tag"], "creditUrl": url}
        else:
            photo = pick_photo(feed["query"])

        out.append({
            "topic": feed["tag"],
            "title": title,
            "summary": summary or "Подробности — по ссылке на источник.",
            "sourceUrl": url,
            "publishedAt": published,
            "photo": photo,
        })
    return out


def collect():
    items = []
    for feed in FEEDS:
        if len(items) >= MAX_ITEMS:
            break
        feed_type = feed.get("type", "rss")
        new_items = collect_from_kazinform(feed) if feed_type == "kazinform" else collect_from_rss(feed)
        cap = feed.get("cap", MAX_ITEMS)  # сколько максимум взять именно из этого источника
        for it in new_items[:cap]:
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
