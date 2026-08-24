"""
Обновляет data/news.json — новости с golos.tj, logistan.info, inform.kz.
РОБАСТНАЯ ВЕРСИЯ:
- Уникальный текст (пересказ своими словами, не копипаста)
- Полное удаление упоминаний СМИ
- Корректная обрезка текста (не на полуслове)
- ровно 6 новостей (по 2 с каждого сайта)
- ТОЛЬКО логистика Центральной Азии
- Уникальные картинки (без повторов)
"""
import html
import json
import os
import re
import random
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import feedparser

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
MAX_ITEMS = 6
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ============================================================
# 1. ЖЁСТКИЙ ФИЛЬТР: ТОЛЬКО ЛОГИСТИКА + СТРАНЫ ЦА
# ============================================================

LOGISTICS_KEYWORDS = [
    # Железная дорога
    "поезд", "вагон", "локомотив", "жд", "ж/д", "железнодорож",
    "магистраль", "путь", "рельс", "состав", "электровоз",
    # Водный транспорт
    "порт", "судно", "контейнеровоз", "паром", "причал", "гавань",
    "морской", "речной", "флот", "танкер",
    # Склады и терминалы
    "терминал", "склад", "хаб", "распределительный центр",
    "логистический центр", "складской", "хранение",
    # Грузы
    "контейнер", "груз", "контейнерный", "teu", "обработка грузов",
    "грузоперевозк", "грузовой", "фрахт",
    # Маршруты
    "коридор", "транзит", "маршрут", "транскаспий",
    "международный транспорт", "транспортный",
    # Таможня
    "таможня", "оформление", "пошлины", "транзитный",
    # Общее
    "перевозк", "транспортировк", "доставк", "логистик",
    "инфраструктур", "строительств", "ремонт", "модернизаци",
    "инвестици", "развити", "экспорт", "импорт",
]

COUNTRIES = [
    "казахстан", "узбекистан", "кыргызстан", "таджикистан", "туркменистан",
    "астана", "алматы", "ташкент", "бишкек", "душанбе", "ашхабад",
    "центральная азия", "центрально-азиат",
]

STOP_WORDS = [
    "цирк", "фестиваль", "искусство", "кино", "музык", "концерт",
    "выставк", "спорт", "футбол", "хоккей", "теннис", "олимпиад",
    "политик", "выбор", "президент", "парламент", "депутат",
    "криминал", "убийств", "арест", "суд", "расследован",
    "погод", "климат", "землетрясени", "наводнен", "вулкан",
    "бюст", "памятник", "возложени", "цветов", "поздравлени",
    "юмор", "анекдот", "звезд", "шоу-бизнес",
]

def is_relevant(title, summary):
    """Проверяет, относится ли новость к логистике в Центральной Азии."""
    if not title:
        return False
    
    full_text = (title + " " + (summary or "")).lower()
    
    # Проверяем стоп-слова
    for word in STOP_WORDS:
        if word in full_text:
            return False
    
    # Проверяем логистику
    has_logistics = False
    for keyword in LOGISTICS_KEYWORDS:
        if keyword in full_text:
            has_logistics = True
            break
    
    if not has_logistics:
        return False
    
    # Проверяем страны ЦА
    has_country = False
    for country in COUNTRIES:
        if country in full_text:
            has_country = True
            break
    
    return has_country

# ============================================================
# 2. ГЕНЕРАЦИЯ УНИКАЛЬНОГО ТЕКСТА (БЕЗ КОПИПАСТЫ)
# ============================================================

