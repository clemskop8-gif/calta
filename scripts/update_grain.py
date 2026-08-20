"""
Обновляет data/grain.json котировками зерна.
Использует Twelve Data API (бесплатный, 800 запросов/день).
Все 4 культуры: Пшеница, Кукуруза, Ячмень, Соя.
Ключ берётся из переменной окружения TWELVEDATA_KEY (GitHub Secrets).
"""
import json
import os
import sys
from datetime import datetime, timezone
import requests

API_KEY = os.environ.get("TWELVEDATA_KEY", "").strip()
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "grain.json")

# Карта культур → символы в Twelve Data
SYMBOLS = {
    "Пшеница": {"symbol": "WHEAT", "label": "Wheat · Twelve Data"},
    "Кукуруза": {"symbol": "CORN", "label": "Corn · Twelve Data"},
    "Ячмень": {"symbol": "BARLEY", "label": "Barley · Twelve Data"},
    "Соя": {"symbol": "SOYBEAN", "label": "Soybean · Twelve Data"},
}

# Запасные демо-данные (если API не работает)
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
    """Получает текущую цену и историю для символа через Twelve Data"""
    if not API_KEY:
        print(f"  ⚠️ TWELVEDATA_KEY не задан")
        return None
    
    try:
        # Текущая цена
        url = "https://api.twelvedata.com/price"
        params = {"symbol": symbol, "apikey": API_KEY}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        if "price" not in data:
            print(f"  ⚠️ Нет цены для {symbol}: {data}")
            return None
        
        current_price = float(data["price"])
        
        # История за 14 дней (для графика spark)
        url_hist = "https://api.twelvedata.com/time_series"
        params_hist = {
            "symbol": symbol,
            "interval": "1day",
            "outputsize": 14,
            "apikey": API_KEY
        }
        r_hist = requests.get(url_hist, params=params_hist, timeout=15)
        r_hist.raise_for_status()
        hist_data = r_hist.json()
        
        values = hist_data.get("values", [])
        if not values:
            return {"price": current_price, "spark": [current_price] * 14}
        
        # Цены от старых к новым (для spark)
        spark = [float(v["close"]) for v in values]
        spark.reverse()
        
        # Изменение за последний день
        if len(spark) >= 2:
            prev = spark[-2]
            change_abs = current_price - prev
        else:
            change_abs = 0
        
        return {
            "price": round(current_price, 2),
            "spark": spark,
            "changeAbs": abs(change_abs),
            "changePercent": abs(round((change_abs / prev) * 100, 2)) if prev else 0,
            "direction": "up" if change_abs >= 0 else "down",
        }
        
    except Exception as e:
        print(f"  ❌ Ошибка для {symbol}: {e}")
        return None


def main():
    print("🔄 Обновление котировок зерна (Twelve Data)...")
    
    featured_data = None
    secondary_data = []
    
    for crop_name, info in SYMBOLS.items():
        symbol = info["symbol"]
        label = info["label"]
        
        print(f"  Загрузка {crop_name} ({symbol})...")
        data = fetch_price(symbol)
        
        if data:
            print(f"    ✅ {crop_name}: {data['price']} USD/т")
            entry = {
                "isDemo": False,
                "crop": crop_name,
                "cropEn": label,
                "price": data["price"],
                "currency": "USD",
                "unit": "т",
                "changeAbs": data["changeAbs"],
                "changePercent": data["changePercent"],
                "direction": data["direction"],
            }
            if crop_name == "Пшеница":
                entry["spark"] = data["spark"]
                featured_data = entry
            else:
                secondary_data.append(entry)
        else:
            print(f"    ⚠️ {crop_name} — используется демо")
            # Используем демо-данные
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
    
    # Формируем результат
    data = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "featured": featured_data,
        "secondary": secondary_data[:3],  # Кукуруза, Ячмень, Соя
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
        print("❌ Ошибка обновления котировок:", e, file=sys.stderr)
        # Сохраняем демо-данные
        data = {
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "featured": FALLBACK_FEATURED.copy(),
            "secondary": [
                {
                    "isDemo": True,
                    "currency": "USD",
                    "unit": "т",
                    **item,
                }
                for item in FALLBACK_SECONDARY
            ],
        }
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("   Сохранены демо-данные")
