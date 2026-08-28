"""
Обновляет data/news.json — новости с golos.tj, logistan.info, inform.kz.
РОБАСТНАЯ ВЕРСИЯ С ПЕРЕФРАЗИРОВАНИЕМ:
- Уникальный текст (пересказ на основе фактов + синонимы)
- Полное удаление упоминаний СМИ
- Корректная обрезка текста (не на полуслове)
- ровно 6 новостей (по 2 с каждого сайта)
- ТОЛЬКО логистика Центральной Азии
- Уникальные картинки (без повторов)

ИСПРАВЛЕНИЕ (см. is_relevant): golos.tj и logistan.info — профильные
сайты по логистике/новостям Центральной Азии, и их собственные новости
часто НЕ называют страну явно (это их локальный контекст, "Таджикистан"
внутри таджикского сайта никто не пишет). Из-за этого старая версия
фильтра отсеивала почти всё, что приходило с этих двух сайтов, и в
ленте оставались только новости с inform.kz. Теперь для этих двух
источников требование явного упоминания страны снято (используется
implicit_region=True) — достаточно логистического ключевого слова.
Для inform.kz (общее казахстанское агентство, пишет и про мировую
логистику) требование явного упоминания страны ЦА сохранено, чтобы не
тащить нерелевantные новости.
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

# Каждому слову из REQUIRED_LOGISTICS_KEYWORDS требуется граница слова СЛЕВА
# (но не справа — чтобы сохранить ловлю словоформ типа "модернизаци" ->
# "модернизация/модернизации"). Это устраняет ложные срабатывания вида
# "хаб" внутри "Ашхабад" или "порт" внутри "паспорт"/"экспорт"/"импорт".
_REQUIRED_PATTERNS = [re.compile(r'\b' + re.escape(kw)) for kw in REQUIRED_LOGISTICS_KEYWORDS]

def is_relevant(title, summary, implicit_region=False):
    """
    Проверяет, относится ли новость к логистике в Центральной Азии.

    implicit_region=True — используется для источников, которые сами по
    себе на 100% посвящены логистике/новостям Центральной Азии
    (golos.tj, logistan.info). Их собственные новости почти никогда не
    называют страну явно (это их локальный контекст), поэтому для них
    требование явного упоминания страны снимается — достаточно
    логистического ключевого слова + отсутствия стоп-слов.
    """
    if not title:
        return False

    full_text = (title + " " + (summary or "")).lower()

    # Проверяем стоп-слова
    for word in STOP_WORDS:
        if word in full_text:
            return False

    # Проверяем логистику (только по "жёсткому" списку, без общих слов,
    # с границей слова слева — без ложных срабатываний внутри других слов)
    if not any(p.search(full_text) for p in _REQUIRED_PATTERNS):
        return False

    # Для источников, целиком посвящённых логистике ЦА, явного упоминания
    # страны не требуем — иначе почти все их новости отсеиваются.
    if implicit_region:
        return True

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
    # --- расширение словаря для более естественной речи ---
    'увеличился': ['вырос', 'повысился', 'прибавил'],
    'увеличилась': ['выросла', 'повысилась'],
    'снизился': ['упал', 'сократился', 'уменьшился'],
    'снизилась': ['упала', 'сократилась', 'уменьшилась'],
    'составил': ['достиг', 'равнялся'],
    'составила': ['достигла', 'равнялась'],
    'подписан': ['заключён', 'утверждён'],
    'подписано': ['заключено', 'утверждено'],
    'подписали': ['заключили', 'утвердили'],
    'открыт': ['запущен', 'введён в строй'],
    'открыли': ['запустили', 'ввели в эксплуатацию'],
    'запустили': ['открыли', 'ввели в эксплуатацию', 'начали работу'],
    'планируют': ['намерены', 'собираются', 'рассчитывают'],
    'позволит': ['даст возможность', 'обеспечит'],
    'позволит увеличить': ['даст возможность нарастить', 'поможет увеличить'],
    'обеспечит': ['гарантирует', 'позволит'],
    'сократить': ['уменьшить', 'снизить'],
    'сократится': ['уменьшится', 'снизится'],
    'вырастет': ['увеличится', 'повысится'],
    'важный': ['значимый', 'ключевой'],
    'крупный': ['масштабный', 'значительный'],
    'участники': ['стороны', 'представители'],
    'соглашение': ['договорённость', 'договор'],
    'проект': ['инициатива', 'программа'],
    'также': ['кроме того', 'помимо этого', 'вместе с тем'],
    'однако': ['при этом', 'вместе с тем'],
    'поэтому': ['в связи с этим', 'вследствие этого'],
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

# ------------------------------------------------------------
# 2b. ПЕРЕСТРОЙКА СТРУКТУРЫ ПРЕДЛОЖЕНИЯ
# (не только замена слов — меняем порядок частей предложения)
# ------------------------------------------------------------

_CAUSE_CONJ = ('потому что', 'так как', 'поскольку', 'в связи с тем что')

def restructure_sentence(sentence):
    """
    Меняет порядок частей предложения там, где это грамматически
    безопасно, чтобы пересказ не повторял структуру оригинала слово
    в слово, а не только заменял отдельные слова синонимами.
    """
    s = sentence.strip()

    # 1) "Главное, потому что/так как придаточное." -> "Так как придаточное, главное."
    for conj in _CAUSE_CONJ:
        pattern = re.compile(rf'^(.{{15,}}?),\s*{re.escape(conj)}\s+(.{{15,}}?)\.?$', re.IGNORECASE)
        m = pattern.match(s)
        if m and random.random() < 0.6:
            main, sub = m.group(1).strip(), m.group(2).strip()
            sub_cap = sub[0].upper() + sub[1:]
            main_low = main[0].lower() + main[1:] if main[0].isupper() else main
            return f"{sub_cap.rstrip('.')}, {main_low.rstrip('.')}."

    # 2) "Субъект, который/которая/которое сделал X, ..." ->
    #    два самостоятельных предложения: "Субъект ... . Он/она сделал X."
    m = re.match(
        r'^([А-ЯЁ][^,]{2,60}),\s*(котор(?:ый|ая|ое|ые))\s+(.{15,}?)\.?$',
        s
    )
    if m and random.random() < 0.5:
        subject, rel, rest = m.group(1).strip(), m.group(2), m.group(3).strip()
        pronoun = {'который': 'Он', 'которая': 'Она', 'которое': 'Оно', 'которые': 'Они'}.get(rel, 'Это')
        return f"{subject}. {pronoun} {rest.rstrip('.')}."

    # 3) Перестановка обстоятельства времени/места из конца в начало:
    #    "Событие произойдёт в г. Шу 5 ноября." -> "5 ноября в г. Шу произойдёт событие."
    #    Применяем только к коротким предложениям, чтобы не ломать смысл.
    m = re.match(r'^(.{10,80}?)\s+(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)(?:\s+\d{4}\s*года?)?)\.?$', s)
    if m and random.random() < 0.4:
        main, date_part = m.group(1).strip(), m.group(2).strip()
        main_low = main[0].lower() + main[1:] if main[0].isupper() else main
        return f"{date_part} {main_low.rstrip('.')}."

    return s

_CONNECTORS = [
    'При этом', 'Кроме того,', 'Вместе с тем,', 'Также отмечается, что',
    'По имеющимся данным,', 'Помимо этого,',
]

def join_sentences_naturally(sentences):
    """
    Склеивает предложения не простым сложением через точку, а с
    переменными связками между ними — так пересказ читается как
    единый текст, а не как список фактов подряд.
    """
    if not sentences:
        return ''
    if len(sentences) == 1:
        return sentences[0]

    out = [sentences[0]]
    used_connectors = set()
    for s in sentences[1:]:
        available = [c for c in _CONNECTORS if c not in used_connectors] or _CONNECTORS
        connector = random.choice(available)
        used_connectors.add(connector)
        s_low = s[0].lower() + s[1:] if s[0].isupper() and not s.startswith(('Он ', 'Она ', 'Оно ', 'Они ')) else s
        out.append(f"{connector} {s_low}")
    return ' '.join(out)

# ============================================================
# 3. ГЕНЕРАЦИЯ УНИКАЛЬНОГО ТЕКСТА (НОВАЯ ВЕРСИЯ)
# ============================================================

def clean_media_phrases(text):
    """Удаляет все упоминания СМИ, источников, клише."""
    if not text:
        return ""

    # Убираем "висячий" хвост RSS-обрезки — WordPress часто режет анонс через
    # "[&hellip;]", что после html.unescape() превращается в "…".
    text = re.sub(r'\[\s*…\s*\]', '', text)
    text = re.sub(r'[:;,\-–—]?\s*…+\s*$', '', text.strip())

    # 1. СНАЧАЛА убираем футер вида "Сообщение <...> появились сначала на
    #    <Сайт>." — используем ".*$" до конца строки, а НЕ ограниченный
    #    список символов: имя сайта может содержать что угодно (латиницу,
    #    цифры, дефисы), и попытка перечислить допустимые символы либо не
    #    находит конец фразы (сайт "Logistan" не проходил через
    #    [А-Яа-я\s\-]), либо съедается предыдущей "жадной" атрибуцией ниже.
    #    Это ДОЛЖНО выполняться раньше атрибуций (шаг 2), иначе "рассказал
    #    ... Сообщение ... появились сначала на ..." склеивается в одну
    #    жадную цепочку и обрубается на первом непредвиденном символе.
    text = re.sub(r'(?i)сообщение\s.*?появились\s+сначала\s+на\s.*$', '', text).strip()
    text = re.sub(r'(?i)читайте\s.*?\sна\s.*$', '', text).strip()

    # 2. Висячая атрибуция цитаты в конце текста вида "..., — рассказал
    #    почётный железнодорожник Калтай" — ограничена 1–6 словами, чтобы
    #    НЕ захватывать случайно последующий текст, если перед ним нет точки.
    text = re.sub(
        r'\s*,?\s*[—\-–]\s*(рассказал|сказал|сообщил|отметил|подчеркнул|заявил)[аи]?\s+'
        r'(?:[«»A-Za-zА-Яа-я\-]+\s*){1,6}$',
        '.', text.strip()
    )

    # 3. Обычные СМИ-клише в начале/середине фразы — тоже ограничены по
    #    длине (1–5 "слов"), а не безлимитным "+", чтобы не съедать всё
    #    до конца строки, если рядом нет точки/запятой-ограничителя.
    NAME = r'(?:[«»A-Za-zА-Яа-я0-9\-]+\s*){1,5}'
    patterns = [
        rf'(?i)сообщает\s+{NAME}',
        rf'(?i)сообщил[аи]?\s+{NAME}',
        rf'(?i)передает\s+{NAME}',
        rf'(?i)передал[аи]?\s+{NAME}',
        rf'(?i)пишет\s+{NAME}',
        rf'(?i)по\s+информации\s+{NAME}',
        rf'(?i)как\s+сообщил[аи]?\s+{NAME}',
        rf'(?i)как\s+передал[аи]?\s+{NAME}',
        rf'(?i)со\s+ссылкой\s+на\s+{NAME}',
        rf'(?i)по\s+данным\s+{NAME}',
        rf'(?i)источник\s+{NAME}',
        rf'(?i)собеседник\s+{NAME}',
        rf'(?i)информировал[аи]?\s+{NAME}',
        rf'(?i)отметил[аи]?\s+{NAME}',
        rf'(?i)подчеркнул[аи]?\s+{NAME}',
        rf'(?i)рассказал[аи]?\s+{NAME}',
        rf'(?i)заявил[аи]?\s+{NAME}',
        r'(?i)Trend\s*[,.]?',
        r'(?i)Kazinform\s*[,.]?',
        r'(?i)Inform\.kz\s*[,.]?',
        r'(?i)РИА\s+Новости\s*[,.]?',
        r'(?i)ТАСС\s*[,.]?',
        r'(?i)Интерфакс\s*[,.]?',
        r'(?i)Евразия\s+Сегодня\s*[,.]?',
        r'\[[^\]]*\]',
        r'\([^)]*\)',
    ]

    for pattern in patterns:
        text = re.sub(pattern, '', text)

    # Если после удаления фразы у текста остался "голый" хвост вида ", " или "— "
    text = re.sub(r'[,;\-–—]\s*$', '.', text.strip())
    text = re.sub(r'[,.]{2,}', '.', text)
    # То же самое, но в СЕРЕДИНЕ текста — если вырезанная СМИ-фраза стояла
    # не в конце всего текста, а в конце своего предложения (например,
    # "..., сообщает Trend. Далее ..."), после удаления остаётся висячая
    # запятая перед точкой ("..., ."), которую нужно схлопнуть в точку.
    text = re.sub(r',\s*\.', '.', text)
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

def split_real_sentences(text):
    """Разбивает очищенный текст на настоящие предложения (не короче 25 символов)."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if len(p.strip()) >= 25]

