import os
import time
import logging
import json
import requests
from datetime import datetime, timedelta
import pytz

# ── Config ──────────────────────────────────────────────────────────────────
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY",    "PKSQZQMDJ3XE54T6EROABF3WGW")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "H23Z7Afhw4zzoBmPDQUHeUPiRpyqeFyGQFAHqU8j7EPp")
NEWS_API_KEY      = os.getenv("NEWS_API_KEY",      "164efb308b644a1084fd3b54226342f4")

ALPACA_BASE_URL   = "https://paper-api.alpaca.markets"
ALPACA_DATA_URL   = "https://data.alpaca.markets"

SCAN_INTERVAL_MINUTES     = 15
POSITION_MONITOR_MINUTES  = 5
TREND_SCAN_MINUTES        = 30

TAKE_PROFIT_PCT   = 0.10
STOP_LOSS_PCT     = 0.05
MAX_POSITIONS     = 5
POSITION_SIZE_USD = 1000

POSITIVE_KEYWORDS = [
    "surge", "soar", "boom", "breakthrough", "partnership", "record",
    "beat", "growth", "bullish", "upgrade", "rally", "launch", "acquire",
    "profit", "revenue", "earnings beat", "all-time high", "expand"
]
NEGATIVE_KEYWORDS = [
    "crash", "plunge", "loss", "fraud", "lawsuit", "bankrupt", "recall",
    "downgrade", "miss", "decline", "bearish", "sell-off", "warning", "cut"
]

# ── Halal Filter ─────────────────────────────────────────────────────────────
HARAM_KEYWORDS = [
    # Alcohol
    "alcohol", "beer", "wine", "spirits", "brewery", "distillery", "liquor",
    "winery", "brewer", "whiskey", "vodka", "rum", "gin", "champagne",
    # Pork
    "pork", "pig", "swine", "bacon", "ham", "hog farming",
    # Interest / conventional finance
    "mortgage", "usury", "payday loan", "interest-bearing",
    # Gambling
    "casino", "gambling", "betting", "lottery", "poker", "sportsbook",
    # Tobacco
    "tobacco", "cigarette", "vaping", "e-cigarette", "nicotine",
    # Adult entertainment
    "adult entertainment", "pornography",
    # Weapons
    "weapons manufacturer", "arms dealer", "munitions"
]

# Sectors to skip entirely
HARAM_SECTORS = [
    "beverages—brewers", "beverages—wineries", "gambling",
    "tobacco", "mortgage finance", "mortgage real estate"
]

BASE_WATCHLIST = [
    "AAPL","TSLA","NVDA","AMD","META","AMZN","GOOGL","MSFT",
    "PLTR","SOFI","RIVN","LCID","GME","AMC","COIN","MSTR"
]

STATE_FILE = "state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────────────

def alpaca_headers():
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Content-Type": "application/json"
    }

def alpaca_get(path, base=ALPACA_BASE_URL, params=None):
    r = requests.get(f"{base}{path}", headers=alpaca_headers(), params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def alpaca_post(path, body):
    r = requests.post(f"{ALPACA_BASE_URL}{path}", headers=alpaca_headers(), json=body, timeout=10)
    r.raise_for_status()
    return r.json()

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"positions": {}, "log": [], "watchlist": BASE_WATCHLIST[:]}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def push_log(state, msg, level="info"):
    entry = {"time": datetime.now().isoformat(), "msg": msg, "level": level}
    state["log"].insert(0, entry)
    state["log"] = state["log"][:200]
    save_state(state)
    if level == "info":    log.info(msg)
    elif level == "warn":  log.warning(msg)
    elif level == "error": log.error(msg)
    elif level == "trade": log.info(f"🟢 TRADE: {msg}")

# ── Market hours ──────────────────────────────────────────────────────────────

def is_market_open():
    try:
        data = alpaca_get("/v1/clock")
        return data.get("is_open", False)
    except Exception:
        et = pytz.timezone("America/New_York")
        now = datetime.now(et)
        if now.weekday() >= 5:
            return False
        open_t  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
        close_t = now.replace(hour=16, minute=0,  second=0, microsecond=0)
        return open_t <= now <= close_t

# ── Halal check ───────────────────────────────────────────────────────────────

