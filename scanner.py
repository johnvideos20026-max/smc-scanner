import os
import time
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
OTHER_CHAT_ID = os.environ.get("OTHER_CHAT_ID")

TIMEFRAME = "15m"
MIN_QUOTE_VOLUME_24H = 1_000_000
TICKER_24H_URL = "https://data-api.binance.vision/api/v3/ticker/24hr"
KLINES_URL = "https://data-api.binance.vision/api/v3/klines"


def send_telegram(message):
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN topilmadi!")
        return

    targets = []
    if CHAT_ID:
        targets.append(("Siz", CHAT_ID.strip()))
    if OTHER_CHAT_ID:
        targets.append(("Boshqa foydalanuvchi", OTHER_CHAT_ID.strip()))

    if not targets:
        print("CHAT_ID yoki OTHER_CHAT_ID topilmadi!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for label, target_id in targets:
        payload = {"chat_id": target_id, "text": message, "parse_mode": "HTML"}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            print(f"{label} ({target_id}) javobi:", resp.status_code, resp.text)
        except Exception as e:
            print(f"{label} ({target_id}) yuborishda xatolik:", e)
        time.sleep(0.3)


def get_btc_price():
    params = {"symbol": "BTCUSDT", "interval": TIMEFRAME, "limit": 2}
    resp = requests.get(KLINES_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # Oxirgi yopilgan shamning yopilish narxi
    closed_price = float(data[-2][4])
    return f"{closed_price:.2f}".rstrip("0").rstrip(".")


def get_all_usdt_symbols():
    resp = requests.get(TICKER_24H_URL, timeout=15)
    resp.raise_for_status()
    tickers = resp.json()

    excluded_suffixes = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
    symbols = []
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        if sym.endswith(excluded_suffixes):
            continue
        try:
            quote_vol = float(t.get("quoteVolume", 0))
        except (TypeError, ValueError):
            quote_vol = 0.0
        if quote_vol >= MIN_QUOTE_VOLUME_24H:
            symbols.append((sym, quote_vol))

    symbols.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in symbols]


def get_candles(symbol, interval="15m", limit=50):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    resp = requests.get(KLINES_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    candles = []
    for c in data[:-1]:
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

    lookback = candles[-24:-4]
    range_high = max(c["high"] for c in lookback)
    range_low = min(c["low"] for c in lookback)
    range_size = range_high - range_low
    if range_size == 0:
        return None

    recent = candles[-4:]
    c0, c1, c2, c3 = recent[0], recent[1], recent[2], recent[3]

    swept_low = min(c0["low"], c1["low"]) < range_low
    swing_high = max(c["high"] for c in candles[-10:-3])
    bullish_mss = c2["close"] > swing_high or c3["close"] > swing_high
    bullish_fvg = c3["low"] > c1["high"]

    if swept_low and bullish_mss and bullish_fvg:
        return {
            "direction": "🟢 LONG (Bullish SMC)",
            "price": c3["close"],
            "liquidity": f"{range_low:.6f}".rstrip("0").rstrip("."),
            "fvg": f"{c1['high']:.6f} - {c3['low']:.6f}"
        }

    swept_high = max(c0["high"], c1["high"]) > range_high
    swing_low = min(c["low"] for c in candles[-10:-3])
    bearish_mss = c2["close"] < swing_low or c3["close"] < swing_low
    bearish_fvg = c3["high"] < c1["low"]

    if swept_high and bearish_mss and bearish_fvg:
        return {
            "direction": "🔴 SHORT (Bearish SMC)",
            "price": c3["close"],
            "liquidity": f"{range_high:.6f}".rstrip("0").rstrip("."),
            "fvg": f"{c3['high']:.6f} - {c1['low']:.6f}"
        }

    return None


def main():
    symbols = get_all_usdt_symbols()
    print(f"Jami tekshiriladigan USDT juftliklar soni: {len(symbols)}")

    found = []
    for idx, symbol in enumerate(symbols, start=1):
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

        if idx % 20 == 0:
            time.sleep(0.5)

    try:
        btc_price = get_btc_price()
        status_msg = f"₿ BTC: <code>{btc_price}</code> USDT | Signallar: <b>{len(found)}</b>"
        send_telegram(status_msg)
    except Exception as e:
        print(f"BTC narxini olishda xatolik: {e}")

    print(f"Tekshiruv tugadi. Jami {len(symbols)} ta juftlikdan topilgan signallar: {found}")


if __name__ == "__main__":
    main()
