"""
Обновляет data/grain.json котировками зерна.
Если API работает — реальные цены.
Если API не работает — запасные цены (без демо-надписей).

Источники:
  Пшеница  — Alpha Vantage (function=WHEAT), нужен ALPHAVANTAGE_KEY
  Кукуруза — Alpha Vantage (function=CORN),  нужен ALPHAVANTAGE_KEY
  Ячмень   — бесплатного живого источника нет, всегда приблизительная цена
  Соя      — бесплатного живого источника цены за тонну нет
             (биржевые тикеры вроде SOYB — это ETF в USD/акция, а не USD/т,
             показывать их как цену тонны было бы недостоверно),
             поэтому тоже приблизительная цена
"""
import json
import os
import time
from datetime import datetime, timezone
import requests

ALPHA_KEY = os.environ.get("ALPHAVANTAGE_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "grain.json")

# ============================================================
# ЗАПАСНЫЕ / ПРИБЛИЗИТЕЛЬНЫЕ ЦЕНЫ
# (используются, если живой источник недоступен или отсутствует)
# ============================================================

FALLBACK_FEATURED = {
    "crop": "Пшеница",
    "cropEn": "Wheat · CBOT",
    "price": 228.74,
    "currency": "USD",
    "unit": "т",
    "changeAbs": 3.3,
    "changePercent": 1.4,
    "direction": "up",
    "spark": [222, 225, 221, 228, 231, 227, 233, 230, 236, 232, 238, 235, 238],
}

FALLBACK_SECONDARY = [
    {"crop": "Кукуруза", "cropEn": "Corn", "price": 191, "changePercent": 0.9, "direction": "up"},
    {"crop": "Ячмень", "cropEn": "Barley", "price": 205, "changePercent": 0.6, "direction": "down"},
    {"crop": "Соя", "cropEn": "Soybean", "price": 438, "changePercent": 0.3, "direction": "up"},
]


def fetch_alpha_vantage(function_name):
    """
    Получает данные через Alpha Vantage (WHEAT, CORN).
    Важно: у товарных функций Alpha Vantage нет дневного интервала —
    только monthly/quarterly/annual, поэтому запрашиваем monthly
    (это реальная последняя доступная точка, просто она обновляется
    не каждый день, а раз в месяц — это ограничение самого API).
    """
    if not ALPHA_KEY:
        print(f"      (нет ALPHAVANTAGE_KEY)")
        return None
    try:
        url = "https://www.alphavantage.co/query"
        params = {"function": function_name, "interval": "monthly", "apikey": ALPHA_KEY}
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        series = data.get("data")
        if not series or len(series) < 2:
            # Alpha Vantage вместо данных часто присылает служебное сообщение —
            # выводим его в лог, чтобы сразу видеть причину (лимит, неверный ключ и т.д.)
            reason = data.get("Note") or data.get("Information") or data.get("Error Message") or data
            print(f"      (нет данных от Alpha Vantage: {reason})")
            return None
        latest = float(series[0]["value"])
        prev = float(series[1]["value"])
        spark = [float(p["value"]) for p in series[:14]][::-1]
        return {
            "price": round(latest, 2),
            "spark": spark,
            "changeAbs": abs(round(latest - prev, 2)),
            "changePercent": abs(round(((latest - prev) / prev) * 100, 2)) if prev else 0,
            "direction": "up" if latest >= prev else "down",
        }
    except Exception as e:
        print(f"      (ошибка запроса к Alpha Vantage: {e})")
        return None


def get_fallback_secondary(crop_name):
    for item in FALLBACK_SECONDARY:
        if item["crop"] == crop_name:
            return {"currency": "USD", "unit": "т", **item}
    return None


def main():
    print("🔄 Обновление котировок зерна...")

    secondary_data = []

    # ===== 1. ПШЕНИЦА (Alpha Vantage) =====
    wheat = fetch_alpha_vantage("WHEAT")
    if wheat:
        print(f"   ✅ Пшеница: {wheat['price']} USD/т (Alpha Vantage)")
        featured_data = {
            "crop": "Пшеница",
            "cropEn": "Wheat · CBOT",
            "price": wheat["price"],
            "currency": "USD",
            "unit": "т",
            "changeAbs": wheat["changeAbs"],
            "changePercent": wheat["changePercent"],
            "direction": wheat["direction"],
            "spark": wheat["spark"],
        }
    else:
        print(f"   ⚠️ Пшеница: запасная цена {FALLBACK_FEATURED['price']} USD/т")
        featured_data = FALLBACK_FEATURED.copy()

    # ===== 2. КУКУРУЗА (Alpha Vantage) =====
    # Пауза перед вторым запросом — бесплатный тариф Alpha Vantage
    # ограничивает не только число запросов в день, но и частоту.
    print("   ⏳ Пауза 15 секунд перед следующим запросом (лимит Alpha Vantage)...")
    time.sleep(15)
    corn = fetch_alpha_vantage("CORN")
    if corn:
        print(f"   ✅ Кукуруза: {corn['price']} USD/т (Alpha Vantage)")
        secondary_data.append({
            "currency": "USD",
            "unit": "т",
            "crop": "Кукуруза",
            "cropEn": "Corn",
            "price": corn["price"],
            "changePercent": corn["changePercent"],
            "direction": corn["direction"],
        })
    else:
        fallback = get_fallback_secondary("Кукуруза")
        print(f"   ⚠️ Кукуруза: запасная цена {fallback['price']} USD/т")
        secondary_data.append(fallback)

    # ===== 3. ЯЧМЕНЬ (живого бесплатного источника нет — приблизительная цена) =====
    fallback = get_fallback_secondary("Ячмень")
    print(f"   ℹ️ Ячмень: приблизительная цена {fallback['price']} USD/т")
    secondary_data.append(fallback)

    # ===== 4. СОЯ (живого источника цены за тонну нет — приблизительная цена) =====
    fallback = get_fallback_secondary("Соя")
    print(f"   ℹ️ Соя: приблизительная цена {fallback['price']} USD/т")
    secondary_data.append(fallback)

    # ============================================================
    # ФОРМИРУЕМ ИТОГОВЫЙ JSON
    # ============================================================

    data = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "featured": featured_data,
        "secondary": secondary_data[:3],
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Записано: {OUT_PATH}")
    print(f"   Пшеница: {featured_data['price']} USD/т")
    for item in secondary_data[:3]:
        print(f"   {item['crop']}: {item['price']} USD/т")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        data = {
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "featured": FALLBACK_FEATURED.copy(),
            "secondary": [
                {"currency": "USD", "unit": "т", **item}
                for item in FALLBACK_SECONDARY
            ],
        }
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("   ✅ Сохранены запасные цены")
