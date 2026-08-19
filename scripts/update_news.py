"""
Обновляет data/news.json — новости с inform.kz, asiaplustj.info, 24.kg.
ГЛУБОКИЙ РЕРАЙТ: меняется структура, порядок частей, убираются шаблонные фразы.
Картинки из Unsplash без подписей. Плашки и ссылки убраны.
"""
import html
import json
import os
import re
import random
from datetime import datetime, timezone
import requests
import feedparser

UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
MAX_ITEMS = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ============================================================
# 1. РАСШИРЕННЫЙ СЛОВАРЬ СИНОНИМОВ
# ============================================================
SYNONYMS = {
    "логистика": ["транспорт", "грузоперевозки", "доставка грузов", "перевозки", "транспортная логистика"],
    "транспорт": ["логистика", "перевозки", "транспортная система", "средства доставки"],
    "груз": ["товар", "продукция", "контейнеры", "грузы", "продукты"],
    "перевозки": ["транспортировка", "доставка", "грузоперевозки", "перемещение грузов"],
    "порт": ["гавань", "морской терминал", "причал", "портовая инфраструктура"],
    "контейнер": ["грузовой модуль", "контейнерный модуль", "тара", "стандартный бокс"],
    "терминал": ["хаб", "распределительный центр", "логистический центр", "транспортный узел"],
    "склад": ["хранилище", "складской комплекс", "распределительный центр", "товарный депо"],
    "дорога": ["трасса", "магистраль", "автотрасса", "путь", "маршрут"],
    "железная дорога": ["ЖД", "ж/д", "железнодорожная линия", "рельсовый путь", "стальная магистраль"],
    "коридор": ["маршрут", "направление", "путь", "трасса", "транспортная артерия"],
    "инвестиция": ["вложение", "финансирование", "капитал", "вклады", "средства"],
    "проект": ["программа", "инициатива", "стройка", "объект", "предприятие"],
    "развитие": ["рост", "прогресс", "совершенствование", "улучшение", "эволюция"],
    "строительство": ["возведение", "создание", "постройка", "сооружение"],
    "открытие": ["запуск", "введение в эксплуатацию", "старт", "начало работы"],
    "открыли": ["запустили", "ввели в строй", "начали работу", "ввели в эксплуатацию"],
    "запустили": ["открыли", "ввели в эксплуатацию", "запустили работу", "дали старт"],
    "построили": ["возвели", "создали", "соорудили", "воздвигли"],
    "планируют": ["намерены", "собираются", "хотят", "предполагают"],
    "создадут": ["построят", "возведут", "организуют", "сформируют"],
    "увеличится": ["вырастет", "повысится", "возрастет", "поднимется"],
    "составит": ["достигнет", "будет на уровне", "составит", "достигнет отметки"],
    "инвестируют": ["вложат", "направят средства", "профинансируют", "выделят"],
    "позволит": ["даст возможность", "обеспечит", "позволит", "создаст условия"],
    "обеспечит": ["гарантирует", "даст", "создаст условия для", "предоставит"],
    "новый": ["современный", "перспективный", "инновационный", "свежий", "передовой"],
    "крупный": ["масштабный", "значительный", "крупнейший", "внушительный", "большой"],
    "важный": ["ключевой", "значимый", "существенный", "основной", "главный"],
    "успешный": ["результативный", "эффективный", "плодотворный", "продуктивный"],
    "транспортный": ["логистический", "перевозочный", "транзитный", "грузовой"],
    "экономика": ["хозяйство", "финансовая система", "экономическая сфера", "бизнес-среда"],
    "торговля": ["коммерция", "обмен товарами", "торговые операции", "бизнес"],
    "цифровизация": ["автоматизация", "внедрение IT", "цифровая трансформация", "информатизация"],
    "инновации": ["новшества", "технологии", "передовые решения", "разработки"],
    "инфраструктура": ["объекты", "комплексы", "сеть", "система"],
    "делегация": ["представители", "команда", "группа", "члены делегации"],
    "встреча": ["переговоры", "совещание", "диалог", "беседа"],
    "обсудили": ["рассмотрели", "обменялись мнениями", "поговорили", "обсудили вопросы"],
    "улучшение": ["развитие", "совершенствование", "оптимизация", "повышение эффективности"],
    "маршрут": ["путь", "направление", "трасса", "коридор"],
    "переговоры": ["встреча", "совещание", "диалог", "консультации"],
}

