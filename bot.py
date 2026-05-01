import os, time, logging, json, requests
from datetime import datetime, timedelta
import pytz

# ── Config ────────────────────────────────────────────────────────────────────
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY",    "PKSQZQMDJ3XE54T6EROABF3WGW")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "H23Z7Afhw4zzoBmPDQUHeUPiRpyqeFyGQFAHqU8j7EPp")
NEWS_API_KEY      = os.getenv("NEWS_API_KEY",      "164efb308b644a1084fd3b54226342f4")

ALPACA_BASE = "https://paper-api.alpaca.markets"
ALPACA_DATA = "https://data.alpaca.markets"

POSITION_MONITOR_MIN = 5
TREND_SCAN_MIN       = 30
SLEEP_BETWEEN        = 4

MAX_POSITIONS   = 10       # max 10 stocks held at once
MIN_TRADE_USD   = 2000     # minimum $2,000 per trade
MIN_CASH_BUFFER = 500      # always keep $500 untouched
TAKE_PROFIT_PCT = 0.05     # sell at +5%
STOP_LOSS_PCT   = 0.025    # sell at -2.5%

POSITIVE_KEYWORDS = [
    "surge","soar","boom","breakthrough","partnership","record","beat",
    "growth","bullish","upgrade","rally","launch","acquire","profit",
    "revenue","earnings beat","all-time high","expand","raises guidance",
    "strong","outperform","buy rating","price target raised"
]
NEGATIVE_KEYWORDS = [
    "crash","plunge","loss","fraud","lawsuit","bankrupt","recall",
    "downgrade","miss","decline","bearish","sell-off","warning","cut",
    "slowing","weak","disappoints","reduces guidance","below expectations"
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

BASE_WATCHLIST = [
    "AAPL","TSLA","NVDA","AMD","META","AMZN","GOOGL","MSFT",
    "PLTR","SOFI","RIVN","LCID","COIN","MSTR","INTC","MU",
    "TXN","CMCSA","IBM","ORCL","NOW","IONQ","OKLO","SMR",
    "SOXL","QQQ","ONTO","FTAI","CRWD","PANW","SNOW","DDOG",
    "ABNB","UBER","LYFT","SHOP","SQ","PYPL","RBLX","U"
]

STATE_FILE = "state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Alpaca helpers ────────────────────────────────────────────────────────────
def ah():
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Content-Type": "application/json"
    }