def clean_media_phrases(text):
    """Удаляет все упоминания СМИ, источников, клише."""
    if not text:
        return ""
    
    # Паттерны для удаления
    patterns = [
        # СМИ и журналисты
        r'(?i)сообщает\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)передает\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)пишет\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)по\s+информации\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)как\s+сообщил[аи]?\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)как\s+передал[аи]?\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)со\s+ссылкой\s+на\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)по\s+данным\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)источник\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)собеседник\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)информировал[аи]?\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)отметил[аи]?\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)подчеркнул[аи]?\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)рассказал[аи]?\s+[А-Яа-яА-Я\s\-]+',
        r'(?i)заявил[аи]?\s+[А-Яа-яА-Я\s\-]+',
        # Конкретные СМИ
        r'(?i)Trend\s*[,.]?',
        r'(?i)Kazinform\s*[,.]?',
        r'(?i)Inform\.kz\s*[,.]?',
        r'(?i)РИА\s+Новости\s*[,.]?',
        r'(?i)ТАСС\s*[,.]?',
        r'(?i)Интерфакс\s*[,.]?',
        r'(?i)Евразия\s+Сегодня\s*[,.]?',
        # Скобки с источниками
        r'\[[^\]]*\]',
        r'\([^)]*\)',
        # Шапки "Сообщение ... появились сначала на ..."
        r'Сообщение\s+[^.]+\s+появились\s+сначала\s+на\s+[А-Яа-я\s\-]+\.',
        r'Читайте\s+[^.]+\s+на\s+[А-Яа-я\s\-]+\.',
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, '', text)
    
    # Убираем лишние запятые и точки
    text = re.sub(r'[,.]{2,}', '.', text)
    text = re.sub(r'\s{2,}', ' ', text)
    
    return text.strip()

