import os
import time
import logging
import json
import requests
from datetime import datetime, timedelta
import pytz

# ── Config ───────────────────────────────────────────────────────────────────
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY",    "PKSQZQMDJ3XE54T6EROABF3WGW")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "H23Z7Afhw4zzoBmPDQUHeUPiRpyqeFyGQFAHqU8j7EPp")
NEWS_API_KEY      = os.getenv("NEWS_API_KEY",      "164efb308b644a1084fd3b54226342f4")

ALPACA_BASE_URL  = "https://paper-api.alpaca.markets"
ALPACA_DATA_URL  = "https://data.alpaca.markets"

POSITION_MONITOR_MINUTES = 5
TREND_SCAN_MINUTES       = 30
SECONDS_BETWEEN_STOCKS   = 4

# ── Strategy settings ─────────────────────────────────────────────────────────
# Buy when price up >= 0.5% AND RSI between 45-78 AND volume >= 1.1x
# News is a BONUS not a requirement
TAKE_PROFIT_PCT    = 0.04   # sell at +4%
STOP_LOSS_PCT      = 0.02   # sell at -2%
MAX_POSITIONS      = 999    # no limit — buy as many winners as possible
MIN_CASH_RESERVE   = 500    # always keep 00 buffer
POSITION_SIZE_PCT  = 0.20   # use 20% of available cash per trade

POSITIVE_KEYWORDS = [
    "surge","soar","boom","breakthrough","partnership","record","beat",
    "growth","bullish","upgrade","rally","launch","acquire","profit",
    "revenue","earnings beat","all-time high","expand","raises guidance"
]
NEGATIVE_KEYWORDS = [
    "crash","plunge","loss","fraud","lawsuit","bankrupt","recall",
    "downgrade","miss","decline","bearish","sell-off","warning","cut","slowing"
]

HARAM_KEYWORDS = [
    "alcohol","beer","wine","spirits","brewery","distillery","liquor",
    "winery","brewer","whiskey","vodka","rum","gin","champagne",
    "pork","pig","swine","bacon","ham",
    "mortgage","usury","payday loan","interest-bearing",
    "casino","gambling","betting","lottery","poker","sportsbook",
    "tobacco","cigarette","vaping","nicotine",
    "adult entertainment","pornography",
    "weapons manufacturer","arms dealer","munitions"
]
HARAM_SECTORS = [
    "beverages--brewers","beverages--wineries","gambling",
    "tobacco","mortgage finance","mortgage real estate"
]

# Broad watchlist including today's movers
BASE_WATCHLIST = [
    "AAPL","TSLA","NVDA","AMD","META","AMZN","GOOGL","MSFT",
    "PLTR","SOFI","RIVN","LCID","COIN","MSTR","INTC","MU",
    "TXN","URI","ONTO","FTAI","CMCSA","IBM","QQQ","SPY",
    "SOXL","IONQ","OKLO","SMR","ORCL","NOW"
]

STATE_FILE = "state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────
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
    return {"positions": {}, "log": [], "watchlist": BASE_WATCHLIST[:], "halal_cache": {}}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def push_log(state, msg, level="info"):
    entry = {"time": datetime.now().isoformat(), "msg": msg, "level": level}
    state["log"].insert(0, entry)
    state["log"] = state["log"][:200]
    save_state(state)
    if level == "trade": log.info("TRADE: " + msg)
    elif level == "warn": log.warning(msg)
    elif level == "error": log.error(msg)
    else: log.info(msg)

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