def a_get(path, base=None, params=None):
    r = requests.get((base or ALPACA_BASE) + path, headers=ah(), params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def a_post(path, body):
    r = requests.post(ALPACA_BASE + path, headers=ah(), json=body, timeout=10)
    r.raise_for_status()
    return r.json()

def a_delete(path):
    r = requests.delete(ALPACA_BASE + path, headers=ah(), timeout=10)
    return r.status_code

# ── State ─────────────────────────────────────────────────────────────────────
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
    state["log"] = state["log"][:300]
    save_state(state)
    getattr(log, "warning" if level=="warn" else "error" if level=="error" else "info")(msg)

# ── Market clock ──────────────────────────────────────────────────────────────
def is_market_open():
    try:
        return a_get("/v1/clock").get("is_open", False)
    except:
        et  = pytz.timezone("America/New_York")
        now = datetime.now(et)
        if now.weekday() >= 5: return False
        return now.replace(hour=9,minute=30,second=0) <= now <= now.replace(hour=16,minute=0,second=0)

# ── Halal filter (cached forever) ────────────────────────────────────────────
def is_halal(symbol, state):
    cache = state.setdefault("halal_cache", {})
    if symbol in cache:
        return cache[symbol]["ok"], cache[symbol]["reason"]
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v10/finance/quoteSummary/" + symbol,
            params={"modules": "assetProfile"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        )
        asset = r.json().get("quoteSummary",{}).get("result",[{}])[0].get("assetProfile",{})
        blob  = " ".join([
            asset.get("sector",""), asset.get("industry",""),
            asset.get("longBusinessSummary","")
        ]).lower()
        for hs in HARAM_SECTORS:
            if hs in blob:
                cache[symbol] = {"ok": False, "reason": "haram sector: "+hs}
                return False, cache[symbol]["reason"]
        for kw in HARAM_KEYWORDS:
            if kw in blob:
                cache[symbol] = {"ok": False, "reason": "contains: "+kw}
                return False, cache[symbol]["reason"]
        sector = asset.get("sector","unknown")
        cache[symbol] = {"ok": True, "reason": "halal ("+sector+")"}
        return True, cache[symbol]["reason"]
    except:
        return True, "halal check skipped"

# ── Yahoo Finance price data ───────────────────────────────────────────────────
def get_data(symbol):
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol,
            params={"interval":"5m","range":"1d","includePrePost":"false"},
            headers={"User-Agent":"Mozilla/5.0"}, timeout=10
        )
        res = r.json().get("chart",{}).get("result",[])
        if not res: return None
        chart   = res[0]
        meta    = chart.get("meta",{})
        q       = chart.get("indicators",{}).get("quote",[{}])[0]
        closes  = [c for c in (q.get("close")  or []) if c is not None]
        volumes = [v for v in (q.get("volume") or []) if v is not None]
        if len(closes) < 5: return None

        price     = closes[-1]
        open_p    = meta.get("regularMarketOpen", closes[0])
        prev      = meta.get("chartPreviousClose", closes[0])
        chg_pct   = (price - open_p) / open_p * 100 if open_p else 0
        day_chg   = (price - prev)   / prev   * 100 if prev   else 0
        rsi       = calc_rsi(closes)
        avg_vol   = sum(volumes[:-1]) / max(len(volumes)-1,1) if len(volumes)>1 else 1
        vol_ratio = volumes[-1] / avg_vol if avg_vol else 1
        ma20      = sum(closes[-min(20,len(closes)):]) / min(20,len(closes))

        # Momentum score 0-10 (used to size trades and rank stocks)
        momentum = 0
        if chg_pct >= 0.5:  momentum += 2
        if chg_pct >= 1.5:  momentum += 1
        if chg_pct >= 3.0:  momentum += 1
        if 45<=rsi<=78:     momentum += 2
        if vol_ratio>=1.2:  momentum += 2
        if price > ma20:    momentum += 1
        if day_chg >= 1.0:  momentum += 1

        return {
            "symbol": symbol, "price": round(price,2),
            "chg_pct": round(chg_pct,2), "day_chg": round(day_chg,2),
            "rsi": round(rsi,1), "vol_ratio": round(vol_ratio,2),
            "above_ma": price > ma20, "momentum": momentum
        }
    except Exception as e:
        log.warning("Yahoo error "+symbol+": "+str(e))
        return None