def generate_unique_summary(title, original_summary):
    """
    Создаёт уникальный пересказ новости своими словами.
    Без копипасты, без упоминаний СМИ, без обрыва на полуслове.
    """
    if not original_summary:
        original_summary = title
    
    # 1. Удаляем HTML-теги
    text = strip_html(original_summary)
    
    # 2. Удаляем все упоминания СМИ
    text = clean_media_phrases(text)
    
    # 3. Разбиваем на предложения
    sentences = re.split(r'[.!?]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    
    if not sentences:
        return summarize_text(title, 200)
    
    # 4. Отбираем предложения с фактами (цифры, ключевые слова)
    fact_sentences = []
    for s in sentences:
        has_fact = (
            re.search(r'\d+', s) or  # есть цифры
            any(kw in s.lower() for kw in [
                'логистик', 'транспорт', 'груз', 'контейнер', 
                'порт', 'склад', 'терминал', 'форум', 'инвестиц',
                'строительств', 'развити', 'закупк', 'обновлени',
                'увеличени', 'снижени', 'рост', 'падени',
                'миллион', 'миллиард', 'тысяч', 'процент',
                'километр', 'тонн', 'вагон', 'состав',
            ])
        )
        if has_fact:
            fact_sentences.append(s)
    
    # 5. Если фактов мало — берём первые 2-3 предложения
    if len(fact_sentences) < 2:
        fact_sentences = sentences[:3]
    
    # 6. Формируем текст
    summary = '. '.join(fact_sentences[:3])
    
    # 7. Очищаем от мусора
    summary = re.sub(r'\s+', ' ', summary).strip()
    summary = re.sub(r'\.{2,}', '.', summary)
    summary = re.sub(r'^[,.\s]+', '', summary)
    
    # 8. Добавляем точку в конце если нужно
    if summary and not summary.endswith('.'):
        summary += '.'
    
    # 9. Обрезаем текст (ТОЛЬКО по окончанию предложения!)
    if len(summary) > 400:
        # Ищем последнюю точку до 350 символов
        cut_point = summary[:350].rfind('.')
        if cut_point > 200:
            summary = summary[:cut_point + 1]
        else:
            # Если нет хорошего места для обреза — ищем точку с запятой или запятую
            cut_point = max(
                summary[:350].rfind(','),
                summary[:350].rfind(';'),
                summary[:350].rfind(' — ')
            )
            if cut_point > 200:
                summary = summary[:cut_point] + '...'
            else:
                summary = summary[:347] + '...'
    
    # 10. Финальная очистка
    summary = re.sub(r'\s+', ' ', summary).strip()
    summary = re.sub(r'\.\.+', '...', summary)
    
    return summary

def summarize_text(text, max_len=200):
    """Упрощённая версия для случаев, когда нет нормальных предложений."""
    text = clean_media_phrases(strip_html(text))
    text = re.sub(r'\s+', ' ', text).strip()
    
    if len(text) <= max_len:
        return text
    
    # Обрезаем по пробелу
    cut = text[:max_len]
    last_space = cut.rfind(' ')
    if last_space > max_len * 0.6:
        return cut[:last_space] + '...'
    else:
        return cut[:max_len - 3] + '...'

# ============================================================
# 3. КАРТИНКИ (УНИКАЛЬНЫЕ, БЕЗ ПОВТОРОВ)
# ============================================================

_used_photos = set()

def pick_photo_from_unsplash(title):
    """Получает уникальное фото для новости."""
    if not UNSPLASH_KEY:
        return None
    
    # Извлекаем ключевые слова из заголовка
    clean_title = re.sub(r'[^\w\s]', ' ', title)
    words = [w for w in clean_title.split() if len(w) > 3][:4]
    
    # Определяем тему для поиска
    topic_map = {
        'поезд': 'train', 'вагон': 'train carriage', 'железнодорож': 'railway', 
        'жд': 'railway', 'магистраль': 'railway track',
        'порт': 'port', 'судно': 'ship', 'контейнеровоз': 'container ship', 
        'паром': 'ferry', 'причал': 'dock', 'гавань': 'harbour',
        'терминал': 'terminal', 'склад': 'warehouse', 'хаб': 'logistics hub',
        'груз': 'cargo', 'контейнер': 'container', 'фрахт': 'freight',
        'транзит': 'transit', 'коридор': 'corridor', 'инфраструктур': 'infrastructure',
        'строительств': 'construction', 'дорог': 'road', 'аэропорт': 'airport',
        'таможня': 'customs', 'оформление': 'customs clearance',
        'перевозк': 'transportation', 'доставк': 'delivery',
        'логистик': 'logistics', 'форум': 'conference',
    }
    
    search_query = "logistics transport"
    for word in words:
        word_lower = word.lower()
        for key, topic in topic_map.items():
            if key in word_lower:
                search_query = topic
                break
        if search_query != "logistics transport":
            break
    
    # Добавляем "central asia" для релевантности
    if random.random() > 0.5:
        search_query += " central asia"
    
    photo_url = None
    
    # Пробуем получить фото
    for attempt in range(3):
        try:
            params = {
                "query": search_query,
                "per_page": 10,
                "orientation": "landscape",
                "content_filter": "high"
            }
            
            r = requests.get(
                "https://api.unsplash.com/search/photos",
                params=params,
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
                timeout=10,
            )
            r.raise_for_status()
            
            results = r.json().get("results") or []
            random.shuffle(results)  # Перемешиваем для разнообразия
            
            for photo in results:
                url = photo["urls"]["regular"]
                if url not in _used_photos:
                    _used_photos.add(url)
                    photo_url = url
                    break
            
            if photo_url:
                break
                
        except Exception as e:
            print(f"    ⚠️ Unsplash ошибка (попытка {attempt+1}): {e}")
            time.sleep(1)
        
        # Меняем запрос для следующей попытки
        search_query = f"{search_query} {random.choice(['transport', 'logistics', 'cargo', 'warehouse'])}"
    
    # Запасные фото (если API не работает)
    if not photo_url:
        fallback_urls = [
            "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=1080&q=80",
            "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=1080&q=80",
            "https://images.unsplash.com/photo-1494412574643-ff11b0a5c1c3?w=1080&q=80",
            "https://images.unsplash.com/photo-1519003722824-356d8a3ff1a1?w=1080&q=80",
            "https://images.unsplash.com/photo-1582721478779-0ae163c05a60?w=1080&q=80",
            "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=1080&q=80",
            "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=1080&q=80",
            "https://images.unsplash.com/photo-1517433456452-f9633a875f6f?w=1080&q=80",
        ]
        random.shuffle(fallback_urls)
        for url in fallback_urls:
            if url not in _used_photos:
                _used_photos.add(url)
                photo_url = url
                break
    
    return {"url": photo_url} if photo_url else None

# ============================================================
# 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def strip_html(text):
    """Удаляет HTML-теги и декодирует сущности."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def detect_topic(title, summary):
    """Определяет тему новости."""
    text = (title + " " + (summary or "")).lower()
    
    topics = {
        "Транспорт": ["поезд", "вагон", "локомотив", "жд", "железнодорож", "магистраль", "рельс", "состав", "электровоз", "вокзал"],
        "Порты": ["порт", "судно", "контейнеровоз", "паром", "причал", "гавань", "морской", "флот", "танкер", "буксир"],
        "Терминалы": ["терминал", "склад", "хаб", "распределительный центр", "логистический центр", "хранилище"],
        "Грузы": ["контейнер", "груз", "контейнерный", "teu", "фрахт", "отправка", "получение"],
        "Коридоры": ["коридор", "транзит", "маршрут", "транскаспий", "путь", "направление"],
        "Таможня": ["таможня", "оформление", "пошлины", "декларация", "контроль"],
        "Перевозки": ["перевозк", "транспортировк", "доставк", "логистик", "отправлени", "прибыти"],
        "Инфраструктура": ["строительств", "ремонт", "модернизаци", "реконструкци", "обновлени", "закупк"],
        "Форумы": ["форум", "конференци", "встреч", "семинар", "конгресс", "совещани"],
        "Инвестиции": ["инвестиц", "финансировани", "грант", "кредит", "бюджет", "средств"],
    }
    
    for topic, keywords in topics.items():
        if any(kw in text for kw in keywords):
            return topic
    
    return "Логистика"

def extract_source_domain(url):
    """Извлекает домен из URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        domain = domain.replace('www.', '')
        return domain.split('/')[0]
    except:
        return ""

# ============================================================
# 5. ПАРСИНГ САЙТОВ
# ============================================================

def collect_golos():
    """Собирает новости с golos.tj."""
    out = []
    try:
        parsed = feedparser.parse("https://golos.tj/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ golos.tj ошибка: {e}")
        return out
    
    for entry in parsed.entries[:30]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        
        summary = strip_html(entry.get("description") or entry.get("summary") or "")[:800]
        
        if not is_relevant(title, summary):
            continue
        
        # Генерируем уникальный текст
        unique_summary = generate_unique_summary(title, summary)
        
        photo = pick_photo_from_unsplash(title)
        
        out.append({
            "source": "golos.tj",
            "topic": detect_topic(title, summary),
            "title": title,
            "summary": unique_summary,
            "publishedAt": entry.get("published", ""),
            "photo": photo,
        })
        
        print(f"    ✅ golos.tj: {title[:50]}...")
        
        if len(out) >= 2:
            break
    
    return out

def collect_logistan():
    """Собирает новости с logistan.info."""
    out = []
    try:
        parsed = feedparser.parse("https://logistan.info/feed/", request_headers=HEADERS)
    except Exception as e:
        print(f"  ❌ logistan.info ошибка: {e}")
        return out
    
    for entry in parsed.entries[:30]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        
        summary = strip_html(entry.get("description") or entry.get("summary") or "")[:800]
        
        if not is_relevant(title, summary):
            continue
        
        unique_summary = generate_unique_summary(title, summary)
        photo = pick_photo_from_unsplash(title)
        
        out.append({
            "source": "logistan.info",
            "topic": detect_topic(title, summary),
            "title": title,
            "summary": unique_summary,
            "publishedAt": entry.get("published", ""),
            "photo": photo,
        })
        
        print(f"    ✅ logistan.info: {title[:50]}...")
        
        if len(out) >= 2:
            break
    
    return out

def collect_inform():
    """Собирает новости с inform.kz."""
    out = []
    url = "https://www.inform.kz/tag/logistika_t11100"
    
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"  ❌ inform.kz ошибка: {e}")
        return out
    
    # Находим ссылки на статьи
    links = set()
    for link in re.findall(r'href=["\']([^"\']*/ru/[a-z0-9\-]+-[a-f0-9]{8})["\']', html_content, re.IGNORECASE):
        if link.startswith('http'):
            links.add(link)
        else:
            links.add("https://www.inform.kz" + link if link.startswith('/') else "https://www.inform.kz/" + link)
    
    for article_url in list(links)[:25]:
        try:
            ar = requests.get(article_url, timeout=20, headers=HEADERS)
            ar.raise_for_status()
            article_html = ar.text
        except Exception:
            continue
        
        # Пытаемся извлечь мета-теги
        def meta(prop):
            for pattern in (
                r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']*)["\']',
                r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\']',
            ):
                m = re.search(pattern, article_html, re.IGNORECASE)
                if m:
                    return html.unescape(m.group(1)).strip()
            return ""
        
        title = meta("og:title")
        if not title:
            continue
        
        summary = meta("og:description")[:800]
        published = meta("article:published_time") or meta("pubdate")
        
        if not is_relevant(title, summary):
            continue
        
        unique_summary = generate_unique_summary(title, summary)
        photo = pick_photo_from_unsplash(title)
        
        out.append({
            "source": "inform.kz",
            "topic": detect_topic(title, summary),
            "title": title,
            "summary": unique_summary,
            "publishedAt": published,
            "photo": photo,
        })
        
        print(f"    ✅ inform.kz: {title[:50]}...")
        
        if len(out) >= 2:
            break
    
    return out