# ============================================================
# 2. ФУНКЦИИ РЕРАЙТА
# ============================================================
def rewrite_text(text):
    """Замена слов на синонимы"""
    if not text:
        return text
    words = text.split()
    new_words = []
    for word in words:
        clean_word = re.sub(r'[^\w\s]', '', word).lower()
        replaced = False
        for key, synonyms in SYNONYMS.items():
            if clean_word == key.lower() or clean_word in key.lower():
                new_word = random.choice(synonyms)
                if word[0].isupper():
                    new_word = new_word.capitalize()
                new_words.append(new_word)
                replaced = True
                break
        if not replaced:
            new_words.append(word)
    return ' '.join(new_words)

def generate_unique_title(original_title):
    """Генерирует уникальный заголовок"""
    if not original_title:
        return ""
    title = rewrite_text(original_title)
    if '—' in title:
        parts = title.split('—')
        if len(parts) == 2:
            title = f"{parts[1].strip()} — {parts[0].strip()}"
    elif ',' in title:
        parts = title.split(',')
        if len(parts) == 2:
            title = f"{parts[1].strip()}, {parts[0].strip()}"
    countries = ["Казахстан", "Узбекистан", "Кыргызстан", "Таджикистан", "Туркменистан"]
    has_country = any(c in title for c in countries)
    if not has_country and len(title) > 10:
        title = f"{title} в Центральной Азии"
    return title

def generate_unique_summary(original_summary):
    """Генерирует уникальное описание с удалением шаблонных фраз"""
    if not original_summary:
        return "Подробнее в источнике."
    
    # 1. Замена синонимов
    summary = rewrite_text(original_summary)
    
    # 2. Убираем шаблонные фразы (они выдают плагиат)
    summary = re.sub(r'передает агентство Kazinform со ссылкой на', 'Как сообщили в', summary)
    summary = re.sub(r'передает агентство Kazinform', 'По информации', summary)
    summary = re.sub(r'со ссылкой на', 'в', summary)
    summary = re.sub(r'пресс-службу акимата региона', 'региональный акимат', summary)
    summary = re.sub(r'агентство Kazinform', 'источник', summary)
    
    # 3. Разбиваем на логические части
    location_match = re.search(r'(в|на) ([А-Яа-я]+ском|ском) районе ([А-Яа-я]+ской области)', summary)
    object_match = re.search(r'(логистический|транспортный|терминал|хаб|центр|комплекс)', summary)
    company_match = re.search(r'(компании|Kusto|Logistics|АО|ТОО)', summary)
    action_match = re.search(r'(запустили|открыли|построили|ввели|начали|создали|запущен|открыт)', summary)
    
    # 4. Собираем текст в новом порядке
    parts = []
    
    if location_match:
        parts.append(f"В {location_match.group(0)}")
    
    if action_match and object_match:
        action = action_match.group(0)
        obj = object_match.group(0)
        parts.append(f"{action} новый {obj}")
    
    if company_match:
        parts.append(f"принадлежащий {company_match.group(0)}")
    
    parts.append("как сообщили в региональном акимате")
    
    if len(parts) >= 2:
        new_summary = ', '.join(parts) + '.'
    else:
        new_summary = summary
    
    # 5. Добавляем итоговую фразу
    endings = [
        " Это укрепит транспортные связи региона.",
        " Комплекс будет способствовать развитию логистики.",
        " Объект повысит эффективность грузоперевозок.",
        " Это важный шаг в развитии транспортной инфраструктуры.",
        " Новый центр расширит транспортные возможности.",
    ]
    if len(new_summary) > 30 and not any(new_summary.endswith(e) for e in endings):
        new_summary = new_summary + random.choice(endings)
    
    if len(new_summary) < 30:
        return summary
    
    return new_summary

# ============================================================
# 3. КАРТИНКИ ИЗ UNSPLASH (БЕЗ CREDIT)
# ============================================================
def pick_photo_from_unsplash(title, summary):
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
            return {"url": photo["urls"]["regular"]}
    except Exception:
        pass
    fallback_urls = [
        "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=800",
        "https://images.unsplash.com/photo-1494412574643-ff11b0a5c1c3?w=800",
        "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800",
        "https://images.unsplash.com/photo-1519003722824-356d8a3ff1a1?w=800",
    ]
    return {"url": random.choice(fallback_urls)}