def is_halal(symbol):
    """
    Fetches company profile from a free API and checks against
    haram keywords in the description, sector, and industry.
    Returns (is_halal: bool, reason: str)
    """
    try:
        # Use Yahoo Finance unofficial summary endpoint
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
        params = {"modules": "assetProfile,summaryProfile"}
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()

        profile = data.get("quoteSummary", {}).get("result", [{}])[0]
        asset   = profile.get("assetProfile", {})

        sector      = (asset.get("sector")      or "").lower()
        industry    = (asset.get("industry")    or "").lower()
        description = (asset.get("longBusinessSummary") or "").lower()

        combined = f"{sector} {industry} {description}"

        # Check haram sectors first
        for hs in HARAM_SECTORS:
            if hs in combined:
                return False, f"Haram sector/industry: {hs}"

        # Check haram keywords
        for kw in HARAM_KEYWORDS:
            if kw in combined:
                return False, f"Haram keyword detected: '{kw}'"

        return True, f"Passed halal check (sector: {sector or 'unknown'}, industry: {industry or 'unknown'})"

    except Exception as e:
        log.warning(f"Halal check failed for {symbol}: {e} — allowing by default")
        return True, "Halal check skipped (API error)"

# ── News sentiment ────────────────────────────────────────────────────────────

def get_news_sentiment(symbol):
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": symbol,
            "apiKey": NEWS_API_KEY,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "from": (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
        }
        r = requests.get(url, params=params, timeout=10)
        articles = r.json().get("articles", [])
        if not articles:
            return 0, []

        score = 0
        headlines = []
        for a in articles:
            title = (a.get("title") or "").lower()
            desc  = (a.get("description") or "").lower()
            text  = title + " " + desc
            pos   = sum(1 for k in POSITIVE_KEYWORDS if k in text)
            neg   = sum(1 for k in NEGATIVE_KEYWORDS if k in text)
            score += pos - neg
            if a.get("title"):
                headlines.append(a["title"])

        return score, headlines[:3]
    except Exception as e:
        log.warning(f"News error for {symbol}: {e}")
        return 0, []

# ── Price & technicals ────────────────────────────────────────────────────────

def get_bars(symbol, limit=50):
    try:
        data = alpaca_get(
            f"/v2/stocks/{symbol}/bars",
            base=ALPACA_DATA_URL,
            params={"timeframe": "15Min", "limit": limit, "feed": "iex"}
        )
        return data.get("bars", [])
    except Exception as e:
        log.warning(f"Bars error for {symbol}: {e}")
        return []

def compute_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def analyse_stock(symbol):
    bars = get_bars(symbol, limit=60)
    if len(bars) < 20:
        return None

    closes  = [b["c"] for b in bars]
    volumes = [b["v"] for b in bars]
    current_price = closes[-1]
    open_price    = bars[-1]["o"]

    price_change_pct = (current_price - open_price) / open_price * 100
    rsi              = compute_rsi(closes)
    avg_volume       = sum(volumes[:-1]) / max(len(volumes) - 1, 1)
    volume_ratio     = volumes[-1] / avg_volume if avg_volume else 1
    ma20             = sum(closes[-20:]) / 20

    return {
        "symbol":       symbol,
        "price":        round(current_price, 2),
        "change_pct":   round(price_change_pct, 2),
        "rsi":          round(rsi, 1),
        "volume_ratio": round(volume_ratio, 2),
        "above_ma20":   current_price > ma20,
        "ma20":         round(ma20, 2),
    }

def should_buy(analysis, news_score):
    if analysis is None:
        return False, "No data"
    reasons = []
    if news_score >= 2:
        reasons.append(f"positive news score ({news_score})")
    if analysis["change_pct"] >= 2:
        reasons.append(f"up {analysis['change_pct']}% today")
    if 50 <= analysis["rsi"] <= 72:
        reasons.append(f"RSI {analysis['rsi']} (rising momentum)")
    if analysis["volume_ratio"] >= 1.5:
        reasons.append(f"volume {analysis['volume_ratio']}x above average")
    if analysis["above_ma20"]:
        reasons.append("above 20-period MA")

    if len(reasons) >= 3:
        return True, " | ".join(reasons)
    return False, f"Only {len(reasons)}/3 signals met"

# ── Trading actions ───────────────────────────────────────────────────────────

def get_account():
    return alpaca_get("/v2/account")

def get_open_positions():
    try:
        return alpaca_get("/v2/positions")
    except Exception:
        return []

