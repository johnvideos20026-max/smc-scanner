import io
import os
import time
import matplotlib.pyplot as plt
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
OTHER_CHAT_ID = os.environ.get("OTHER_CHAT_ID")

TIMEFRAME = "15m"
MIN_QUOTE_VOLUME_24H = 1_000_000
TICKER_24H_URL = "https://data-api.binance.vision/api/v3/ticker/24hr"
KLINES_URL = "https://data-api.binance.vision/api/v3/klines"


def get_targets():
    targets = []
    if CHAT_ID and CHAT_ID.strip():
        targets.append(("Siz", CHAT_ID.strip()))
    if OTHER_CHAT_ID and OTHER_CHAT_ID.strip():
        targets.append(("Boshqa foydalanuvchi", OTHER_CHAT_ID.strip()))
    return targets


def send_telegram(message):
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN topilmadi!")
        return

    targets = get_targets()
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


def send_telegram_photo(image_bytes, caption=""):
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN topilmadi!")
        return

    targets = get_targets()
    if not targets:
        print("CHAT_ID yoki OTHER_CHAT_ID topilmadi!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    for label, target_id in targets:
        files = {"photo": ("btc_status.png", image_bytes, "image/png")}
        data = {"chat_id": target_id, "caption": caption, "parse_mode": "HTML"}
        try:
            image_bytes.seek(0)
            resp = requests.post(url, data=data, files=files, timeout=20)
            print(f"{label} ({target_id}) rasm javobi:", resp.status_code, resp.text)
        except Exception as e:
            print(f"{label} ({target_id}) rasm yuborishda xatolik:", e)
        time.sleep(0.3)


def get_btc_summary_and_chart():
    # 24 soatlik o'zgarish va oxirgi 36 ta 15m sham
    ticker_resp = requests.get(TICKER_24H_URL, params={"symbol": "BTCUSDT"}, timeout=15)
    ticker_resp.raise_for_status()
    ticker = ticker_resp.json()

    klines_resp = requests.get(
        KLINES_URL,
        params={"symbol": "BTCUSDT", "interval": TIMEFRAME, "limit": 37},
        timeout=15,
    )
    klines_resp.raise_for_status()
    raw_klines = klines_resp.json()[:-1]  # faqat yopilgan shamlar

    closes = [float(c[4]) for c in raw_klines]
    current_price = closes[-1]

    # 24 soatlik foiz o'zgarish
    pct_24h = float(ticker.get("priceChangePercent", 0.0))

    # Oxirgi 15m shamga nisbatan foiz o'zgarish
    prev_close = closes[-2] if len(closes) >= 2 and closes[-2] != 0 else current_price
    pct_15m = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0.0

    is_up = pct_24h >= 0
    main_color = "#16a34a" if is_up else "#dc2626"
    bg_color = "#0f172a"
    panel_color = "#1e293b"
    text_color = "#f8fafc"
    muted_color = "#94a3b8"

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(panel_color)

    x_vals = list(range(1, len(closes) + 1))
    ax.plot(x_vals, closes, color=main_color, linewidth=2.2)
    ax.fill_between(x_vals, closes, min(closes), color=main_color, alpha=0.18)

    sign_24h = "+" if pct_24h >= 0 else ""
    sign_15m = "+" if pct_15m >= 0 else ""
    trend_word = "O'SISH" if is_up else "PASAYISH"

    ax.set_title(
        f"BTC/USDT ({TIMEFRAME})  |  ${current_price:,.2f}  |  24h: {sign_24h}{pct_24h:.2f}% ({trend_word})",
        color=text_color,
        fontsize=11,
        fontweight="bold",
        pad=12,
    )
    ax.text(
        0.02,
        0.92,
        f"Oxirgi 15m: {sign_15m}{pct_15m:.2f}%",
        transform=ax.transAxes,
        color=main_color,
        fontsize=10,
        fontweight="bold",
    )

    ax.tick_params(colors=muted_color, labelsize=9)
    ax.grid(True, linestyle="--", alpha=0.2, color=muted_color)
    for spine in ax.spines.values():
        spine.set_color("#334155")

    ax.set_xlabel(f"Oxirgi {len(closes)} ta yopilgan {TIMEFRAME} sham", color=muted_color, fontsize=9)
    ax.set_ylabel("Narx (USDT)", color=muted_color, fontsize=9)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    return current_price, pct_24h, pct_15m, buf


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
        price, pct_24h, pct_15m, chart_buf = get_btc_summary_and_chart()
        s24 = "+" if pct_24h >= 0 else ""
        s15 = "+" if pct_15m >= 0 else ""
        emoji = "📈" if pct_24h >= 0 else "📉"
        caption = (
            f"{emoji} <b>BTC/USDT</b>: <code>${price:,.2f}</code>\n"
            f"📊 24 soat: <b>{s24}{pct_24h:.2f}%</b> | 15m: <b>{s15}{pct_15m:.2f}%</b>\n"
            f"🎯 Topilgan SMC signallar: <b>{len(found)} ta</b>"
        )
        send_telegram_photo(chart_buf, caption=caption)
    except Exception as e:
        print(f"BTC grafik rasmni yuborishda xatolik: {e}")

    print(f"Tekshiruv tugadi. Jami {len(symbols)} ta juftlikdan topilgan signallar: {found}")


if __name__ == "__main__":
    main()
