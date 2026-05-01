import os
import json
import requests as req
from flask import Flask, jsonify, render_template_string, request
from datetime import datetime

app = Flask(__name__)
STATE_FILE = "state.json"

ALPACA_KEY    = lambda: os.getenv("ALPACA_API_KEY",    "PKSQZQMDJ3XE54T6EROABF3WGW")
ALPACA_SECRET = lambda: os.getenv("ALPACA_SECRET_KEY", "H23Z7Afhw4zzoBmPDQUHeUPiRpyqeFyGQFAHqU8j7EPp")
ALPACA_BASE   = "https://paper-api.alpaca.markets"

def alpaca_headers():
    return {
        "APCA-API-KEY-ID": ALPACA_KEY(),
        "APCA-API-SECRET-KEY": ALPACA_SECRET(),
        "Content-Type": "application/json"
    }

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"positions": {}, "log": [], "watchlist": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def push_log(msg, level="trade"):
    state = load_state()
    state["log"].insert(0, {"time": datetime.now().isoformat(), "msg": msg, "level": level})
    state["log"] = state["log"][:200]
    save_state(state)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Stock Agent Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap" rel="stylesheet"/>
<style>
  :root {
    --bg:#0a0d12; --surface:#111620; --border:#1e2535;
    --accent:#00ff88; --accent2:#0af; --red:#ff4466;
    --yellow:#ffd166; --text:#e2e8f0; --muted:#4a5568; --card-bg:#141926;
  }
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh;}

  header{display:flex;align-items:center;justify-content:space-between;padding:1.2rem 2rem;border-bottom:1px solid var(--border);background:var(--surface);}
  .logo{font-family:'Space Mono',monospace;font-size:1.1rem;color:var(--accent);letter-spacing:2px;}
  .status-pill{display:flex;align-items:center;gap:.5rem;background:#0f1f17;border:1px solid var(--accent);padding:.35rem .9rem;border-radius:999px;font-size:.8rem;color:var(--accent);}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--accent);animation:pulse 1.5s infinite;}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

  .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;padding:1.5rem 2rem;}
  @media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr);}}
  .stat-card{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:1.2rem 1.4rem;}
  .stat-label{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:.4rem;}
  .stat-value{font-family:'Space Mono',monospace;font-size:1.6rem;color:var(--text);}
  .stat-value.green{color:var(--accent);}
  .stat-value.red{color:var(--red);}
  .stat-value.blue{color:var(--accent2);}

  /* Manual Trade Panel */
  .trade-bar{padding:0 2rem 1rem;}
  .trade-panel{background:var(--card-bg);border:1px solid var(--accent2);border-radius:12px;padding:1.2rem 1.4rem;}
  .trade-title{font-family:'Space Mono',monospace;font-size:.8rem;color:var(--accent2);letter-spacing:1px;text-transform:uppercase;margin-bottom:1rem;}
  .trade-form{display:flex;gap:.8rem;align-items:center;flex-wrap:wrap;}
  .trade-input{
    background:#0d1117;border:1px solid var(--border);color:var(--text);
    padding:.6rem 1rem;border-radius:8px;font-family:'Space Mono',monospace;
    font-size:.9rem;width:130px;outline:none;text-transform:uppercase;
  }
  .trade-input:focus{border-color:var(--accent2);}
  .trade-input-qty{width:90px;}
  .trade-lookup{
    background:#0d1a2e;border:1px solid var(--accent2);color:var(--accent2);
    padding:.6rem 1rem;border-radius:8px;font-size:.85rem;cursor:pointer;
  }
  .trade-lookup:hover{background:#0f2040;}
  .trade-price-info{font-family:'Space Mono',monospace;font-size:.85rem;color:var(--yellow);min-width:120px;}
  .btn-buy{
    background:#0f2b1a;border:1px solid var(--accent);color:var(--accent);
    padding:.6rem 1.4rem;border-radius:8px;font-size:.9rem;cursor:pointer;font-weight:600;
  }
  .btn-buy:hover{background:#1a4a2a;}
  .btn-buy:disabled{opacity:.4;cursor:not-allowed;}
  .btn-sell{
    background:#2b0f17;border:1px solid var(--red);color:var(--red);
    padding:.6rem 1.4rem;border-radius:8px;font-size:.9rem;cursor:pointer;font-weight:600;
  }
  .btn-sell:hover{background:#4a1a22;}
  .btn-sell:disabled{opacity:.4;cursor:not-allowed;}
  .trade-msg{font-size:.8rem;margin-top:.6rem;min-height:1rem;}
  .trade-msg.ok{color:var(--accent);}
  .trade-msg.err{color:var(--red);}

  .main{display:grid;grid-template-columns:1fr 380px;gap:1rem;padding:0 2rem 2rem;}
  @media(max-width:1100px){.main{grid-template-columns:1fr;}}
  .panel{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;overflow:hidden;}
  .panel-header{padding:.9rem 1.4rem;border-bottom:1px solid var(--border);font-family:'Space Mono',monospace;font-size:.8rem;color:var(--accent2);letter-spacing:1px;text-transform:uppercase;}

  table{width:100%;border-collapse:collapse;}
  th{padding:.7rem 1.2rem;text-align:left;font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid var(--border);}
  td{padding:.75rem 1.2rem;font-size:.88rem;border-bottom:1px solid #0d1017;}
  tr:last-child td{border-bottom:none;}
  tr:hover td{background:#0f1420;}

  .badge{display:inline-block;padding:.2rem .6rem;border-radius:4px;font-size:.72rem;font-family:'Space Mono',monospace;}
  .badge.manual{background:#1a1000;color:var(--yellow);border:1px solid #4a3000;}
  .badge.auto{background:#0f2b1a;color:var(--accent);border:1px solid #1a4a2a;}
  .badge.hold{background:#1a1f2b;color:var(--accent2);border:1px solid #2a3045;}

  .btn-sell-pos{background:#2b0f17;border:1px solid var(--red);color:var(--red);padding:.2rem .7rem;border-radius:6px;font-size:.75rem;cursor:pointer;}
  .btn-sell-pos:hover{background:#4a1a22;}

  .log-panel{height:420px;overflow-y:auto;padding:1rem;}
  .log-entry{display:flex;gap:.8rem;padding:.5rem 0;border-bottom:1px solid #0d1017;font-size:.8rem;align-items:flex-start;}
  .log-time{color:var(--muted);font-family:'Space Mono',monospace;font-size:.68rem;white-space:nowrap;padding-top:2px;}
  .log-msg{flex:1;line-height:1.4;}
  .log-msg.trade{color:var(--accent);}
  .log-msg.warn{color:var(--yellow);}
  .log-msg.error{color:var(--red);}

  .empty{padding:2rem;text-align:center;color:var(--muted);font-size:.85rem;}
  .refresh-bar{text-align:right;padding:.6rem 2rem;color:var(--muted);font-size:.75rem;}
</style>
</head>
<body>

<header>
  <div class="logo">⚡ STOCK AGENT</div>
  <div class="status-pill"><div class="dot"></div> LIVE — PAPER TRADING</div>
</header>

<div class="grid">
  <div class="stat-card"><div class="stat-label">Portfolio Value</div><div class="stat-value blue" id="portfolio">—</div></div>
  <div class="stat-card"><div class="stat-label">Cash Available</div><div class="stat-value green" id="cash">—</div></div>
  <div class="stat-card"><div class="stat-label">Open Positions</div><div class="stat-value" id="pos-count">—</div></div>
  <div class="stat-card"><div class="stat-label">Today P&L</div><div class="stat-value" id="pnl">—</div></div>
</div>

<!-- Manual Trade Panel -->
<div class="trade-bar">
  <div class="trade-panel">
    <div class="trade-title">🖐 Manual Trade</div>
    <div class="trade-form">
      <input class="trade-input" id="trade-symbol" placeholder="SYMBOL" maxlength="6" oninput="this.value=this.value.toUpperCase()"/>
      <button class="trade-lookup" onclick="lookupPrice()">Look up price</button>
      <span class="trade-price-info" id="price-info">—</span>
      <input class="trade-input trade-input-qty" id="trade-qty" placeholder="Qty" type="number" min="1" value="1"/>
      <button class="btn-buy" id="btn-buy" onclick="manualBuy()" disabled>BUY</button>
      <button class="btn-sell" id="btn-sell" onclick="manualSell()" disabled>SELL</button>
    </div>
    <div class="trade-msg" id="trade-msg"></div>
  </div>
</div>

<div class="main">
  <div>
    <div class="panel">
      <div class="panel-header">Open Positions</div>
      <div id="positions-table"><div class="empty">No open positions</div></div>
    </div>
  </div>
  <div>
    <div class="panel">
      <div class="panel-header">Agent Activity Log</div>
      <div class="log-panel" id="log-panel"><div class="empty">Waiting for activity...</div></div>
    </div>
  </div>
</div>

<div class="refresh-bar">Auto-refreshes every 15s &nbsp;|&nbsp; <span id="last-update">—</span></div>

<script>
let currentPrice = null;

async function lookupPrice() {
  const sym = document.getElementById('trade-symbol').value.trim().toUpperCase();
  if (!sym) return;
  document.getElementById('price-info').textContent = 'Looking up...';
  document.getElementById('btn-buy').disabled = true;
  document.getElementById('btn-sell').disabled = true;
  try {
    const r = await fetch('/api/quote?symbol=' + sym);
    const d = await r.json();
    if (d.price) {
      currentPrice = d.price;
      document.getElementById('price-info').textContent = sym + ' @ $' + d.price.toFixed(2);
      document.getElementById('btn-buy').disabled  = false;
      document.getElementById('btn-sell').disabled = false;
      setMsg('', '');
    } else {
      document.getElementById('price-info').textContent = 'Not found';
      setMsg('Could not find ' + sym, 'err');
    }
  } catch(e) {
    document.getElementById('price-info').textContent = 'Error';
    setMsg('Lookup failed', 'err');
  }
}

async function manualBuy() {
  const sym = document.getElementById('trade-symbol').value.trim().toUpperCase();
  const qty = parseInt(document.getElementById('trade-qty').value) || 1;
  if (!sym || !currentPrice) return;
  setMsg('Placing BUY order...', 'ok');
  try {
    const r = await fetch('/api/manual_trade', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({symbol: sym, qty: qty, side: 'buy'})
    });
    const d = await r.json();
    if (d.ok) {
      setMsg('BUY ' + qty + ' x ' + sym + ' placed successfully!', 'ok');
      fetchData();
    } else {
      setMsg('Error: ' + (d.error || 'unknown'), 'err');
    }
  } catch(e) {
    setMsg('Request failed', 'err');
  }
}

async function manualSell() {
  const sym = document.getElementById('trade-symbol').value.trim().toUpperCase();
  const qty = parseInt(document.getElementById('trade-qty').value) || 1;
  if (!sym) return;
  setMsg('Placing SELL order...', 'ok');
  try {
    const r = await fetch('/api/manual_trade', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({symbol: sym, qty: qty, side: 'sell'})
    });
    const d = await r.json();
    if (d.ok) {
      setMsg('SELL ' + qty + ' x ' + sym + ' placed successfully!', 'ok');
      fetchData();
    } else {
      setMsg('Error: ' + (d.error || 'unknown'), 'err');
    }
  } catch(e) {
    setMsg('Request failed', 'err');
  }
}

async function sellPosition(symbol, qty) {
  if (!confirm('Sell all ' + qty + ' shares of ' + symbol + '?')) return;
  try {
    const r = await fetch('/api/manual_trade', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({symbol, qty, side: 'sell'})
    });
    const d = await r.json();
    if (d.ok) { fetchData(); }
    else { alert('Sell error: ' + (d.error || 'unknown')); }
  } catch(e) { alert('Request failed'); }
}

function setMsg(msg, cls) {
  const el = document.getElementById('trade-msg');
  el.textContent = msg;
  el.className = 'trade-msg ' + cls;
}

async function fetchData() {
  try {
    const [stateRes, accountRes, posRes] = await Promise.all([
      fetch('/api/state'),
      fetch('/api/account'),
      fetch('/api/positions')
    ]);
    const state   = await stateRes.json();
    const account = await accountRes.json();
    const posData = await posRes.json();

    const portfolio = parseFloat(account.portfolio_value || 0);
    const cash      = parseFloat(account.cash || 0);
    const pnl       = parseFloat(account.equity || 0) - 100000;

    document.getElementById('portfolio').textContent = '$' + portfolio.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
    document.getElementById('cash').textContent      = '$' + cash.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
    document.getElementById('pos-count').textContent = Array.isArray(posData) ? posData.length : 0;
    document.getElementById('pnl').textContent       = (pnl >= 0 ? '+' : '') + '$' + Math.abs(pnl).toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
    document.getElementById('pnl').className         = 'stat-value ' + (pnl >= 0 ? 'green' : 'red');

    if (Array.isArray(posData) && posData.length) {
      let html = '<table><thead><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>Current</th><th>P&L</th><th>Type</th><th>Action</th></tr></thead><tbody>';
      posData.forEach(p => {
        const entry   = parseFloat(p.avg_entry_price);
        const current = parseFloat(p.current_price);
        const qty     = parseInt(p.qty);
        const pct     = ((current - entry) / entry * 100).toFixed(2);
        const cls     = pct >= 0 ? 'green' : 'red';
        const manual  = (state.positions || {})[p.symbol]?.manual;
        html += '<tr>' +
          '<td><strong>' + p.symbol + '</strong></td>' +
          '<td>' + qty + '</td>' +
          '<td>$' + entry.toFixed(2) + '</td>' +
          '<td>$' + current.toFixed(2) + '</td>' +
          '<td style="color:var(--' + cls + ')">' + (pct >= 0 ? '+' : '') + pct + '%</td>' +
          '<td><span class="badge ' + (manual ? 'manual' : 'auto') + '">' + (manual ? 'MANUAL' : 'AUTO') + '</span></td>' +
          '<td><button class="btn-sell-pos" onclick="sellPosition(\'' + p.symbol + '\',' + qty + ')">SELL</button></td>' +
        '</tr>';
      });
      html += '</tbody></table>';
      document.getElementById('positions-table').innerHTML = html;
    } else {
      document.getElementById('positions-table').innerHTML = '<div class="empty">No open positions</div>';
    }

    const logs = state.log || [];
    if (logs.length) {
      let html = '';
      logs.slice(0, 80).forEach(e => {
        const t   = new Date(e.time).toLocaleTimeString();
        const cls = e.level === 'trade' ? 'trade' : e.level === 'warn' ? 'warn' : e.level === 'error' ? 'error' : '';
        html += '<div class="log-entry"><span class="log-time">' + t + '</span><span class="log-msg ' + cls + '">' + e.msg + '</span></div>';
      });
      document.getElementById('log-panel').innerHTML = html;
    }

    document.getElementById('last-update').textContent = 'Last update: ' + new Date().toLocaleTimeString();
  } catch(e) { console.error(e); }
}

// Enter key on symbol input triggers lookup
document.getElementById('trade-symbol').addEventListener('keydown', e => {
  if (e.key === 'Enter') lookupPrice();
});

fetchData();
setInterval(fetchData, 15000);
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route("/api/state")
def api_state():
    return jsonify(load_state())

@app.route("/api/account")
def api_account():
    try:
        r = req.get(f"{ALPACA_BASE}/v2/account", headers=alpaca_headers(), timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/positions")
def api_positions():
    try:
        r = req.get(f"{ALPACA_BASE}/v2/positions", headers=alpaca_headers(), timeout=10)
        return jsonify(r.json())
    except Exception:
        return jsonify([])

@app.route("/api/quote")
def api_quote():
    symbol = request.args.get("symbol", "").upper()
    if not symbol:
        return jsonify({"error": "no symbol"})
    try:
        # Try Yahoo Finance for live price
        r = req.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol,
            params={"interval": "1m", "range": "1d"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=8
        )
        result = r.json().get("chart", {}).get("result", [])
        if result:
            meta  = result[0].get("meta", {})
            price = meta.get("regularMarketPrice") or meta.get("previousClose")
            if price:
                return jsonify({"symbol": symbol, "price": price})
        return jsonify({"error": "not found"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/manual_trade", methods=["POST"])
def api_manual_trade():
    data   = request.get_json()
    symbol = (data.get("symbol") or "").upper()
    qty    = int(data.get("qty") or 1)
    side   = data.get("side", "buy")

    if not symbol or qty < 1:
        return jsonify({"ok": False, "error": "invalid input"})

    try:
        r = req.post(
            f"{ALPACA_BASE}/v2/orders",
            headers=alpaca_headers(),
            json={"symbol": symbol, "qty": qty, "side": side,
                  "type": "market", "time_in_force": "day"},
            timeout=10
        )
        if r.status_code in (200, 201):
            # Log it and mark as manual in state
            state = load_state()
            msg   = ("MANUAL BUY " if side == "buy" else "MANUAL SELL ") + str(qty) + " x " + symbol
            state["log"].insert(0, {"time": datetime.now().isoformat(), "msg": msg, "level": "trade"})
            if side == "buy":
                state["positions"][symbol] = {
                    "qty": qty, "manual": True,
                    "bought_at": datetime.now().isoformat()
                }
            elif side == "sell" and symbol in state.get("positions", {}):
                state["positions"].pop(symbol, None)
            state["log"] = state["log"][:200]
            save_state(state)
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": r.json().get("message", "order failed")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
