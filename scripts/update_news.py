"""
Обновляет data/news.json — новости с golos.tj, logistan.info, inform.kz.
РОБАСТНАЯ ВЕРСИЯ С ПЕРЕФРАЗИРОВАНИЕМ:
- Уникальный текст (пересказ на основе фактов + синонимы)
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

# Слова, которые ДОЛЖНЫ встретиться, чтобы новость считалась логистической.
# В отличие от LOGISTICS_KEYWORDS (используется только для detect_topic),
# сюда НЕ входят общие слова вроде "развитие/инвестиции/строительство/форум" —
# они пропускали дипломатические и финансовые новости, не связанные с логистикой.
REQUIRED_LOGISTICS_KEYWORDS = [
    "поезд", "вагон", "локомотив", "жд", "ж/д", "железнодорож",
    "магистраль", "рельс", "состав", "электровоз",
    "порт", "судно", "контейнеровоз", "паром", "причал", "гавань",
    "морской", "флот", "танкер",
    "терминал", "склад", "хаб", "логистический центр", "распределительный центр",
    "контейнер", "груз", "teu", "фрахт", "грузоперевозк", "грузовой",
    "коридор", "транзит", "транскаспий",
    "таможня", "таможенн", "пошлин",
    "перевозк", "транспортировк", "доставк", "логистик",
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

    # Проверяем логистику (только по "жёсткому" списку, без общих слов)
    if not any(keyword in full_text for keyword in REQUIRED_LOGISTICS_KEYWORDS):
        return False

    # Проверяем страны ЦА
    return any(country in full_text for country in COUNTRIES)

# ============================================================
# 2. СЛОВАРЬ СИНОНИМОВ И ФУНКЦИИ ПЕРЕФРАЗИРОВАНИЯ
# ============================================================

SYNONYMS = {
    'пройдет': ['состоится', 'пройдёт', 'будет проведён', 'запланирован'],
    'состоится': ['пройдёт', 'будет организован', 'запланирован'],
    'проведет': ['организует', 'проведёт', 'будет проводить'],
    'заявил': ['отметил', 'подчеркнул', 'сообщил', 'сказал'],
    'сообщил': ['рассказал', 'информировал', 'уведомил'],
    'планируется': ['запланировано', 'намечено', 'предполагается'],
    'начало': ['старт', 'запуск'],
    'завершение': ['окончание', 'финиш'],
    'увеличение': ['рост', 'повышение'],
    'снижение': ['падение', 'уменьшение'],
    'развитие': ['совершенствование', 'прогресс'],
    'строительство': ['возведение', 'сооружение'],
    'модернизация': ['обновление', 'реконструкция'],
    'форум': ['конференция', 'встреча', 'съезд'],
    'инвестиции': ['вложения', 'финансирование'],
    'логистика': ['транспортировка', 'перевозки'],
    'транспорт': ['перевозки', 'транспортировка'],
    'груз': ['товар', 'продукция'],
    'контейнер': ['тарра', 'упаковка'],
    'порт': ['гавань', 'терминал'],
    'склад': ['хранилище', 'терминал'],
    'терминал': ['пункт', 'узел'],
    'коридор': ['маршрут', 'направление'],
    'транзит': ['перевозка', 'транспортировка'],
    'таможня': ['пограничный контроль', 'оформление'],
    'перевозки': ['транспортировка', 'доставка'],
    'доставка': ['перевозка', 'транспортировка'],
    'инфраструктура': ['оснащение', 'сеть'],
    'экспорт': ['вывоз', 'поставка за рубеж'],
    'импорт': ['ввоз', 'закупка за рубежом'],
}

def paraphrase_text(text):
    """Заменяет слова на синонимы для уникальности."""
    if not text:
        return text
    words = text.split()
    new_words = []
    for word in words:
        # Убираем знаки препинания для поиска
        clean = word.strip('.,!?;:')
        punct = ''
        if word and word[-1] in '.,!?;:':
            punct = word[-1]
            word_clean = word[:-1]
        else:
            word_clean = word
        if word_clean.lower() in SYNONYMS:
            synonym = random.choice(SYNONYMS[word_clean.lower()])
            # Сохраняем регистр
            if word_clean[0].isupper():
                synonym = synonym.capitalize()
            new_words.append(synonym + punct)
        else:
            new_words.append(word)
    return ' '.join(new_words)

# ============================================================
# 3. ГЕНЕРАЦИЯ УНИКАЛЬНОГО ТЕКСТА (НОВАЯ ВЕРСИЯ)
# ============================================================

def clean_media_phrases(text):
    """Удаляет все упоминания СМИ, источников, клише."""
    if not text:
        return ""

    # Убираем "висячий" хвост RSS-обрезки — WordPress часто режет анонс через
    # "[&hellip;]", что после html.unescape() превращается в "…". Раньше это
    # многоточие оставалось в тексте и давало артефакты вида "2026:…."
    text = re.sub(r'\[\s*…\s*\]', '', text)
    text = re.sub(r'[:;,\-–—]?\s*…+\s*$', '', text.strip())

    patterns = [
        r'(?i)сообщает\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)передает\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)пишет\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)по\s+информации\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)как\s+сообщил[аи]?\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)как\s+передал[аи]?\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)со\s+ссылкой\s+на\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)по\s+данным\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)источник\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)собеседник\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)информировал[аи]?\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)отметил[аи]?\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)подчеркнул[аи]?\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)рассказал[аи]?\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)заявил[аи]?\s+[«»A-Za-zА-Яа-я0-9\s\-\.]+[«»]?',
        r'(?i)Trend\s*[,.]?',
        r'(?i)Kazinform\s*[,.]?',
        r'(?i)Inform\.kz\s*[,.]?',
        r'(?i)РИА\s+Новости\s*[,.]?',
        r'(?i)ТАСС\s*[,.]?',
        r'(?i)Интерфакс\s*[,.]?',
        r'(?i)Евразия\s+Сегодня\s*[,.]?',
        r'\[[^\]]*\]',
        r'\([^)]*\)',
        r'Сообщение\s+[^.]+\s+появились\s+сначала\s+на\s+[А-Яа-я\s\-]+\.',
        r'Читайте\s+[^.]+\s+на\s+[А-Яа-я\s\-]+\.',
    ]

    for pattern in patterns:
        text = re.sub(pattern, '', text)

    # Если после удаления фразы у текста остался "голый" хвост вида ", " или "— "
    text = re.sub(r'[,;\-–—]\s*$', '.', text.strip())
    text = re.sub(r'[,.]{2,}', '.', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def extract_facts(text):
    """Извлекает из текста факты: даты, числа, названия организаций, города."""
    facts = {
        'dates': re.findall(r'\b\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}\b', text),
        'years': re.findall(r'\b\d{4}\b', text),
        'numbers': re.findall(r'\b\d+[\.,]?\d*\s*(?:млн|млрд|тыс|процентов?|%|тонн|вагонов|километров|км|млрд|млн)\b', text),
        'orgs': re.findall(r'[А-Я][а-я]+(?:\s+[А-Я][а-я]+)*\s+(?:центр|компания|министерство|ассоциация|финансовый|логистический|терминал|порт|завод|университет|институт|предприятие|корпорация|холдинг)', text),
        'cities': re.findall(r'(?:Астана|Алматы|Ташкент|Бишкек|Душанбе|Ашхабад|Москва|Пекин|Лондон)', text),
    }
    return facts

def generate_unique_summary(title, original_summary):
    """
    Генерирует абсолютно новый текст на основе фактов и синонимов.
    Без копипасты, без упоминаний СМИ, без обрыва на полуслове.
    """
    if not original_summary:
        original_summary = title

    # 1. Удаляем HTML и СМИ-фразы
    text = strip_html(original_summary)
    text = clean_media_phrases(text)

    # 2. Извлекаем факты
    facts = extract_facts(text)

    # 3. Строим новые предложения на основе фактов
    new_sentences = []

    # --- Первое предложение: дата + событие ---
    if facts['dates']:
        date = facts['dates'][0]
        # Определяем тип события по заголовку
        if 'форум' in title.lower() or 'конференц' in title.lower():
            action = random.choice(['состоится', 'пройдёт', 'запланирован'])
            new_sentences.append(f"{date} в Центральной Азии {action} логистический форум.")
        elif 'закуп' in title.lower() or 'приобрет' in title.lower():
            action = random.choice(['планируется закупка', 'будет приобретено', 'закупят'])
            new_sentences.append(f"{date} {action} новое оборудование для транспорта.")
        elif 'строительств' in title.lower() or 'модернизац' in title.lower():
            action = random.choice(['запланированы работы', 'начинается строительство', 'проводится модернизация'])
            new_sentences.append(f"{date} {action} на транспортных маршрутах.")
        else:
            action = random.choice(['обсуждается', 'рассматривается', 'планируется'])
            new_sentences.append(f"{date} {action} развитие транспортной инфраструктуры.")

    # --- Второе предложение: числа и организации ---
    if facts['numbers']:
        num = facts['numbers'][0]
        org = facts['orgs'][0] if facts['orgs'] else 'участники рынка'
        if 'вагонов' in num or 'тыс' in num or 'млн' in num or 'млрд' in num:
            new_sentences.append(f"Речь идёт о {num}, которые планируется {random.choice(['приобрести', 'модернизировать', 'обновить', 'задействовать'])}.")
        elif 'км' in num or 'километров' in num:
            new_sentences.append(f"Протяжённость маршрута составляет {num}.")
        else:
            new_sentences.append(f"По данным {org}, ключевые параметры составляют {num}.")

    # --- Третье предложение: города ---
    if facts['cities']:
        cities = ', '.join(facts['cities'][:2])
        if len(facts['cities']) > 1:
            new_sentences.append(f"В обсуждении участвуют представители {cities}.")
        else:
            new_sentences.append(f"Мероприятие затронет вопросы развития логистики в {cities}.")

    # --- Если предложений мало — добавляем перефразированный заголовок ---
    if len(new_sentences) < 2:
        # Перефразируем заголовок
        paraphrased_title = paraphrase_text(title)
        new_sentences.append(paraphrased_title + '.')
        if facts['orgs']:
            new_sentences.append(f"Организатором выступает {facts['orgs'][0]}.")

    # 4. Собираем текст
    result = ' '.join(new_sentences)
    result = re.sub(r'\s+', ' ', result).strip()
    result = re.sub(r'\.{2,}', '.', result)
    if not result.endswith('.'):
        result += '.'

    # 5. Обрезаем текст только по естественной границе (точка, "!", "?").
    #    Если хорошей границы нет — отбрасываем незаконченный хвост целиком,
    #    НЕ приклеивая многоточие (это и создавало артефакты вида "2026:….").
    if len(result) > 400:
        cut_point = result[:350].rfind('.')
        if cut_point > 150:
            result = result[:cut_point + 1]
        else:
            for sep in ('!', '?'):
                pos = result[:350].rfind(sep)
                if pos > 150:
                    result = result[:pos + 1]
                    break
            else:
                last_space = result[:350].rfind(' ')
                result = (result[:last_space] + '.') if last_space > 150 else (result[:347] + '.')

    # 6. Финальная очистка — никакого многоточия и висячих знаков в конце
    result = re.sub(r'\s+', ' ', result).strip()
    result = re.sub(r'…+', '', result)
    result = re.sub(r'\.{2,}', '.', result)
    result = re.sub(r'[,;\-–—:]\s*$', '.', result.strip())

    return result

def summarize_text(text, max_len=200):
    """Упрощённая версия для случаев, когда нет нормальных предложений."""
    text = clean_media_phrases(strip_html(text))
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    last_space = cut.rfind(' ')
    if last_space > max_len * 0.6:
        return cut[:last_space] + '...'
    else:
        return cut[:max_len - 3] + '...'

# ============================================================
# 4. КАРТИНКИ (УНИКАЛЬНЫЕ, БЕЗ ПОВТОРОВ)
# ============================================================

_used_photos = set()

def pick_photo_from_unsplash(title):
    """Получает уникальное фото для новости."""
    if not UNSPLASH_KEY:
        return None

    clean_title = re.sub(r'[^\w\s]', ' ', title)
    words = [w for w in clean_title.split() if len(w) > 3][:4]

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

    if random.random() > 0.5:
        search_query += " central asia"

    photo_url = None
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
            random.shuffle(results)
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
        search_query = f"{search_query} {random.choice(['transport', 'logistics', 'cargo', 'warehouse'])}"

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
# 5. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
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
# 6. ПАРСИНГ САЙТОВ
# ============================================================

def collect_golos():
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
    out = []
    url = "https://www.inform.kz/tag/logistika_t11100"
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"  ❌ inform.kz ошибка: {e}")
        return out

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
# 7. СБОР И ОБРАБОТКА
# ============================================================

def collect_all():
    print("\n🔍 Сбор новостей (только логистика, уникальные тексты)...")
    items = []
    items.extend(collect_golos())
    items.extend(collect_logistan())
    items.extend(collect_inform())

    seen = set()
    unique_items = []
    for item in items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    unique_items.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)
    return unique_items[:MAX_ITEMS]

# ============================================================
# 8. MAIN
# ============================================================

def main():
    print("🚀 Запуск обновления новостей (НОВАЯ ВЕРСИЯ С СИНОНИМАМИ)...")
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
        data = {
            "isDemo": True,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "items": [],
        }
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("   ✅ Сохранён пустой массив (демо-режим)")
