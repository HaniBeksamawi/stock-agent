import os
import json
from flask import Flask, jsonify, render_template_string
from datetime import datetime

app = Flask(__name__)
STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"positions": {}, "log": [], "watchlist": []}

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
    --bg: #0a0d12;
    --surface: #111620;
    --border: #1e2535;
    --accent: #00ff88;
    --accent2: #0af;
    --red: #ff4466;
    --yellow: #ffd166;
    --text: #e2e8f0;
    --muted: #4a5568;
    --card-bg: #141926;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif; min-height:100vh; }

  header {
    display:flex; align-items:center; justify-content:space-between;
    padding:1.2rem 2rem; border-bottom:1px solid var(--border);
    background:var(--surface);
  }
  .logo { font-family:'Space Mono',monospace; font-size:1.1rem; color:var(--accent); letter-spacing:2px; }
  .status-pill {
    display:flex; align-items:center; gap:.5rem;
    background:#0f1f17; border:1px solid var(--accent);
    padding:.35rem .9rem; border-radius:999px; font-size:.8rem; color:var(--accent);
  }
  .dot { width:8px; height:8px; border-radius:50%; background:var(--accent); animation:pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

  .grid { display:grid; grid-template-columns:repeat(4,1fr); gap:1rem; padding:1.5rem 2rem; }
  @media(max-width:900px){ .grid{grid-template-columns:repeat(2,1fr);} }

  .stat-card {
    background:var(--card-bg); border:1px solid var(--border);
    border-radius:12px; padding:1.2rem 1.4rem;
  }
  .stat-label { font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:1px; margin-bottom:.4rem; }
  .stat-value { font-family:'Space Mono',monospace; font-size:1.6rem; color:var(--text); }
  .stat-value.green { color:var(--accent); }
  .stat-value.red { color:var(--red); }
  .stat-value.blue { color:var(--accent2); }

  .main { display:grid; grid-template-columns:1fr 380px; gap:1rem; padding:0 2rem 2rem; }
  @media(max-width:1100px){ .main{grid-template-columns:1fr;} }

  .panel {
    background:var(--card-bg); border:1px solid var(--border);
    border-radius:12px; overflow:hidden;
  }
  .panel-header {
    padding:.9rem 1.4rem; border-bottom:1px solid var(--border);
    font-family:'Space Mono',monospace; font-size:.8rem;
    color:var(--accent2); letter-spacing:1px; text-transform:uppercase;
  }

  table { width:100%; border-collapse:collapse; }
  th { padding:.7rem 1.2rem; text-align:left; font-size:.7rem; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; border-bottom:1px solid var(--border); }
  td { padding:.75rem 1.2rem; font-size:.88rem; border-bottom:1px solid #0d1017; }
  tr:last-child td { border-bottom:none; }
  tr:hover td { background:#0f1420; }

  .badge {
    display:inline-block; padding:.2rem .6rem; border-radius:4px;
    font-size:.72rem; font-family:'Space Mono',monospace;
  }
  .badge.buy  { background:#0f2b1a; color:var(--accent); border:1px solid #1a4a2a; }
  .badge.sell { background:#2b0f17; color:var(--red);    border:1px solid #4a1a22; }
  .badge.hold { background:#1a1f2b; color:var(--accent2);border:1px solid #2a3045; }

  .log-panel { height:420px; overflow-y:auto; padding:1rem; }
  .log-entry { display:flex; gap:.8rem; padding:.5rem 0; border-bottom:1px solid #0d1017; font-size:.8rem; align-items:flex-start; }
  .log-time { color:var(--muted); font-family:'Space Mono',monospace; font-size:.68rem; white-space:nowrap; padding-top:2px; }
  .log-msg { flex:1; line-height:1.4; }
  .log-msg.trade { color:var(--accent); }
  .log-msg.warn  { color:var(--yellow); }
  .log-msg.error { color:var(--red); }

  .empty { padding:2rem; text-align:center; color:var(--muted); font-size:.85rem; }

  .refresh-bar { text-align:right; padding:.6rem 2rem; color:var(--muted); font-size:.75rem; }
</style>
</head>
<body>

<header>
  <div class="logo">⚡ STOCK AGENT</div>
  <div class="status-pill"><div class="dot"></div> LIVE — PAPER TRADING</div>
</header>

<div class="grid" id="stats">
  <div class="stat-card"><div class="stat-label">Portfolio Value</div><div class="stat-value blue" id="portfolio">—</div></div>
  <div class="stat-card"><div class="stat-label">Cash Available</div><div class="stat-value green" id="cash">—</div></div>
  <div class="stat-card"><div class="stat-label">Open Positions</div><div class="stat-value" id="positions">—</div></div>
  <div class="stat-card"><div class="stat-label">Today P&L</div><div class="stat-value" id="pnl">—</div></div>
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
async function fetchData() {
  try {
    const [stateRes, accountRes] = await Promise.all([
      fetch('/api/state'),
      fetch('/api/account')
    ]);
    const state   = await stateRes.json();
    const account = await accountRes.json();

    // Stats
    const portfolio = parseFloat(account.portfolio_value || 0);
    const cash      = parseFloat(account.cash || 0);
    const pnl       = parseFloat(account.equity || 0) - 100000;
    document.getElementById('portfolio').textContent = '$' + portfolio.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
    document.getElementById('cash').textContent      = '$' + cash.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
    document.getElementById('pnl').textContent       = (pnl >= 0 ? '+' : '') + '$' + pnl.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
    document.getElementById('pnl').className         = 'stat-value ' + (pnl >= 0 ? 'green' : 'red');

    // Positions
    const posRes  = await fetch('/api/positions');
    const posData = await posRes.json();
    document.getElementById('positions').textContent = posData.length;

    if (posData.length) {
      let html = '<table><thead><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>Current</th><th>P&L</th><th>Status</th></tr></thead><tbody>';
      posData.forEach(p => {
        const entry   = parseFloat(p.avg_entry_price);
        const current = parseFloat(p.current_price);
        const pct     = ((current - entry) / entry * 100).toFixed(2);
        const cls     = pct >= 0 ? 'green' : 'red';
        html += `<tr>
          <td><strong>${p.symbol}</strong></td>
          <td>${p.qty}</td>
          <td>$${entry.toFixed(2)}</td>
          <td>$${current.toFixed(2)}</td>
          <td style="color:var(--${cls})">${pct >= 0 ? '+' : ''}${pct}%</td>
          <td><span class="badge hold">HOLDING</span></td>
        </tr>`;
      });
      html += '</tbody></table>';
      document.getElementById('positions-table').innerHTML = html;
    } else {
      document.getElementById('positions-table').innerHTML = '<div class="empty">No open positions</div>';
    }

    // Log
    const logs = state.log || [];
    if (logs.length) {
      let html = '';
      logs.slice(0, 60).forEach(e => {
        const t   = new Date(e.time).toLocaleTimeString();
        const cls = e.level === 'trade' ? 'trade' : e.level === 'warn' ? 'warn' : e.level === 'error' ? 'error' : '';
        html += `<div class="log-entry"><span class="log-time">${t}</span><span class="log-msg ${cls}">${e.msg}</span></div>`;
      });
      document.getElementById('log-panel').innerHTML = html;
    }

    document.getElementById('last-update').textContent = 'Last update: ' + new Date().toLocaleTimeString();
  } catch(e) {
    console.error(e);
  }
}

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
    import requests as req
    try:
        r = req.get(
            "https://paper-api.alpaca.markets/v2/account",
            headers={
                "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", "PKSQZQMDJ3XE54T6EROABF3WGW"),
                "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY", "H23Z7Afhw4zzoBmPDQUHeUPiRpyqeFyGQFAHqU8j7EPp")
            }, timeout=10
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/positions")
def api_positions():
    import requests as req
    try:
        r = req.get(
            "https://paper-api.alpaca.markets/v2/positions",
            headers={
                "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", "PKSQZQMDJ3XE54T6EROABF3WGW"),
                "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY", "H23Z7Afhw4zzoBmPDQUHeUPiRpyqeFyGQFAHqU8j7EPp")
            }, timeout=10
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify([])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
