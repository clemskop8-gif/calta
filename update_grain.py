"""
Обновляет data/grain.json свежей котировкой пшеницы.

Источник: Alpha Vantage (бесплатный ключ, лимит 25 запросов/день —
для обновления раз в сутки более чем достаточно).
Получить ключ: https://www.alphavantage.co/support/#api-key

Ключ НЕ хранится в коде — берётся из переменной окружения
ALPHAVANTAGE_KEY, которая приходит из GitHub Secrets.
Если ключ не задан или запрос не удался — файл помечается как demo,
сайт в этом случае покажет прежние демонстрационные данные.
"""
import json
import os
import sys
from datetime import datetime, timezone
import requests

API_KEY = os.environ.get("ALPHAVANTAGE_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "grain.json")

FALLBACK = {
    "isDemo": True,
    "crop": "Пшеница",
    "cropEn": "Wheat · CBOT",
    "price": 238,
    "currency": "USD",
    "unit": "т",
    "changeAbs": 3.3,
    "changePercent": 1.4,
    "direction": "up",
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "spark": [222, 225, 221, 228, 231, 227, 233, 230, 236, 232, 238, 235, 238],
}


def fetch_wheat():
    if not API_KEY:
        print("ALPHAVANTAGE_KEY не задан — оставляю demo-данные.")
        return None
    url = "https://www.alphavantage.co/query"
    params = {"function": "WHEAT", "interval": "daily", "apikey": API_KEY}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    payload = r.json()
    series = payload.get("data")
    if not series or len(series) < 2:
        print("Неожиданный ответ Alpha Vantage:", payload)
        return None

    # data[0] — самая свежая точка, data[1] — предыдущая
    latest = float(series[0]["value"])
    prev = float(series[1]["value"])
    change_abs = round(latest - prev, 2)
    change_pct = round((change_abs / prev) * 100, 2) if prev else 0
    spark = [float(p["value"]) for p in series[:14]][::-1]  # последние 14 точек, по возрастанию даты

    return {
        "isDemo": False,
        "crop": "Пшеница",
        "cropEn": "Wheat · Alpha Vantage",
        "price": round(latest, 2),
        "currency": "USD",
        "unit": "т",
        "changeAbs": abs(change_abs),
        "changePercent": abs(change_pct),
        "direction": "up" if change_abs >= 0 else "down",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "spark": spark,
    }


def main():
    data = fetch_wheat() or FALLBACK
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Записано:", OUT_PATH, "-> isDemo =", data["isDemo"])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Ошибка обновления котировки, оставляю demo-данные:", e, file=sys.stderr)
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(FALLBACK, f, ensure_ascii=False, indent=2)