# ============================================================
# 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

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
# 5. ПАРСИНГ inform.kz
# ============================================================
def collect_inform_kz():
    out = []
    url = "https://www.inform.kz/tag/logistika_t11100"
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"inform.kz ошибка: {e}")
        return out
    all_links = set()
    for link in re.findall(r'href=["\']([^"\']*/ru/[a-z0-9\-]+-[a-f0-9]{8})["\']', html_content, re.IGNORECASE):
        if link.startswith('http'):
            all_links.add(link)
        else:
            all_links.add("https://www.inform.kz" + link if link.startswith('/') else "https://www.inform.kz/" + link)
    print(f"inform.kz: найдено {len(all_links)} ссылок")
    for article_url in list(all_links)[:6]:
        try:
            ar = requests.get(article_url, timeout=20, headers=HEADERS)
            ar.raise_for_status()
            article_html = ar.text
        except Exception:
            continue
        title = _meta_tag(article_html, "og:title")
        if not title:
            continue
        summary = _meta_tag(article_html, "og:description")[:300]
        published = _meta_tag(article_html, "article:published_time")
        new_title = generate_unique_title(title)
        new_summary = generate_unique_summary(summary)
        photo = pick_photo_from_unsplash(new_title, new_summary)
        out.append({
            "title": new_title,
            "summary": new_summary or "Подробнее в источнике.",
            "publishedAt": published,
            "photo": photo,
            "_original": title[:50] + "..."
        })
        print(f"  ✅ inform.kz: {new_title[:50]}...")
    return out

# ============================================================
# 6. ПАРСИНГ asiaplustj.info
# ============================================================
def collect_asiaplus():
    out = []
    url = "https://asiaplustj.info/ru/news/economic"
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()
        html_content = r.text
    except Exception as e:
        print(f"asiaplustj ошибка: {e}")
        return out
    all_links = set()
    for link in re.findall(r'href=["\'](https?://asiaplustj\.info/[^"\']+\.html)["\']', html_content, re.IGNORECASE):
        if 'economic' in link or 'logistics' in link or 'transport' in link:
            all_links.add(link)
    print(f"asiaplustj: найдено {len(all_links)} ссылок")
    for article_url in list(all_links)[:6]:
        try:
            ar = requests.get(article_url, timeout=20, headers=HEADERS)
            ar.raise_for_status()
            article_html = ar.text
        except Exception:
            continue
        title = _meta_tag(article_html, "og:title")
        if not title:
            continue
        summary = _meta_tag(article_html, "og:description")[:300]
        published = _meta_tag(article_html, "article:published_time")
        if not any(w in (title + summary).lower() for w in ['логист', 'транспорт', 'перевозк', 'груз', 'контейнер', 'порт']):
            continue
        new_title = generate_unique_title(title)
        new_summary = generate_unique_summary(summary)
        photo = pick_photo_from_unsplash(new_title, new_summary)
        out.append({
            "title": new_title,
            "summary": new_summary or "Подробнее в источнике.",
            "publishedAt": published,
            "photo": photo,
            "_original": title[:50] + "..."
        })
        print(f"  ✅ asiaplustj: {new_title[:50]}...")
    return out

# ============================================================
# 7. ПАРСИНГ 24.kg (через RSS)
# ============================================================
def collect_24kg():
    out = []
    url = "https://24.kg/feed/"
    try:
        parsed = feedparser.parse(url, request_headers=HEADERS)
    except Exception as e:
        print(f"24.kg ошибка: {e}")
        return out
    print(f"24.kg: найдено {len(parsed.entries)} записей")
    for entry in parsed.entries[:8]:
        title = strip_html(entry.get("title") or "")
        if not title:
            continue
        summary = strip_html(entry.get("summary") or "")[:300]
        if not any(w in (title + summary).lower() for w in ['логист', 'транспорт', 'перевозк', 'груз', 'контейнер', 'порт', 'економик', 'инвестиц']):
            continue
        new_title = generate_unique_title(title)
        new_summary = generate_unique_summary(summary)
        photo = pick_photo_from_unsplash(new_title, new_summary)
        out.append({
            "title": new_title,
            "summary": new_summary or "Подробнее в источнике.",
            "publishedAt": entry.get("published", ""),
            "photo": photo,
            "_original": title[:50] + "..."
        })
        print(f"  ✅ 24.kg: {new_title[:50]}...")
    return out

# ============================================================
# 8. СБОР И ОБЪЕДИНЕНИЕ
# ============================================================
def collect():
    items = []
    print("\n🔍 Парсинг inform.kz...")
    items.extend(collect_inform_kz())
    print("\n🔍 Парсинг asiaplustj.info...")
    items.extend(collect_asiaplus())
    print("\n🔍 Парсинг 24.kg...")
    items.extend(collect_24kg())
    seen = set()
    unique_items = []
    for item in items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    unique_items.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)
    for item in unique_items:
        item.pop("_original", None)
    return unique_items[:MAX_ITEMS]

# ============================================================
# 9. MAIN
# ============================================================
def main():
    print("🚀 Начинаем сбор новостей с рерайтом...")
    items = collect()
    data = {
        "isDemo": len(items) == 0,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Записано: {OUT_PATH} -> {len(items)} новостей")
    for i, item in enumerate(items[:3]):
        print(f"  {i+1}. {item['title'][:60]}...")

if __name__ == "__main__":
    main()
