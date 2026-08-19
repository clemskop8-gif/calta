# 1. Добавить страны в фильтр
CENTRAL_ASIA_COUNTRIES = [
    "казахстан", "қазақстан", "kazakhstan", "kz",
    "узбекистан", "o'zbekiston", "uzbekistan", "uz",
    "кыргызстан", "kyrgyzstan", "kg",
    "таджикистан", "tojikiston", "tajikistan", "tj",
    "туркменистан", "turkmenistan", "tm",
    "центральная азия", "central asia", "цар",
]

# 2. Добавить логистические слова на русском
LOGISTICS_KEYWORDS_RU = [
    "логист", "груз", "перевозк", "транспорт", "порт", 
    "контейнер", "таможен", "склад", "жд", "железнодорож",
    "коридор", "экспорт", "импорт", "фрахт", "судоходств",
    "автоперевоз", "грузопоток", "транзит", "терминал",
    "вагон", "локомотив", "путь", "магистраль",
]

# 3. Функция проверки релевантности (страна + логистика)
def is_relevant(title, summary):
    text = (title + " " + summary).lower()
    
    # Должна быть хотя бы одна страна ЦА
    has_country = any(country in text for country in CENTRAL_ASIA_COUNTRIES)
    
    # И хотя бы одно логистическое слово
    has_logistics = any(kw in text for kw in LOGISTICS_KEYWORDS_RU)
    
    return has_country and has_logistics

# 4. Добавить больше русскоязычных источников
FEEDS = [
    # Казинформ (уже есть)
    {
        "url": "https://www.inform.kz/tag/logistika_t11100",
        "tag": "Казинформ",
        "query": "kazakhstan logistics",
        "type": "kazinform",
        "skip_filter": False,  # теперь фильтруем!
    },
    # 24.kg (Кыргызстан)
    {
        "url": "https://24.kg/feed/",
        "tag": "24.kg",
        "query": "kyrgyzstan transport logistics",
        "type": "rss",
        "skip_filter": False,
    },
    # Kun.uz (Узбекистан)
    {
        "url": "https://kun.uz/ru/news/feed",
        "tag": "Kun.uz",
        "query": "uzbekistan logistics transport",
        "type": "rss",
        "skip_filter": False,
    },
    # Азия-Плюс (Таджикистан)
    {
        "url": "https://asiaplustj.info/ru/rss",
        "tag": "Азия-Плюс",
        "query": "tajikistan transport logistics",
        "type": "rss",
        "skip_filter": False,
    },
    # Туркменистан (альтернативный источник)
    {
        "url": "https://turkmenportal.com/rss",
        "tag": "Туркменпортал",
        "query": "turkmenistan transport",
        "type": "rss",
        "skip_filter": False,
    },
    # Оставить англ. источники только как запасные
    {"url": "https://www.railfreight.com/feed", "tag": "RailFreight", "query": "central asia rail freight", "skip_filter": False},
]
