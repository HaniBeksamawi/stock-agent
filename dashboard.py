import os, json, requests as req
from flask import Flask, jsonify, render_template_string
from datetime import datetime

app = Flask(__name__)
STATE_FILE = "state.json"

def alpaca_headers():
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY","PKSQZQMDJ3XE54T6EROABF3WGW"),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY","H23Z7Afhw4zzoBmPDQUHeUPiRpyqeFyGQFAHqU8j7EPp")
    }

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: return json.load(f)
    return {"positions":{}, "log":[], "watchlist":[]}

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Stock Agent</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap" rel="stylesheet"/>
<style>
:root{--bg:#0a0d12;--surface:#111620;--border:#1e2535;--accent:#00ff88;--accent2:#0af;--red:#ff4466;--yellow:#ffd166;--text:#e2e8f0;--muted:#4a5568;--card:#141926;}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh;}
header{display:flex;align-items:center;justify-content:space-between;padding:1.2rem 2rem;border-bottom:1px solid var(--border);background:var(--surface);}
.logo{font-family:'Space Mono',monospace;font-size:1.1rem;color:var(--accent);letter-spacing:2px;}
.pill{display:flex;align-items:center;gap:.5rem;background:#0f1f17;border:1px solid var(--accent);padding:.35rem .9rem;border-radius:999px;font-size:.8rem;color:var(--accent);}
.dot{width:8px;height:8px;border-radius:50%;background:var(--accent);animation:pulse 1.5s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;padding:1.5rem 2rem;}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr);}}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.2rem 1.4rem;}
.label{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:.4rem;}
.val{font-family:'Space Mono',monospace;font-size:1.6rem;}
.val.green{color:var(--accent);}.val.red{color:var(--red);}.val.blue{color:var(--accent2);}
.main{display:grid;grid-template-columns:1fr 380px;gap:1rem;padding:0 2rem 2rem;}
@media(max-width:1100px){.main{grid-template-columns:1fr;}}
.panel{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;}
.ph{padding:.9rem 1.4rem;border-bottom:1px solid var(--border);font-family:'Space Mono',monospace;font-size:.8rem;color:var(--accent2);letter-spacing:1px;text-transform:uppercase;}
table{width:100%;border-collapse:collapse;}
th{padding:.7rem 1.2rem;text-align:left;font-size:.7rem;color:var(--muted);text-transform:uppercase;border-bottom:1px solid var(--border);}
td{padding:.75rem 1.2rem;font-size:.88rem;border-bottom:1px solid #0d1017;}
tr:last-child td{border-bottom:none;}
tr:hover td{background:#0f1420;}
.log-wrap{height:450px;overflow-y:auto;padding:1rem;}
.le{display:flex;gap:.8rem;padding:.5rem 0;border-bottom:1px solid #0d1017;font-size:.8rem;}
.lt{color:var(--muted);font-family:'Space Mono',monospace;font-size:.68rem;white-space:nowrap;padding-top:2px;}
.lm{flex:1;line-height:1.4;}
.lm.trade{color:var(--accent);}.lm.warn{color:var(--yellow);}.lm.error{color:var(--red);}
.empty{padding:2rem;text-align:center;color:var(--muted);font-size:.85rem;}
.bar{text-align:right;padding:.6rem 2rem;color:var(--muted);font-size:.75rem;}
</style>
</head>
<body>
<header>
  <div class="logo">⚡ STOCK AGENT</div>
  <div class="pill"><div class="dot"></div> LIVE — PAPER TRADING</div>
</header>
<div class="grid">
  <div class="card"><div class="label">Portfolio Value</div><div class="val blue" id="pv">—</div></div>
  <div class="card"><div class="label">Cash Available</div><div class="val green" id="cash">—</div></div>
  <div class="card"><div class="label">Open Positions</div><div class="val" id="pc">—</div></div>
  <div class="card"><div class="label">Today P&L</div><div class="val" id="pnl">—</div></div>
</div>
<div class="main">
  <div>
    <div class="panel">
      <div class="ph">Open Positions</div>
      <div id="pos"><div class="empty">No open positions</div></div>
    </div>
  </div>
  <div>
    <div class="panel">
      <div class="ph">Agent Activity Log</div>
      <div class="log-wrap" id="log"><div class="empty">Waiting for activity...</div></div>
    </div>
  </div>
</div>
<div class="bar">Auto-refresh every 15s &nbsp;|&nbsp; <span id="upd">—</span></div>
<script>
async function refresh(){
  try{
    const [s,a,p]=await Promise.all([fetch('/api/state'),fetch('/api/account'),fetch('/api/positions')]);
    const state=await s.json(), acct=await a.json(), pos=await p.json();
    const pv=parseFloat(acct.portfolio_value||0), cash=parseFloat(acct.cash||0), pnl=pv-100000;
    const fmt=n=>'$'+Math.abs(n).toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2});
    document.getElementById('pv').textContent=fmt(pv);
    document.getElementById('cash').textContent=fmt(cash);
    document.getElementById('pc').textContent=Array.isArray(pos)?pos.length:0;
    const pel=document.getElementById('pnl');
    pel.textContent=(pnl>=0?'+':'-')+fmt(pnl);
    pel.className='val '+(pnl>=0?'green':'red');
    if(Array.isArray(pos)&&pos.length){
      let h='<table><thead><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>Current</th><th>P&L</th></tr></thead><tbody>';
      pos.forEach(p=>{
        const e=parseFloat(p.avg_entry_price),c=parseFloat(p.current_price),pct=((c-e)/e*100).toFixed(2),cl=pct>=0?'green':'red';
        h+='<tr><td><strong>'+p.symbol+'</strong></td><td>'+p.qty+'</td><td>$'+e.toFixed(2)+'</td><td>$'+c.toFixed(2)+'</td><td style="color:var(--'+cl+')">'+(pct>=0?'+':'')+pct+'%</td></tr>';
      });
      h+='</tbody></table>';
      document.getElementById('pos').innerHTML=h;
    } else document.getElementById('pos').innerHTML='<div class="empty">No open positions</div>';
    const logs=state.log||[];
    if(logs.length){
      let h='';
      logs.slice(0,80).forEach(e=>{
        const t=new Date(e.time).toLocaleTimeString(),cls=e.level==='trade'?'trade':e.level==='warn'?'warn':e.level==='error'?'error':'';
        h+='<div class="le"><span class="lt">'+t+'</span><span class="lm '+cls+'">'+e.msg+'</span></div>';
      });
      document.getElementById('log').innerHTML=h;
    }
    document.getElementById('upd').textContent='Last update: '+new Date().toLocaleTimeString();
  }catch(e){console.error(e);}
}
refresh(); setInterval(refresh,15000);
</script>
</body>
</html>
"""

@app.route("/")
def index(): return render_template_string(HTML)

@app.route("/api/state")
def api_state(): return jsonify(load_state())

@app.route("/api/account")
def api_account():
    try:
        r=req.get("https://paper-api.alpaca.markets/v2/account",headers=alpaca_headers(),timeout=10)
        return jsonify(r.json())
    except Exception as e: return jsonify({"error":str(e)})

@app.route("/api/positions")
def api_positions():
    try:
        r=req.get("https://paper-api.alpaca.markets/v2/positions",headers=alpaca_headers(),timeout=10)
        return jsonify(r.json())
    except: return jsonify([])

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",8080)))
