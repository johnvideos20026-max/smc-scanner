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
    ticker_resp = requests.get(TICKER_24H_URL, params={"symbol": "BTCUSDT"}, timeout=15)
    ticker_resp.raise_for_status()
    ticker = ticker_resp.json()

    klines_resp = requests.get(
        KLINES_URL,
        params={"symbol": "BTCUSDT", "interval": TIMEFRAME, "limit": 37},
        timeout=15,
    )
    klines_resp.raise_for_status()
    raw_klines = klines_resp.json()[:-1]

    closes = [float(c[4]) for c in raw_klines]
    current_price = closes[-1]

    pct_24h = float(ticker.get("priceChangePercent", 0.0))
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
            "volume": float(c[5]),
        })
    return candles


def analyze_srt_and_probabilities(candles, smc_direction=None):
    if len(candles) < 25:
        return None

    last = candles[-1]
    prev = candles[-2]
    price = last["close"]

    # Support va Resistance darajalari (oxirgi 25 ta yopilgan shamdan)
    window = candles[-25:-1]
    support = min(c["low"] for c in window)
    resistance = max(c["high"] for c in window)
    span = resistance - support
    if span <= 0:
        return None

    # Narxning diapazondagi pozitsiyasi (0.0 = supportda, 1.0 = resistanceda)
    pos_ratio = max(0.0, min(1.0, (price - support) / span))

    # Hajm reaksiyasi
    avg_vol = sum(c["volume"] for c in candles[-15:-1]) / 14.0
    vol_boost = 6.0 if avg_vol > 0 and last["volume"] > avg_vol * 1.25 else 0.0

    # Oxirgi sham yo'nalishi
    last_green = last["close"] >= last["open"]
    prev_green = prev["close"] >= prev["open"]

    up_score = 50.0
    srt_note = "Neytral zona"

    # Support yaqinida reaksiya (o'sish ehtimolini oshiradi)
    if pos_ratio <= 0.25:
        up_score += 14.0
        srt_note = "Support yaqinida (reaksiya zonasi)"
        if last_green:
            up_score += 6.0 + vol_boost
            srt_note = "Supportdan yuqoriga qaytish (Bullish SRT)"
    # Resistance yaqinida reaksiya (tushish ehtimolini oshiradi)
    elif pos_ratio >= 0.75:
        up_score -= 14.0
        srt_note = "Resistance yaqinida (qarshilik zonasi)"
        if not last_green:
            up_score -= 6.0 + vol_boost
            srt_note = "Resistancedan pastga qaytish (Bearish SRT)"
    else:
        if last_green and prev_green:
            up_score += 4.0
            srt_note = "O'rta zonada yuqori impuls"
        elif not last_green and not prev_green:
            up_score -= 4.0
            srt_note = "O'rta zonada pastki impuls"

    # SMC signal bilan moslik
    if smc_direction == "LONG":
        up_score += 10.0
    elif smc_direction == "SHORT":
        up_score -= 10.0

    up_pct = int(round(max(15.0, min(85.0, up_score))))
    down_pct = 100 - up_pct

    return {
        "support": f"{support:.6f}".rstrip("0").rstrip("."),
        "resistance": f"{resistance:.6f}".rstrip("0").rstrip("."),
        "srt_note": srt_note,
        "up_pct": up_pct,
        "down_pct": down_pct,
    }


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
            "side": "LONG",
            "direction": "🟢 LONG (Bullish SMC)",
            "price": c3["close"],
            "liquidity": f"{range_low:.6f}".rstrip("0").rstrip("."),
            "fvg": f"{c1['high']:.6f} - {c3['low']:.6f}",
        }

    swept_high = max(c0["high"], c1["high"]) > range_high
    swing_low = min(c["low"] for c in candles[-10:-3])
    bearish_mss = c2["close"] < swing_low or c3["close"] < swing_low
    bearish_fvg = c3["high"] < c1["low"]

    if swept_high and bearish_mss and bearish_fvg:
        return
