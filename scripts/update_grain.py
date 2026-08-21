"""
Обновляет data/grain.json котировками зерна.
- Пшеница и Кукуруза: Alpha Vantage (стабильно)
- Ячмень и Соя: Twelve Data
"""
import json
import os
import sys
from datetime import datetime, timezone
import requests

ALPHA_KEY = os.environ.get("ALPHAVANTAGE_KEY", "").strip()
TWELVE_KEY = os.environ.get("TWELVEDATA_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "grain.json")

# Демо-данные
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

FALLBACK_SECONDARY = [
    {"crop": "Кукуруза", "cropEn": "Corn", "price": 191, "changePercent": 0.9, "direction": "up"},
    {"crop": "Ячмень", "cropEn": "Barley", "price": 205, "changePercent": 0.6, "direction": "down"},
    {"crop": "Соя", "cropEn": "Soybean", "price": 438, "changePercent": 0.3, "direction": "up"},
]


def fetch_alpha_vantage(function_name):
    """Получает данные через Alpha Vantage (стабильно работает для WHEAT и CORN)"""
    if not ALPHA_KEY:
        return None
    try:
        url = "https://www.alphavantage.co/query"
        params = {"function": function_name, "interval": "daily", "apikey": ALPHA_KEY}
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        series = data.get("data")
        if not series or len(series) < 2:
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
        print(f"  ❌ Alpha Vantage ошибка: {e}")
        return None


def fetch_twelve_data(symbol):
    """Получает данные через Twelve Data (для ячменя и сои)"""
    if not TWELVE_KEY:
        return None
    try:
        url = "https://api.twelvedata.com/price"
        params = {"symbol": symbol, "apikey": TWELVE_KEY}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if "price" not in data:
            return None
        return {"price": float(data["price"])}
    except Exception as e:
        print(f"  ❌ Twelve Data ошибка: {e}")
        return None


def main():
    print("🔄 Обновление котировок зерна (гибридный режим)...")
    
    featured_data = None
    secondary_data = []
    
    # ===== ПШЕНИЦА — Alpha Vantage =====
    print("  Загрузка Пшеница (Alpha Vantage)...")
    wheat = fetch_alpha_vantage("WHEAT")
    if wheat:
        print(f"    ✅ Пшеница: {wheat['price']} USD/т")
        featured_data = {
            "isDemo": False,
            "crop": "Пшеница",
            "cropEn": "Wheat · Alpha Vantage",
            "price": wheat["price"],
            "currency": "USD",
            "unit": "т",
            "changeAbs": wheat["changeAbs"],
            "changePercent": wheat["changePercent"],
            "direction": wheat["direction"],
            "spark": wheat["spark"],
        }
    else:
        print("    ⚠️ Пшеница — демо-данные")
        featured_data = FALLBACK_FEATURED.copy()
    
    # ===== КУКУРУЗА — Alpha Vantage =====
    print("  Загрузка Кукуруза (Alpha Vantage)...")
    corn = fetch_alpha_vantage("CORN")
    if corn:
        print(f"    ✅ Кукуруза: {corn['price']} USD/т")
        secondary_data.append({
            "isDemo": False,
            "currency": "USD",
            "unit": "т",
            "crop": "Кукуруза",
            "cropEn": "Corn · Alpha Vantage",
            "price": corn["price"],
            "changePercent": corn["changePercent"],
            "direction": corn["direction"],
        })
    else:
        print("    ⚠️ Кукуруза — демо-данные")
        for fallback in FALLBACK_SECONDARY:
            if fallback["crop"] == "Кукуруза":
                secondary_data.append({"isDemo": True, "currency": "USD", "unit": "т", **fallback})
                break
    
    # ===== ЯЧМЕНЬ — Twelve Data =====
    print("  Загрузка Ячмень (Twelve Data)...")
    barley = fetch_twelve_data("BARLEY")
    if barley:
        print(f"    ✅ Ячмень: {barley['price']} USD/т")
        secondary_data.append({
            "isDemo": False,
            "currency": "USD",
            "unit": "т",
            "crop": "Ячмень",
            "cropEn": "Barley · Twelve Data",
            "price": barley["price"],
            "changePercent": 0,
            "direction": "up",
        })
    else:
        print("    ⚠️ Ячмень — демо-данные")
        for fallback in FALLBACK_SECONDARY:
            if fallback["crop"] == "Ячмень":
                secondary_data.append({"isDemo": True, "currency": "USD", "unit": "т", **fallback})
                break
    
    # ===== СОЯ — Twelve Data =====
    print("  Загрузка Соя (Twelve Data)...")
    soy = fetch_twelve_data("SOYBEAN")
    if soy:
        print(f"    ✅ Соя: {soy['price']} USD/т")
        secondary_data.append({
            "isDemo": False,
            "currency": "USD",
            "unit": "т",
            "crop": "Соя",
            "cropEn": "Soybean · Twelve Data",
            "price": soy["price"],
            "changePercent": 0,
            "direction": "up",
        })
    else:
        print("    ⚠️ Соя — демо-данные")
        for fallback in FALLBACK_SECONDARY:
            if fallback["crop"] == "Соя":
                secondary_data.append({"isDemo": True, "currency": "USD", "unit": "т", **fallback})
                break
    
    # Формируем результат
    data = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "featured": featured_data,
        "secondary": secondary_data[:3],
    }
    
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Записано: {OUT_PATH}")
    print(f"   Пшеница: isDemo={featured_data['isDemo']}, цена={featured_data['price']}")
    for item in secondary_data[:3]:
        print(f"   {item['crop']}: isDemo={item['isDemo']}, цена={item['price']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ Ошибка:", e, file=sys.stderr)
        data = {
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "featured": FALLBACK_FEATURED.copy(),
            "secondary": [
                {"isDemo": True, "currency": "USD", "unit": "т", **item}
                for item in FALLBACK_SECONDARY
            ],
        }
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("   Сохранены демо-данные")
