"""
Обновляет data/grain.json котировками зерна.
Использует Twelve Data API.
"""
import json
import os
import sys
from datetime import datetime, timezone
import requests

API_KEY = os.environ.get("TWELVEDATA_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "grain.json")

# Карта культур → символы в Twelve Data (проверенные рабочие символы)
SYMBOLS = {
    "Пшеница": {"symbol": "WHEAT", "label": "Wheat · Twelve Data"},
    "Кукуруза": {"symbol": "CORN", "label": "Corn · Twelve Data"},
    "Ячмень": {"symbol": "BARLEY", "label": "Barley · Twelve Data"},
    "Соя": {"symbol": "SOYBEAN", "label": "Soybean · Twelve Data"},
}

# Альтернативные символы (если основные не работают)
ALTERNATIVE_SYMBOLS = {
    "Пшеница": ["ZW", "WHEAT"],
    "Кукуруза": ["ZC", "CORN"],
    "Ячмень": ["BARLEY", "AB"],
    "Соя": ["ZS", "SOYBEAN"],
}

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


def fetch_price(symbol):
    """Получает текущую цену для символа через Twelve Data"""
    if not API_KEY:
        print(f"  ⚠️ TWELVEDATA_KEY не задан")
        return None
    
    try:
        url = "https://api.twelvedata.com/price"
        params = {"symbol": symbol, "apikey": API_KEY}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        if "price" not in data:
            print(f"  ⚠️ Нет цены для {symbol}: {data.get('message', data)}")
            return None
        
        return float(data["price"])
        
    except Exception as e:
        print(f"  ❌ Ошибка для {symbol}: {e}")
        return None


def fetch_spark(symbol):
    """Получает историю за 14 дней для графика"""
    if not API_KEY:
        return None
    
    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": symbol,
            "interval": "1day",
            "outputsize": 14,
            "apikey": API_KEY
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        values = data.get("values", [])
        if not values:
            return None
        
        spark = [float(v["close"]) for v in values]
        spark.reverse()
        return spark
        
    except Exception as e:
        print(f"  ❌ Ошибка истории для {symbol}: {e}")
        return None


def fetch_with_fallback(crop_name, symbol, label):
    """Пытается получить данные по основному символу, потом по альтернативным"""
    
    # Основной символ
    price = fetch_price(symbol)
    if price is not None:
        spark = fetch_spark(symbol)
        return {"price": price, "spark": spark}
    
    # Альтернативные символы
    alt_symbols = ALTERNATIVE_SYMBOLS.get(crop_name, [])
    for alt in alt_symbols:
        if alt == symbol:
            continue
        print(f"    🔄 Пробуем {crop_name} через {alt}...")
        price = fetch_price(alt)
        if price is not None:
            spark = fetch_spark(alt)
            return {"price": price, "spark": spark}
    
    return None


def main():
    print("🔄 Обновление котировок зерна (Twelve Data)...")
    
    featured_data = None
    secondary_data = []
    
    for crop_name, info in SYMBOLS.items():
        symbol = info["symbol"]
        label = info["label"]
        
        print(f"  Загрузка {crop_name} ({symbol})...")
        result = fetch_with_fallback(crop_name, symbol, label)
        
        if result:
            price = result["price"]
            spark = result["spark"]
            
            # Вычисляем изменения
            if spark and len(spark) >= 2:
                prev = spark[-2]
                change_abs = price - prev
                change_pct = (change_abs / prev) * 100 if prev else 0
            else:
                change_abs = 0
                change_pct = 0
            
            print(f"    ✅ {crop_name}: {price} USD/т")
            
            entry = {
                "isDemo": False,
                "crop": crop_name,
                "cropEn": label,
                "price": round(price, 2),
                "currency": "USD",
                "unit": "т",
                "changeAbs": abs(round(change_abs, 2)),
                "changePercent": abs(round(change_pct, 2)),
                "direction": "up" if change_abs >= 0 else "down",
            }
            
            if crop_name == "Пшеница":
                if spark:
                    entry["spark"] = spark
                else:
                    entry["spark"] = [price] * 14
                featured_data = entry
            else:
                secondary_data.append(entry)
        else:
            print(f"    ⚠️ {crop_name} — используется демо")
            if crop_name == "Пшеница":
                featured_data = FALLBACK_FEATURED.copy()
            else:
                for fallback in FALLBACK_SECONDARY:
                    if fallback["crop"] == crop_name:
                        secondary_data.append({
                            "isDemo": True,
                            "currency": "USD",
                            "unit": "т",
                            **fallback,
                        })
                        break
    
    # Если Пшеница не загрузилась — ставим демо
    if not featured_data:
        featured_data = FALLBACK_FEATURED.copy()
        print("  ⚠️ Пшеница — демо-данные")
    
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