def place_buy(symbol, price, state):
    try:
        account = get_account()
        cash    = float(account.get("cash", 0))
        if cash < POSITION_SIZE_USD:
            push_log(state, f"Not enough cash (${cash:.0f}) to buy {symbol}", "warn")
            return False

        qty = int(POSITION_SIZE_USD / price)
        if qty < 1:
            return False

        order = alpaca_post("/v2/orders", {
            "symbol": symbol, "qty": qty,
            "side": "buy", "type": "market", "time_in_force": "day"
        })
        state["positions"][symbol] = {
            "buy_price": price, "qty": qty,
            "order_id":  order.get("id"),
            "bought_at": datetime.now().isoformat()
        }
        push_log(state, f"BUY {qty} x {symbol} @ ${price}", "trade")
        return True
    except Exception as e:
        push_log(state, f"Buy error {symbol}: {e}", "error")
        return False

def place_sell(symbol, qty, reason, state):
    try:
        alpaca_post("/v2/orders", {
            "symbol": symbol, "qty": qty,
            "side": "sell", "type": "market", "time_in_force": "day"
        })
        state["positions"].pop(symbol, None)
        push_log(state, f"SELL {qty} x {symbol} — {reason}", "trade")
    except Exception as e:
        push_log(state, f"Sell error {symbol}: {e}", "error")

# ── Core loops ────────────────────────────────────────────────────────────────

def scan_and_trade(state):
    push_log(state, "🔍 Scanning watchlist for opportunities...")
    positions = get_open_positions()
    held = {p["symbol"] for p in positions}

    if len(held) >= MAX_POSITIONS:
        push_log(state, f"Max positions ({MAX_POSITIONS}) reached, skipping scan")
        return

    for symbol in state.get("watchlist", BASE_WATCHLIST):
        if symbol in held:
            continue

        # ── Halal check FIRST ──────────────────────────────────────────────
        halal, halal_reason = is_halal(symbol)
        if not halal:
            push_log(state, f"🚫 {symbol} blocked — {halal_reason}", "warn")
            continue
        else:
            push_log(state, f"☑️  {symbol} halal check passed — {halal_reason}")

        # ── Technical + news analysis ──────────────────────────────────────
        analysis = analyse_stock(symbol)
        if not analysis:
            continue

        news_score, headlines = get_news_sentiment(symbol)
        buy, reason = should_buy(analysis, news_score)

        if buy:
            push_log(state, f"✅ {symbol} — {reason}")
            if headlines:
                push_log(state, f"   📰 {headlines[0]}")
            place_buy(symbol, analysis["price"], state)
            time.sleep(1)
        else:
            push_log(state, f"⏭ {symbol} skipped — {reason}")

def monitor_positions(state):
    positions = get_open_positions()
    if not positions:
        return

    push_log(state, f"📊 Monitoring {len(positions)} open position(s)...")
    for p in positions:
        symbol    = p["symbol"]
        cur_price = float(p["current_price"])
        avg_price = float(p["avg_entry_price"])
        qty       = int(p["qty"])
        pnl_pct   = (cur_price - avg_price) / avg_price

        if pnl_pct >= TAKE_PROFIT_PCT:
            place_sell(symbol, qty, f"Take profit +{pnl_pct*100:.1f}%", state)
        elif pnl_pct <= -STOP_LOSS_PCT:
            place_sell(symbol, qty, f"Stop loss {pnl_pct*100:.1f}%", state)
        else:
            news_score, _ = get_news_sentiment(symbol)
            if news_score <= -3:
                place_sell(symbol, qty, f"Negative news (score {news_score})", state)
            else:
                push_log(state, f"   {symbol}: {pnl_pct*100:+.1f}% | news={news_score}")

def refresh_watchlist(state):
    try:
        movers = alpaca_get("/v1beta1/screener/stocks/most-actives?by=trades&top=20", base=ALPACA_DATA_URL)
        symbols = [m["symbol"] for m in movers.get("most_actives", [])]
        combined = list(dict.fromkeys(BASE_WATCHLIST + symbols))[:30]
        state["watchlist"] = combined
        push_log(state, f"📋 Watchlist refreshed: {len(combined)} stocks")
        save_state(state)
    except Exception as e:
        log.warning(f"Watchlist refresh failed: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    state = load_state()
    push_log(state, "🚀 Stock agent started")

    last_scan    = 0
    last_monitor = 0
    last_trend   = 0

    while True:
        now = time.time()

        if not is_market_open():
            log.info("Market closed — sleeping 5 min")
            time.sleep(300)
            continue

        if now - last_trend >= TREND_SCAN_MINUTES * 60:
            refresh_watchlist(state)
            last_trend = now

        if now - last_scan >= SCAN_INTERVAL_MINUTES * 60:
            scan_and_trade(state)
            last_scan = now

        if now - last_monitor >= POSITION_MONITOR_MINUTES * 60:
            monitor_positions(state)
            last_monitor = now

        time.sleep(30)

if __name__ == "__main__":
    main()