def calc_rsi(closes, period=14):
    if len(closes) < period+1: return 50
    gains = [max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
    losses= [max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
    ag = sum(gains[-period:])/period
    al = sum(losses[-period:])/period
    if al == 0: return 100
    return round(100-(100/(1+ag/al)),1)

# ── News score ────────────────────────────────────────────────────────────────
def news_score(symbol):
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": symbol, "apiKey": NEWS_API_KEY, "language": "en",
            "sortBy": "publishedAt", "pageSize": 5,
            "from": (datetime.utcnow()-timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S")
        }, timeout=8)
        articles = r.json().get("articles",[])
        score = 0
        headline = ""
        for a in articles:
            text = ((a.get("title") or "")+" "+(a.get("description") or "")).lower()
            score += sum(1 for k in POSITIVE_KEYWORDS if k in text)
            score -= sum(1 for k in NEGATIVE_KEYWORDS if k in text)
            if not headline and a.get("title"): headline = a["title"]
        return score, headline
    except:
        return 0, ""

# ── Trade sizing based on momentum score ─────────────────────────────────────
def calc_trade_size(momentum, available_cash):
    """
    momentum 0-10 → trade size
    Higher momentum = bigger bet, minimum $2000
    """
    portfolio_val = 100000  # base reference
    try:
        portfolio_val = float(a_get("/v2/account").get("portfolio_value", 100000))
    except: pass

    # Scale: momentum 3=3%, 5=5%, 7=7%, 9=9%, 10=10%
    pct = min(0.03 + (momentum - 3) * 0.01, 0.10)
    pct = max(pct, 0.02)  # floor at 2%
    amount = portfolio_val * pct
    amount = max(amount, MIN_TRADE_USD)  # never below $2000
    amount = min(amount, available_cash - MIN_CASH_BUFFER)  # never more than cash allows
    return round(amount, 2)

# ── Account helpers ───────────────────────────────────────────────────────────
def get_account():
    return a_get("/v2/account")

def get_positions():
    try: return a_get("/v2/positions")
    except: return []

# ── Buy ───────────────────────────────────────────────────────────────────────
def place_buy(symbol, data, state):
    try:
        acct  = get_account()
        cash  = float(acct.get("cash", 0))
        if cash - MIN_CASH_BUFFER < MIN_TRADE_USD:
            push_log(state, "💰 Not enough cash ($"+str(int(cash))+") — skipping "+symbol, "warn")
            return False
        amount = calc_trade_size(data["momentum"], cash)
        qty    = int(amount / data["price"])
        if qty < 1: return False
        order = a_post("/v2/orders", {
            "symbol": symbol, "qty": qty,
            "side": "buy", "type": "market", "time_in_force": "day"
        })
        total = round(qty * data["price"], 2)
        state["positions"][symbol] = {
            "buy_price": data["price"], "qty": qty,
            "order_id": order.get("id"),
            "bought_at": datetime.now().isoformat(),
            "momentum": data["momentum"]
        }
        push_log(state,
            "🟢 BUY "+str(qty)+" x "+symbol+" @ $"+str(data["price"])+
            " | total $"+str(total)+" | momentum "+str(data["momentum"])+"/10", "trade")
        return True
    except Exception as e:
        push_log(state, "Buy error "+symbol+": "+str(e), "error")
        return False

# ── Sell ──────────────────────────────────────────────────────────────────────
def place_sell(symbol, qty, reason, state):
    try:
        a_post("/v2/orders", {
            "symbol": symbol, "qty": qty,
            "side": "sell", "type": "market", "time_in_force": "day"
        })
        state["positions"].pop(symbol, None)
        push_log(state, "🔴 SELL "+str(qty)+" x "+symbol+" — "+reason, "trade")
        return True
    except Exception as e:
        push_log(state, "Sell error "+symbol+": "+str(e), "error")
        return False

# ── Monitor open positions ────────────────────────────────────────────────────
def monitor_positions(state):
    positions = get_positions()
    if not positions:
        push_log(state, "📊 No open positions")
        return
    push_log(state, "📊 Monitoring "+str(len(positions))+" position(s)...")
    for p in positions:
        sym   = p["symbol"]
        cur   = float(p["current_price"])
        entry = float(p["avg_entry_price"])
        qty   = int(p["qty"])
        pnl   = (cur - entry) / entry

        if pnl >= TAKE_PROFIT_PCT:
            place_sell(sym, qty, "Take profit +"+str(round(pnl*100,1))+"%", state)
        elif pnl <= -STOP_LOSS_PCT:
            place_sell(sym, qty, "Stop loss "+str(round(pnl*100,1))+"%", state)
        else:
            ns, _ = news_score(sym)
            if ns <= -3:
                place_sell(sym, qty, "Bad news score "+str(ns), state)
            else:
                push_log(state, "   "+sym+": "+str(round(pnl*100,2))+"% P&L | holding")

# ── Swap worst position if better stock found ─────────────────────────────────
def maybe_swap(new_data, held_positions, state):
    """
    If we're at max positions and new stock has better momentum
    than our worst holding, sell the worst and buy the new one.
    """
    if not held_positions: return False

    # Find worst performing position by P&L
    worst     = None
    worst_pnl = float("inf")
    for p in held_positions:
        pnl = (float(p["current_price"]) - float(p["avg_entry_price"])) / float(p["avg_entry_price"])
        if pnl < worst_pnl:
            worst_pnl = pnl
            worst     = p

    if worst is None: return False

    worst_momentum = state.get("positions",{}).get(worst["symbol"],{}).get("momentum", 5)

    # Only swap if new stock has meaningfully better momentum AND worst is negative
    if new_data["momentum"] > worst_momentum + 2 and worst_pnl < -0.005:
        push_log(state,
            "🔄 SWAP — selling "+worst["symbol"]+" ("+str(round(worst_pnl*100,1))+"% P&L, momentum "+str(worst_momentum)+
            ") for "+new_data["symbol"]+" (momentum "+str(new_data["momentum"])+")", "trade")
        qty = int(worst["qty"])
        if place_sell(worst["symbol"], qty, "Swapped for better opportunity", state):
            time.sleep(1)
            return True  # signal to buy new stock
    return False

# ── Main scan loop ────────────────────────────────────────────────────────────
def scan_and_trade(state):
    positions = get_positions()
    held      = {p["symbol"]: p for p in positions}
    n_held    = len(held)

    try:
        cash = float(get_account().get("cash", 0))
    except:
        cash = 0

    push_log(state, "🔍 Scanning "+str(len(state.get('watchlist', BASE_WATCHLIST)))+
             " stocks | holding: "+str(n_held)+"/"+str(MAX_POSITIONS)+
             " | cash: $"+str(int(cash)))

    candidates = []  # (momentum, data) for buy candidates

    for symbol in state.get("watchlist", BASE_WATCHLIST):
        # Halal filter
        halal, reason = is_halal(symbol, state)
        if not halal:
            push_log(state, "🚫 "+symbol+" — "+reason, "warn")
            time.sleep(1)
            continue

        # Get price data
        data = get_data(symbol)
        if not data:
            time.sleep(2)
            continue

        # Get news (bonus)
        ns, headline = news_score(symbol)
        if ns >= 1: data["momentum"] = min(data["momentum"]+1, 10)
        if ns <= -2: data["momentum"] = max(data["momentum"]-2, 0)

        # Log what we found
        tag = "🔴" if data["chg_pct"] < 0 else "🟡" if data["chg_pct"] < 1 else "🟢"
        push_log(state,
            tag+" "+symbol+" $"+str(data["price"])+" | "+
            str(data["chg_pct"])+"% | RSI "+str(data["rsi"])+
            " | vol "+str(data["vol_ratio"])+"x | momentum "+str(data["momentum"])+"/10"+
            (" | 📰 "+headline[:60] if headline else ""))

        # Already holding this one — skip buying more
        if symbol in held:
            time.sleep(SLEEP_BETWEEN)
            continue

        # Must have momentum >= 5 to be a buy candidate
        if data["momentum"] >= 5:
            candidates.append(data)

        time.sleep(SLEEP_BETWEEN)

    # Sort candidates by momentum (best first)
    candidates.sort(key=lambda x: x["momentum"], reverse=True)

    for data in candidates:
        symbol = data["symbol"]
        if symbol in held: continue

        # Reload positions in case something changed
        positions = get_positions()
        held      = {p["symbol"]: p for p in positions}
        n_held    = len(held)

        if n_held < MAX_POSITIONS:
            # Slots available — just buy
            push_log(state, "✅ BUY CANDIDATE: "+symbol+" momentum "+str(data["momentum"])+"/10")
            if headline:
                push_log(state, "   📰 "+headline[:80])
            place_buy(symbol, data, state)
            held[symbol] = True
            time.sleep(1)
        else:
            # At max — try to swap worst position
            swapped = maybe_swap(data, list(held.values()) if isinstance(list(held.values())[0], dict) else positions, state)
            if swapped:
                place_buy(symbol, data, state)
                time.sleep(1)
            else:
                push_log(state, "⏸ "+symbol+" momentum "+str(data["momentum"])+"/10 — no slot, not worth swapping")

# ── Watchlist refresh ─────────────────────────────────────────────────────────
def refresh_watchlist(state):
    try:
        movers  = a_get("/v1beta1/screener/stocks/most-actives?by=trades&top=20", base=ALPACA_DATA)
        symbols = [m["symbol"] for m in movers.get("most_actives",[])]
        combined= list(dict.fromkeys(BASE_WATCHLIST + symbols))[:40]
        state["watchlist"] = combined
        push_log(state, "📋 Watchlist: "+str(len(combined))+" stocks")
        save_state(state)
    except Exception as e:
        log.warning("Watchlist refresh failed: "+str(e))

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    state = load_state()
    push_log(state, "🚀 Bot FINAL — max 10 positions, momentum sizing, smart swap, min $2k trades")
    last_monitor = 0
    last_trend   = 0

    while True:
        now = time.time()
        if not is_market_open():
            log.info("Market closed — sleeping 5 min")
            time.sleep(300)
            continue
        if now - last_trend >= TREND_SCAN_MIN * 60:
            refresh_watchlist(state)
            last_trend = now
        if now - last_monitor >= POSITION_MONITOR_MIN * 60:
            monitor_positions(state)
            last_monitor = now
        scan_and_trade(state)

if __name__ == "__main__":
    main()
