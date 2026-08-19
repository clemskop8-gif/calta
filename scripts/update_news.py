"""
Обновляет data/news.json — новости ТОЛЬКО с inform.kz (Казинформ).
Картинки берутся из самих статей.
"""
import html
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import requests

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
MAX_ITEMS = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ============================================================
# 1. ТОЛЬКО ЭТИ СТРАНЫ (для фильтра)
# ============================================================
CENTRAL_ASIA = [
    "казахстан", "қазақстан", "kz",
    "узбекистан", "o'zbekiston", "uzbekistan", "uz",
    "кыргызстан", "kyrgyzstan", "kg",
    "таджикистан", "tojikiston", "tajikistan", "tj",
    "туркменистан", "turkmenistan", "tm",
    "центральная азия", "средняя азия",
    "астана", "astana", "алматы", "almaty",
    "ташкент", "tashkent", "бишкек", "bishkek",
    "душанбе", "dushanbe", "ашхабад", "ashgabat",
]

# ============================================================
# 2. ЛОГИСТИЧЕСКИЕ КЛЮЧЕВЫЕ СЛОВА
# ============================================================
LOGISTICS_WORDS = [
    "логист", "груз", "перевозк", "транспорт", "порт",
    "контейнер", "таможен", "склад", "жд", "железнодорож",
    "коридор", "экспорт", "импорт", "фрахт", "автоперевоз",
    "транзит", "терминал", "вагон", "локомотив", "магистраль",
    "логистик", "перевалк", "хранени", "дистрибуци",
    "транспортн", "грузовой", "инфраструктур", "международн",
]

# ============================================================
# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_relevant(title, summary):
    """Проверяет, что новость о логистике в странах ЦА"""
    text = (title + " " + summary).lower()
    
    # Должна быть хотя бы одна страна ЦА
    has_country = any(c in text for c in CENTRAL_ASIA)
    
    # И хотя бы одно логистическое слово
    has_logistics = any(w in text for w in LOGISTICS_WORDS)
    
    return has_country and has_logistics

def _meta_tag(html_text, prop):
    """Достаёт content из meta тега"""
    for pattern in (
        r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\']',
    ):
        m = re.search(pattern, html_text, re.IGNORECASE)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""

# ============================================================
# 4. ПАРСИНГ КАЗИНФОРМА
# ============================================================
# Регулярка для ссылок на статьи
KAZINFORM_ARTICLE_RE = re.compile(
    r'href="(https://www\.inform\.kz/ru/[a-z0-9\-]+-[a-f0-9]{8})"'
)

def collect_from_kazinform():
    """Парсит новости с inform.kz"""
    out = []
    
    # Страница с тегом "Логистика"
    url = "https://www.inform.kz/tag/logistika_t11100"
    
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"Ошибка при загрузке страницы Казинформа: {e}")
        return out
    
    # Находим все ссылки на статьи
    seen = set()
    urls = []
    for m in KAZINFORM_ARTICLE_RE.finditer(html_content):
        u = m.group(1)
        if u not in seen:
            seen.add(u)
            urls.append(u)
    
    print(f"Найдено ссылок на статьи: {len(urls)}")
    
    # Парсим каждую статью
    for article_url in urls[:15]:  # Берем до 15 статей
        try:
            ar = requests.get(article_url, timeout=20, headers=HEADERS)
            ar.raise_for_status()
            article_html = ar.text
        except Exception as e:
            print(f"Ошибка при загрузке статьи {article_url}: {e}")
            continue
        
        # Извлекаем метаданные
        title = _meta_tag(article_html, "og:title")
        if not title:
            continue
        
        summary = _meta_tag(article_html, "og:description")[:300]
        image_url = _meta_tag(article_html, "og:image")
        published = _meta_tag(article_html, "article:published_time")
        
        # Проверяем релевантность
        if not is_relevant(title, summary):
            print(f"  Пропущено (не релевантно): {title[:50]}...")
            continue
        
        # Формируем картинку
        photo = None
        if image_url and "plug.png" not in image_url.lower():
            photo = {
                "url": image_url,
                "credit": "Казинформ",
                "creditUrl": article_url,
            }
        else:
            # Пробуем найти картинку в статье
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', article_html)
            if img_match:
                img_url = img_match.group(1)
                if not img_url.startswith('http'):
                    img_url = urljoin("https://www.inform.kz", img_url)
                if "plug.png" not in img_url.lower():
                    photo = {
                        "url": img_url,
                        "credit": "Казинформ",
                        "creditUrl": article_url,
                    }
        
        # Если есть картинка — добавляем новость
        if photo:
            out.append({
                "topic": "Казинформ",
                "title": title,
                "summary": summary or "Подробности — по ссылке на источник.",
                "sourceUrl": article_url,
                "publishedAt": published,
                "photo": photo,
            })
            print(f"  ✅ Добавлено: {title[:50]}...")
        else:
            print(f"  ❌ Пропущено (нет картинки): {title[:50]}...")
        
        # Останавливаемся, если набрали достаточно
        if len(out) >= MAX_ITEMS:
            break
    
    return out[:MAX_ITEMS]

# ============================================================
# 5. MAIN
# ============================================================
def main():
    print("Начинаем парсинг Казинформа...")
    items = collect_from_kazinform()
    
    data = {
        "isDemo": len(items) == 0,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Записано: {OUT_PATH} -> карточек: {len(items)}")
    
    if len(items) == 0:
        print("⚠️ ВНИМАНИЕ: Новостей не найдено!")

if __name__ == "__main__":
    main()
