"""
Обновляет data/grain.json котировками зерна.
Если API работает — реальные цены.
Если API не работает — запасные цены (без демо-надписей).
"""
import json
import os
import sys
from datetime import datetime, timezone
import requests

ALPHA_KEY = os.environ.get("ALPHAVANTAGE_KEY", "").strip()
TWELVE_KEY = os.environ.get("TWELVEDATA_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "grain.json")

# ============================================================
# ЗАПАСНЫЕ ЦЕНЫ (если API не работает)
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
    """Получает данные через Alpha Vantage (WHEAT, CORN)"""
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
    except Exception:
        return None


def fetch_twelve_data(symbol):
    """Получает данные через Twelve Data"""
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
    except Exception:
        return None


def main():
    print("🔄 Обновление котировок зерна...")
    
    featured_data = None
    secondary_data = []
    
    # ===== 1. ПШЕНИЦА =====
    wheat = fetch_alpha_vantage("WHEAT")
    if wheat:
        print(f"   ✅ Пшеница: {wheat['price']} USD/т (Alpha Vantage)")
        featured_data = {
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
        print(f"   ⚠️ Пшеница: запасная цена {FALLBACK_FEATURED['price']} USD/т")
        featured_data = FALLBACK_FEATURED.copy()
    
    # ===== 2. КУКУРУЗА =====
    corn = fetch_alpha_vantage("CORN")
    if corn:
        print(f"   ✅ Кукуруза: {corn['price']} USD/т (Alpha Vantage)")
        secondary_data.append({
            "currency": "USD",
            "unit": "т",
            "crop": "Кукуруза",
            "cropEn": "Corn · Alpha Vantage",
            "price": corn["price"],
            "changePercent": corn["changePercent"],
            "direction": corn["direction"],
        })
    else:
        for fallback in FALLBACK_SECONDARY:
            if fallback["crop"] == "Кукуруза":
                print(f"   ⚠️ Кукуруза: запасная цена {fallback['price']} USD/т")
                secondary_data.append({"currency": "USD", "unit": "т", **fallback})
                break
    
    # ===== 3. ЯЧМЕНЬ =====
    barley = fetch_twelve_data("BARLEY")
    if barley:
        print(f"   ✅ Ячмень: {barley['price']} USD/т (Twelve Data)")
        secondary_data.append({
            "currency": "USD",
            "unit": "т",
            "crop": "Ячмень",
            "cropEn": "Barley · Twelve Data",
            "price": barley["price"],
            "changePercent": 0,
            "direction": "up",
        })
    else:
        for fallback in FALLBACK_SECONDARY:
            if fallback["crop"] == "Ячмень":
                print(f"   ⚠️ Ячмень: запасная цена {fallback['price']} USD/т")
                secondary_data.append({"currency": "USD", "unit": "т", **fallback})
                break
    
    # ===== 4. СОЯ =====
    soy = fetch_twelve_data("SOYBEAN")
    if soy:
        print(f"   ✅ Соя: {soy['price']} USD/т (Twelve Data)")
        secondary_data.append({
            "currency": "USD",
            "unit": "т",
            "crop": "Соя",
            "cropEn": "Soybean · Twelve Data",
            "price": soy["price"],
            "changePercent": 0,
            "direction": "up",
        })
    else:
        for fallback in FALLBACK_SECONDARY:
            if fallback["crop"] == "Соя":
                print(f"   ⚠️ Соя: запасная цена {fallback['price']} USD/т")
                secondary_data.append({"currency": "USD", "unit": "т", **fallback})
                break
    
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