def strip_quote_attribution(sentence):
    """
    Убирает прямую речь в кавычках-ёлочках и висячую атрибуцию вида
    "— сказал он" / "— рассказал почётный железнодорожник Калтай" —
    превращает цитату в косвенную речь и убирает атрибуцию к реальному
    человеку, а не выбрасывает содержание целиком.
    """
    s = sentence
    # "«...», — сказал он." -> "..."
    s = re.sub(
        r'[«"]([^»"]+)[»"]\s*,?\s*[—\-–]\s*(сказал|сообщил|отметил|подчеркнул|заявил)[аи]?\s+'
        r'(?:[«»A-Za-zА-Яа-я\-]+\s*){1,6}\.?',
        r'\1.', s
    )
    # Висячая атрибуция в конце (кавычки могли охватывать не всю фразу,
    # напр. "..., — рассказал почётный железнодорожник Калтай")
    s = re.sub(
        r'\s*,?\s*[—\-–]\s*(рассказал|сказал|сообщил|отметил|подчеркнул|заявил)[аи]?\s+'
        r'(?:[«»A-Za-zА-Яа-я\-]+\s*){1,6}$',
        '', s.strip()
    )
    s = re.sub(r'^[«"]|[»"]$', '', s).strip()
    return s

def generate_unique_summary(title, original_summary):
    """
    Генерирует пересказ своими словами на основе РЕАЛЬНОГО текста статьи.
    Факты (даты/числа/города) используются как опциональное дополнение,
    а не как единственный источник — при их отсутствии функция больше
    не выбрасывает содержание статьи и не подставляет вместо него заголовок.

    В отличие от предыдущей версии, пересказ не просто заменяет отдельные
    слова синонимами: части предложений переставляются местами
    (restructure_sentence), а между предложениями используются
    переменные связки (join_sentences_naturally) вместо простого
    сложения через точку — так текст читается как связный пересказ,
    а не как список переставленных слов исходной статьи.
    """
    if not original_summary:
        original_summary = title

    # 1. Удаляем HTML и СМИ-фразы
    text = strip_html(original_summary)
    text = clean_media_phrases(text)

    # 2. Извлекаем факты (используются только как опциональное вступление)
    facts = extract_facts(text)

    new_sentences = []

    # --- Опциональное вступление с датой — только для явных анонсов форумов ---
    if facts['dates'] and ('форум' in title.lower() or 'конференц' in title.lower()):
        date = facts['dates'][0]
        action = random.choice(['состоится', 'пройдёт', 'запланирован'])
        new_sentences.append(f"{date} в Центральной Азии {action} логистический форум.")

    # --- Основа пересказа: реальные предложения статьи, перестроенные и перефразированные ---
    real_sentences = split_real_sentences(text)
    used_body = False
    for s in real_sentences[:3]:
        s = strip_quote_attribution(s)
        s = restructure_sentence(s)
        s = paraphrase_text(s)
        s = s.strip()
        if len(s) < 20:
            continue
        if not s.endswith(('.', '!', '?')):
            s += '.'
        new_sentences.append(s)
        used_body = True

    # --- Числа/организации — добавляем отдельным уточняющим предложением, если есть ---
    if facts['numbers']:
        num = facts['numbers'][0]
        org = facts['orgs'][0] if facts['orgs'] else None
        if org and org.lower() not in ' '.join(new_sentences).lower():
            new_sentences.append(f"По данным {org}, ключевые параметры составляют {num}.")

    # --- Если в статье вообще не нашлось пригодного текста — только тогда заголовок ---
    if not used_body:
        new_sentences.append(paraphrase_text(title) + '.')

    # 4. Собираем текст с переменными связками между предложениями,
    #    а не простым сложением через точку
    result = join_sentences_naturally(new_sentences)
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
        # golos.tj — таджикский сайт; его новости о логистике почти
        # никогда не называют "Таджикистан" явно, поэтому страну не требуем.
        if not is_relevant(title, summary, implicit_region=True):
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
        # logistan.info целиком посвящён логистике Центральной Азии —
        # явного упоминания страны в конкретной новости не требуем.
        if not is_relevant(title, summary, implicit_region=True):
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
        # inform.kz — общее казахстанское агентство, освещает и мировую
        # логистику, поэтому здесь по-прежнему требуем явное упоминание
        # страны ЦА, чтобы не тащить нерелевантные новости.
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
