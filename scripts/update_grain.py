"""
Обновляет data/grain.json котировками зерна.

Живые данные (Alpha Vantage, бесплатный ключ, лимит 25 запросов/день):
  - Пшеница (WHEAT)
  - Кукуруза (CORN)
Это единственные два зерновых, которые Alpha Vantage отдаёт бесплатно.

Ячмень и соя — у Alpha Vantage (и вообще у бесплатных API без подписки)
живых котировок по ним нет. Чтобы не выдумывать цифры, они помечены
"isDemo": true и берутся из MANUAL_SECONDARY ниже — при желании можно
руками поправить значение здесь, и оно попадёт на сайт при следующем
запуске workflow. Если позже подключите платный источник (например,
Nasdaq Data Link) — замените fetch_manual_crop() на реальный запрос,
формат ответа должен совпадать с fetch_commodity().

Ключ НЕ хранится в коде — берётся из переменной окружения
ALPHAVANTAGE_KEY (GitHub Secrets).
"""
import json
import os
import sys
from datetime import datetime, timezone
import requests

API_KEY = os.environ.get("ALPHAVANTAGE_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "grain.json")

# Ручные значения для культур без бесплатного живого источника.
# Поправьте цифры здесь при необходимости — они попадут на сайт
# при следующем запуске workflow (Actions → Run workflow).
MANUAL_SECONDARY = [
    {"crop": "Ячмень", "cropEn": "Barley", "price": 205, "changePercent": 0.6, "direction": "down"},
    {"crop": "Соя", "cropEn": "Soybean", "price": 438, "changePercent": 0.3, "direction": "up"},
]

FALLBACK_FEATURED = {
    "isDemo": True,
    "crop": "Пшеница",
    "cropEn": "Wheat · CBOT",
    "price": 238,
    "currency": "USD",
    "unit": "т",
    "changeAbs": 3.3,
    "changePercent": 1.4,
    "direction": "up",
    "spark": [222, 225, 221, 228, 231, 227, 233, 230, 236, 232, 238, 235, 238],
}

FALLBACK_CORN = {
    "isDemo": True,
    "crop": "Кукуруза",
    "cropEn": "Corn",
    "price": 191,
    "currency": "USD",
    "unit": "т",
    "changePercent": 0.9,
    "direction": "up",
}


def fetch_commodity(function_name, crop_ru, crop_en_label):
    """Универсальный запрос к Alpha Vantage для WHEAT / CORN."""
    if not API_KEY:
        print("ALPHAVANTAGE_KEY не задан —", crop_ru, "останется demo.")
        return None
    url = "https://www.alphavantage.co/query"
    params = {"function": function_name, "interval": "daily", "apikey": API_KEY}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    payload = r.json()
    series = payload.get("data")
    if not series or len(series) < 2:
        print(f"Неожиданный ответ Alpha Vantage для {function_name}:", payload)
        return None

    latest = float(series[0]["value"])
    prev = float(series[1]["value"])
    change_abs = round(latest - prev, 2)
    change_pct = round((change_abs / prev) * 100, 2) if prev else 0
    spark = [float(p["value"]) for p in series[:14]][::-1]

    return {
        "isDemo": False,
        "crop": crop_ru,
        "cropEn": crop_en_label,
        "price": round(latest, 2),
        "currency": "USD",
        "unit": "т",
        "changeAbs": abs(change_abs),
        "changePercent": abs(change_pct),
        "direction": "up" if change_abs >= 0 else "down",
        "spark": spark,
    }


def build_secondary(corn):
    secondary = [corn or FALLBACK_CORN]
    for manual in MANUAL_SECONDARY:
        secondary.append({
            "isDemo": True,  # честно: живого бесплатного источника по этой культуре нет
            "currency": "USD",
            "unit": "т",
            **manual,
        })
    return secondary


def main():
    featured = fetch_commodity("WHEAT", "Пшеница", "Wheat · Alpha Vantage") or FALLBACK_FEATURED
    corn = fetch_commodity("CORN", "Кукуруза", "Corn · Alpha Vantage")

    data = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "featured": featured,
        "secondary": build_secondary(corn),
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(
        "Записано:", OUT_PATH,
        "-> пшеница isDemo =", featured["isDemo"],
        ", кукуруза isDemo =", data["secondary"][0]["isDemo"],
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Ошибка обновления котировок, оставляю demo-данные:", e, file=sys.stderr)
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "featured": FALLBACK_FEATURED,
                "secondary": build_secondary(None),
            }, f, ensure_ascii=False, indent=2)