# ── Halal check (cached — only runs once per symbol ever) ─────────────────────
def is_halal(symbol, state):
    cache = state.get("halal_cache", {})
    if symbol in cache:
        return cache[symbol]["result"], cache[symbol]["reason"]
    try:
        url = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/" + symbol
        r = requests.get(url, params={"modules": "assetProfile"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        profile = r.json().get("quoteSummary", {}).get("result", [{}])[0]
        asset   = profile.get("assetProfile", {})
        combined = " ".join([
            (asset.get("sector")              or ""),
            (asset.get("industry")            or ""),
            (asset.get("longBusinessSummary") or "")
        ]).lower()
        for hs in HARAM_SECTORS:
            if hs in combined:
                cache[symbol] = {"result": False, "reason": "haram sector: " + hs}
                state["halal_cache"] = cache
                return False, cache[symbol]["reason"]
        for kw in HARAM_KEYWORDS:
            if kw in combined:
                cache[symbol] = {"result": False, "reason": "contains: " + kw}
                state["halal_cache"] = cache
                return False, cache[symbol]["reason"]
        sector = asset.get("sector") or "unknown"
        cache[symbol] = {"result": True, "reason": "halal OK (" + sector + ")"}
        state["halal_cache"] = cache
        return True, cache[symbol]["reason"]
    except Exception as e:
        return True, "halal check skipped"

# ── Price data via Yahoo Finance ──────────────────────────────────────────────
def get_yahoo_data(symbol):
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol
        r = requests.get(url,
            params={"interval": "5m", "range": "1d", "includePrePost": "false"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        result = r.json().get("chart", {}).get("result", [])
        if not result:
            return None
        chart   = result[0]
        meta    = chart.get("meta", {})
        quote   = chart.get("indicators", {}).get("quote", [{}])[0]
        closes  = [c for c in (quote.get("close")  or []) if c is not None]
        volumes = [v for v in (quote.get("volume") or []) if v is not None]
        if len(closes) < 5:
            return None
        current   = closes[-1]
        open_p    = meta.get("regularMarketOpen", closes[0])
        chg_pct   = (current - open_p) / open_p * 100 if open_p else 0
        rsi       = compute_rsi(closes)
        avg_vol   = sum(volumes[:-1]) / max(len(volumes) - 1, 1) if len(volumes) > 1 else 1
        vol_ratio = volumes[-1] / avg_vol if avg_vol else 1
        ma20      = sum(closes[-min(20,len(closes)):]) / min(20, len(closes))
        return {
            "symbol":    symbol,
            "price":     round(current, 2),
            "chg_pct":   round(chg_pct, 2),
            "rsi":       round(rsi, 1),
            "vol_ratio": round(vol_ratio, 2),
            "above_ma":  current > ma20,
        }
    except Exception as e:
        log.warning("Yahoo error " + symbol + ": " + str(e))
        return None

def compute_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0:
        return 100
    return round(100 - (100 / (1 + ag/al)), 1)

# ── News (bonus signal, not required) ────────────────────────────────────────
def get_news_score(symbol):
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": symbol, "apiKey": NEWS_API_KEY, "language": "en",
            "sortBy": "publishedAt", "pageSize": 5,
            "from": (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S")
        }, timeout=8)
        articles = r.json().get("articles", [])
        score = 0
        headline = ""
        for a in articles:
            text = ((a.get("title") or "") + " " + (a.get("description") or "")).lower()
            score += sum(1 for k in POSITIVE_KEYWORDS if k in text)
            score -= sum(1 for k in NEGATIVE_KEYWORDS if k in text)
            if not headline and a.get("title"):
                headline = a["title"]
        return score, headline
    except:
        return 0, ""

# ── Buy decision ──────────────────────────────────────────────────────────────
def should_buy(d, news_score):
    if not d:
        return False, "no data"

    # CORE signals (all 3 must pass)
    price_ok = d["chg_pct"] >= 0.5          # up at least 0.5% today
    rsi_ok   = 42 <= d["rsi"] <= 78         # momentum zone
    vol_ok   = d["vol_ratio"] >= 1.1        # above average volume

    # BONUS signals (nice to have)
    ma_ok    = d["above_ma"]
    news_ok  = news_score >= 1

    core_passed = sum([price_ok, rsi_ok, vol_ok])
    bonus       = sum([ma_ok, news_ok])

    summary = (
        "price(" + str(d["chg_pct"]) + "%)" + ("OK" if price_ok else "NO") + " | " +
        "RSI(" + str(d["rsi"]) + ")" + ("OK" if rsi_ok else "NO") + " | " +
        "vol(" + str(d["vol_ratio"]) + "x)" + ("OK" if vol_ok else "NO") + " | " +
        "MA" + ("OK" if ma_ok else "NO") + " | " +
        "news(" + str(news_score) + ")" + ("OK" if news_ok else "NO")
    )

    # Buy if all 3 core signals pass (news + MA are bonuses)
    if core_passed == 3:
        return True, "CORE 3/3 + bonus " + str(bonus) + "/2 | " + summary
    return False, str(core_passed) + "/3 core | " + summary

# ── Account & positions ───────────────────────────────────────────────────────
def get_account():
    return alpaca_get("/v2/account")

def get_open_positions():
    try:
        return alpaca_get("/v2/positions")
    except:
        return []

def place_buy(symbol, price, state):
    try:
        cash = float(get_account().get("cash", 0))
        usable = cash - MIN_CASH_RESERVE
        if usable < price:
            push_log(state, "Not enough cash ($" + str(int(cash)) + ") for " + symbol, "warn")
            return False
        # Use 20% of available cash per trade, but never more than available
        trade_amount = min(usable * POSITION_SIZE_PCT, usable)
        qty = int(trade_amount / price)
        if qty < 1:
            return False
        order = alpaca_post("/v2/orders", {
            "symbol": symbol, "qty": qty,
            "side": "buy", "type": "market", "time_in_force": "day"
        })
        state["positions"][symbol] = {
            "buy_price": price, "qty": qty,
            "order_id": order.get("id"),
            "bought_at": datetime.now().isoformat()
        }
        total = round(qty * price, 2)
        push_log(state, "BUY " + str(qty) + " x " + symbol + " @ $" + str(price) + " (total $" + str(total) + ")", "trade")
        return True
    except Exception as e:
        push_log(state, "Buy error " + symbol + ": " + str(e), "error")
        return False

def place_sell(symbol, qty, reason, state):
    try:
        alpaca_post("/v2/orders", {
            "symbol": symbol, "qty": qty,
            "side": "sell", "type": "market", "time_in_force": "day"
        })
        state["positions"].pop(symbol, None)
        push_log(state, "SELL " + str(qty) + " x " + symbol + " — " + reason, "trade")
    except Exception as e:
        push_log(state, "Sell error " + symbol + ": " + str(e), "error")

# ── Core loops ────────────────────────────────────────────────────────────────
def scan_and_trade(state):
    watchlist = state.get("watchlist", BASE_WATCHLIST)
    positions = get_open_positions()
    held = {p["symbol"] for p in positions}

    push_log(state, "🔍 Scanning " + str(len(watchlist)) + " stocks | held: " + str(len(held)) + " | cash: $" + str(int(float(get_account().get("cash",0)))))
    bought = 0

    for symbol in watchlist:
        if symbol in held:
            continue

        # Halal filter (cached after first check)
        halal, reason = is_halal(symbol, state)
        if not halal:
            push_log(state, "🚫 " + symbol + " — " + reason, "warn")
            continue

        # Price data
        data = get_yahoo_data(symbol)
        if not data:
            time.sleep(2)
            continue

        # News (bonus only)
        news_score, headline = get_news_score(symbol)

        # Decision
        buy, reason = should_buy(data, news_score)

        if buy:
            push_log(state, "✅ BUY SIGNAL — " + symbol + " @ $" + str(data["price"]) + " | " + reason)
            if headline:
                push_log(state, "   📰 " + headline)
            if place_buy(symbol, data["price"], state):
                held.add(symbol)
                bought += 1
            time.sleep(2)
        else:
            push_log(state, "⏭ " + symbol + " $" + str(data["price"]) + " | " + reason)

        time.sleep(SECONDS_BETWEEN_STOCKS)

    if bought == 0:
        push_log(state, "💤 Cycle done — no buys. Market conditions: " +
                 ("mostly down today" if True else "scanning"))

def monitor_positions(state):
    positions = get_open_positions()
    if not positions:
        push_log(state, "📊 No open positions")
        return
    push_log(state, "📊 Checking " + str(len(positions)) + " position(s)...")
    for p in positions:
        sym   = p["symbol"]
        cur   = float(p["current_price"])
        entry = float(p["avg_entry_price"])
        qty   = int(p["qty"])
        pnl   = (cur - entry) / entry

        if pnl >= TAKE_PROFIT_PCT:
            place_sell(sym, qty, "Take profit +" + str(round(pnl*100,1)) + "%", state)
        elif pnl <= -STOP_LOSS_PCT:
            place_sell(sym, qty, "Stop loss " + str(round(pnl*100,1)) + "%", state)
        else:
            news_score, _ = get_news_score(sym)
            if news_score <= -3:
                place_sell(sym, qty, "Bad news score " + str(news_score), state)
            else:
                push_log(state, "   " + sym + " P&L " + str(round(pnl*100,2)) + "% — holding")

def refresh_watchlist(state):
    try:
        movers = alpaca_get("/v1beta1/screener/stocks/most-actives?by=trades&top=20",
                            base=ALPACA_DATA_URL)
        symbols  = [m["symbol"] for m in movers.get("most_actives", [])]
        combined = list(dict.fromkeys(BASE_WATCHLIST + symbols))[:35]
        state["watchlist"] = combined
        push_log(state, "📋 Watchlist: " + str(len(combined)) + " stocks")
        save_state(state)
    except Exception as e:
        log.warning("Watchlist refresh failed: " + str(e))

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    state = load_state()
    push_log(state, "🚀 Bot v5 — needs price+RSI+volume to buy. News is a bonus.")
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
        if now - last_monitor >= POSITION_MONITOR_MINUTES * 60:
            monitor_positions(state)
            last_monitor = now
        scan_and_trade(state)

if __name__ == "__main__":
    main()