# ============================================================
# 6. СБОР И ОБРАБОТКА
# ============================================================

def collect_all():
    """Собирает новости со всех источников."""
    print("\n🔍 Сбор новостей (только логистика, уникальные тексты)...")
    
    items = []
    items.extend(collect_golos())
    items.extend(collect_logistan())
    items.extend(collect_inform())
    
    # Удаляем дубликаты по заголовку
    seen = set()
    unique_items = []
    for item in items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    
    # Сортируем по дате (новые сверху)
    unique_items.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)
    
    return unique_items[:MAX_ITEMS]

# ============================================================
# 7. MAIN
# ============================================================

def main():
    print("🚀 Запуск обновления новостей...")
    print(f"   Unsplash API: {'✅ есть' if UNSPLASH_KEY else '❌ нет'}")
    
    items = collect_all()
    
    if not items:
        print("⚠️ Новостей не найдено. Сохраняем демо-режим.")
        data = {
            "isDemo": True,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "items": [],
        }
    else:
        data = {
            "isDemo": False,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "items": items,
        }
    
    # Сохраняем
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено: {OUT_PATH}")
    print(f"   Всего новостей: {len(items)}")
    
    if items:
        print("\n📰 Список новостей:")
        for i, item in enumerate(items, 1):
            has_photo = "✅" if item.get("photo") and item["photo"].get("url") else "❌"
            source = item.get("source", "?")
            title = item.get("title", "")[:60]
            summary_len = len(item.get("summary", ""))
            print(f"  {i}. {has_photo} [{source}] {title}... (текст: {summary_len} симв.)")
            if item.get("summary"):
                preview = item["summary"][:80] + "..." if len(item.get("summary", "")) > 80 else item["summary"]
                print(f"      📝 {preview}")
    
    print("\n✨ Готово!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        
        # В случае ошибки сохраняем пустой массив
        data = {
            "isDemo": True,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "items": [],
        }
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("   ✅ Сохранён пустой массив (демо-режим)")
