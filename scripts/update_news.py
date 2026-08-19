"""
Обновляет data/news.json — новости ТОЛЬКО с inform.kz (Казинформ).
Расширенный поиск ссылок на статьи.
"""
import html
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
MAX_ITEMS = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ============================================================
# 1. ЛОГИСТИЧЕСКИЕ КЛЮЧЕВЫЕ СЛОВА
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
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_logistics(title, summary):
    text = (title + " " + summary).lower()
    return any(w in text for w in LOGISTICS_WORDS)

def _meta_tag(html_text, prop):
    for pattern in (
        r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\']',
    ):
        m = re.search(pattern, html_text, re.IGNORECASE)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""

# ============================================================
# 3. ПАРСИНГ КАЗИНФОРМА — РАСШИРЕННЫЙ ПОИСК ССЫЛОК
# ============================================================
def collect_from_kazinform():
    out = []
    url = "https://www.inform.kz/tag/logistika_t11100"
    
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"Ошибка загрузки страницы: {e}")
        return out
    
    # === РАСШИРЕННЫЙ ПОИСК ССЫЛОК ===
    all_links = set()
    
    # 1. Ищем ссылки в href
    href_links = re.findall(
        r'href=["\']([^"\']*/ru/[a-z0-9\-]+-[a-f0-9]{8})["\']',
        html_content,
        re.IGNORECASE
    )
    for link in href_links:
        if link.startswith('http'):
            all_links.add(link)
        else:
            all_links.add("https://www.inform.kz" + link if link.startswith('/') else "https://www.inform.kz/" + link)
    
    # 2. Ищем ссылки в data-href (если такие есть)
    data_href_links = re.findall(
        r'data-href=["\']([^"\']*ru/[a-z0-9\-]+-[a-f0-9]{8})["\']',
        html_content,
        re.IGNORECASE
    )
    for link in data_href_links:
        if link.startswith('http'):
            all_links.add(link)
        else:
            all_links.add("https://www.inform.kz" + link if link.startswith('/') else "https://www.inform.kz/" + link)
    
    # 3. Ищем прямые ссылки на статьи (без кавычек)
    direct_links = re.findall(
        r'(?:https?://)?(?:www\.)?inform\.kz/ru/[a-z0-9\-]+-[a-f0-9]{8}',
        html_content,
        re.IGNORECASE
    )
    for link in direct_links:
        if not link.startswith('http'):
            link = "https://" + link if not link.startswith('https://') else link
        all_links.add(link)
    
    print(f"Найдено уникальных ссылок: {len(all_links)}")
    
    # Сортируем ссылки (простейший способ — по длине, чтобы короткие шли первыми)
    urls = sorted(list(all_links), key=len)
    
    for article_url in urls[:20]:  # Больше попыток
        try:
            ar = requests.get(article_url, timeout=20, headers=HEADERS)
            ar.raise_for_status()
            article_html = ar.text
        except Exception as e:
            print(f"Ошибка загрузки статьи: {e}")
            continue
        
        title = _meta_tag(article_html, "og:title")
        if not title:
            continue
        
        summary = _meta_tag(article_html, "og:description")[:300]
        image_url = _meta_tag(article_html, "og:image")
        published = _meta_tag(article_html, "article:published_time")
        
        # Проверяем на логистику
        if not is_logistics(title, summary):
            print(f"  ⏭ Пропущено (не логистика): {title[:40]}...")
            continue
        
        # Ищем картинку
        photo = None
        if image_url and "plug.png" not in image_url.lower():
            photo = {
                "url": image_url,
                "credit": "Казинформ",
                "creditUrl": article_url,
            }
        else:
            # Пробуем найти первую картинку в статье
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
        
        # Добавляем, только если есть картинка
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
            print(f"  ❌ Нет картинки: {title[:40]}...")
        
        if len(out) >= MAX_ITEMS:
            break
    
    return out[:MAX_ITEMS]

# ============================================================
# 4. MAIN
# ============================================================
def main():
    print("Парсинг Казинформа (расширенный поиск)...")
    items = collect_from_kazinform()
    
    data = {
        "isDemo": len(items) == 0,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Записано: {OUT_PATH} -> {len(items)} новостей")
    
    if len(items) == 0:
        print("⚠️ ВНИМАНИЕ: Новостей не найдено!")

if __name__ == "__main__":
    main()
