import os
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "NEARUSDT", "APTUSDT", "ARBUSDT", "OPUSDT",
    "SUIUSDT", "INJUSDT", "TIAUSDT", "SEIUSDT", "FETUSDT"
]
TIMEFRAME = "15m"
BASE_URL = "https://data-api.binance.vision/api/v3/klines"


def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("TELEGRAM_TOKEN yoki CHAT_ID topilmadi!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload, timeout=10)


def get_candles(symbol, interval="15m", limit=50):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    candles = []
    for c in data[:-1]:  # yopilgan shamlarni olamiz
        candles.append({
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
        })
    return candles


def analyze_smc(candles):
    if len(candles) < 25:
        return None

    # 1. Candle Range & 2. Liquidity (oldingi 20 shamning High/Low diapazoni)
    lookback = candles[-24:-4]
    range_high = max(c["high"] for c in lookback)
    range_low = min(c["low"] for c in lookback)
    range_size = range_high - range_low
    if range_size == 0:
        return None

    recent = candles[-4:]  # oxirgi 4 ta yopilgan sham
    c0, c1, c2, c3 = recent[0], recent[1], recent[2], recent[3]

    # --- BULLISH SETUP (LONG) ---
    # 3. Liquidity Sweep (pastki likvidlikni yechish)
    swept_low = min(c0["low"], c1["low"]) < range_low

    # 4. Market Structure Shift (MSS - yuqoriga struktura buzilishi)
    swing_high = max(c["high"] for c in candles[-10:-3])
    bullish_mss = c2["close"] > swing_high or c3["close"] > swing_high

    # 5. Fair Value Gap (FVG - 1-sham High va 3-sham Low orasidagi bo'shliq)
    bullish_fvg = c3["low"] > c1["high"]

    if swept_low and bullish_mss and bullish_fvg:
        return {
            "direction": "🟢 LONG (Bullish SMC)",
            "price": c3["close"],
            "liquidity": f"{range_low:.4f}",
            "fvg": f"{c1['high']:.4f} - {c3['low']:.4f}"
        }

    # --- BEARISH SETUP (SHORT) ---
    # 3. Liquidity Sweep (yuqori likvidlikni yechish)
    swept_high = max(c0["high"], c1["high"]) > range_high

    # 4. Market Structure Shift (MSS - pastga struktura buzilishi)
    swing_low = min(c["low"] for c in candles[-10:-3])
    bearish_mss = c2["close"] < swing_low or c3["close"] < swing_low

    # 5. Fair Value Gap (FVG - 1-sham Low va 3-sham High orasidagi bo'shliq)
    bearish_fvg = c3["high"] < c1["low"]

    if swept_high and bearish_mss and bearish_fvg:
        return {
            "direction": "🔴 SHORT (Bearish SMC)",
            "price": c3["close"],
            "liquidity": f"{range_high:.4f}",
            "fvg": f"{c3['high']:.4f} - {c1['low']:.4f}"
        }

    return None


def main():
    found = []
    for symbol in SYMBOLS:
        try:
            candles = get_candles(symbol, TIMEFRAME)
            signal = analyze_smc(candles)
            if signal:
                msg = (
                    f"<b>{signal['direction']}</b>\n"
                    f"🪙 Juftlik: <b>{symbol}</b> ({TIMEFRAME})\n"
                    f"💰 Joriy narx: <code>{signal['price']}</code>\n"
                    f"💧 Yechilgan likvidlik: <code>{signal['liquidity']}</code>\n"
                    f"📊 FVG zonasi: <code>{signal['fvg']}</code>"
                )
                send_telegram(msg)
                found.append(symbol)
        except Exception as e:
            print(f"{symbol} xatolik: {e}")

    print(f"Tekshiruv tugadi. Topilgan signallar: {found}")


if __name__ == "__main__":
    main()
