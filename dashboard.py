# =============================================================================
# dashboard.py — Dashboard multi-par (BTC, ETH, SOL)
# Ejecuta: python3 dashboard.py
# Abre: http://localhost:5001
# =============================================================================

import json
import os
import csv
import io
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

GITHUB_USER = "Jorjota12"
GITHUB_REPO = "trading_bots"
SYMBOLS     = ["BTC", "ETH", "SOL"]

HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trading Bots — Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500&display=swap');
  :root {
    --bg:#0a0a0f; --surface:#111118; --border:#1e1e2e; --text:#e2e2f0; --muted:#5a5a7a;
    --green:#00e5a0; --red:#ff4d6d; --blue:#4d9fff; --amber:#ffb347; --purple:#b47fff;
    --bot1:#4d9fff; --bot2:#00e5a0; --bot3:#ffb347;
    --btc:#f7931a; --eth:#627eea; --sol:#9945ff;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:'IBM Plex Sans',sans-serif; font-size:14px; padding:24px; }
  header { display:flex; align-items:baseline; gap:16px; margin-bottom:28px; border-bottom:1px solid var(--border); padding-bottom:16px; }
  header h1 { font-family:'IBM Plex Mono',monospace; font-size:18px; font-weight:500; letter-spacing:.05em; }
  .live-dot { width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);animation:pulse 1.5s ease-in-out infinite;display:inline-block;margin-right:6px; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
  .last-update { font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--muted); margin-left:auto; }
  .section-label { font-size:11px; font-weight:500; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; margin:1.5rem 0 10px; }
  .pair-header { display:flex; align-items:center; gap:10px; margin:24px 0 12px; }
  .pair-badge { font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:500; padding:4px 12px; border-radius:20px; }
  .pair-btc { background:rgba(247,147,26,.15); color:var(--btc); }
  .pair-eth { background:rgba(98,126,234,.15); color:var(--eth); }
  .pair-sol { background:rgba(153,69,255,.15); color:var(--sol); }
  .grid-3 { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:20px; }
  .bot-card { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:20px; position:relative; overflow:hidden; }
  .bot-card::before { content:''; position:absolute; top:0;left:0;right:0; height:2px; }
  .bot-card.b1::before{background:var(--bot1)} .bot-card.b2::before{background:var(--bot2)} .bot-card.b3::before{background:var(--bot3)}
  .bot-name { font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:500; letter-spacing:.08em; color:var(--muted); text-transform:uppercase; margin-bottom:14px; }
  .bot-card.b1 .bot-name{color:var(--bot1)} .bot-card.b2 .bot-name{color:var(--bot2)} .bot-card.b3 .bot-name{color:var(--bot3)}
  .pnl-big { font-family:'IBM Plex Mono',monospace; font-size:26px; font-weight:500; margin-bottom:4px; }
  .pnl-big.pos{color:var(--green)} .pnl-big.neg{color:var(--red)} .pnl-big.neu{color:var(--text)}
  .pnl-pct { font-size:12px; color:var(--muted); margin-bottom:14px; }
  .metrics-row { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  .metric { background:var(--bg); border-radius:8px; padding:10px 12px; }
  .metric-label { font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; margin-bottom:3px; }
  .metric-value { font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:500; color:var(--text); }
  .metric-value.pos{color:var(--green)} .metric-value.neg{color:var(--red)}
  .chart-section { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:20px; }
  .chart-wrap { position:relative; height:220px; }
  .trades-table { width:100%; border-collapse:collapse; font-size:12px; }
  .trades-table th { font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; text-align:left; padding:8px 12px; border-bottom:1px solid var(--border); }
  .trades-table td { padding:10px 12px; border-bottom:1px solid var(--border); font-family:'IBM Plex Mono',monospace; }
  .trades-table tr:last-child td{border-bottom:none}
  .badge { display:inline-block; font-size:10px; padding:2px 7px; border-radius:4px; font-weight:500; }
  .badge-buy{background:rgba(0,229,160,.12);color:var(--green)} .badge-sell{background:rgba(255,77,109,.12);color:var(--red)}
  .badge-tp{background:rgba(0,229,160,.12);color:var(--green)} .badge-sl{background:rgba(255,77,109,.12);color:var(--red)}
  .badge-other{background:rgba(255,179,71,.12);color:var(--amber)}
  .no-data { text-align:center; color:var(--muted); font-family:'IBM Plex Mono',monospace; font-size:13px; padding:32px 0; }
  .bot-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; vertical-align:middle; }
  .divider { border:none; border-top:1px solid var(--border); margin:24px 0; }
</style>
</head>
<body>
<header>
  <h1><span class="live-dot"></span>TRADING BOTS — LIVE DASHBOARD</h1>
  <span class="last-update" id="last-update">actualizando...</span>
</header>
<div id="content"></div>

<script>
const BOT_COLORS = {'Bot1_Trend':'#4d9fff','Bot2_MeanReversion':'#00e5a0','Bot3_Momentum':'#ffb347'};
const BOT_LABELS = {'Bot1_Trend':'BOT 1 — TREND','Bot2_MeanReversion':'BOT 2 — MEAN REV','Bot3_Momentum':'BOT 3 — MOMENTUM'};
const BOT_CLASSES= {'Bot1_Trend':'b1','Bot2_MeanReversion':'b2','Bot3_Momentum':'b3'};
const PAIR_COLORS= {'BTC':'#f7931a','ETH':'#627eea','SOL':'#9945ff'};
const SYMBOLS    = ['BTC','ETH','SOL'];

let charts = {};

function fmt(n,d=2){ if(n===undefined||n===null||isNaN(n))return'—'; return(n>=0?'+':'')+Number(n).toFixed(d); }
function fmtAbs(n,d=2){ return Number(n).toFixed(d); }
function pnlClass(n){ return n>0?'pos':n<0?'neg':'neu'; }

function renderPair(symbol, trades, stats) {
  const bots = ['Bot1_Trend','Bot2_MeanReversion','Bot3_Momentum'];
  const pairTrades = trades.filter(t => t.symbol === symbol+'/USDT');

  const cards = bots.map(bot => {
    const key = `${bot}_${symbol}`;
    const s   = stats[key] || {};
    const pnl = s.total_pnl ?? 0;
    const wr  = s.win_rate != null ? s.win_rate.toFixed(1)+'%' : '—';
    const pf  = s.profit_factor != null ? fmtAbs(s.profit_factor) : '—';
    const dd  = s.max_drawdown != null ? fmtAbs(Math.abs(s.max_drawdown)) : '—';
    return `<div class="bot-card ${BOT_CLASSES[bot]}">
      <p class="bot-name">${BOT_LABELS[bot]}</p>
      <div class="pnl-big ${pnlClass(pnl)}">${fmt(pnl)} USDT</div>
      <div class="pnl-pct">${pnl>=0?'▲':'▼'} ${Math.abs((pnl/1000*100).toFixed(2))}% del capital</div>
      <div class="metrics-row">
        <div class="metric"><div class="metric-label">Trades</div><div class="metric-value">${s.trades??0}</div></div>
        <div class="metric"><div class="metric-label">Win Rate</div><div class="metric-value ${(s.win_rate??0)>=50?'pos':'neg'}">${wr}</div></div>
        <div class="metric"><div class="metric-label">Profit Factor</div><div class="metric-value ${(s.profit_factor??0)>=1.5?'pos':''}">${pf}</div></div>
        <div class="metric"><div class="metric-label">Max Drawdown</div><div class="metric-value neg">${dd} USDT</div></div>
      </div>
    </div>`;
  }).join('');

  // Equity curve
  const chartId = `chart_${symbol}`;
  const datasets = bots.map(bot => {
    const bt = pairTrades.filter(t=>t.bot===bot).sort((a,b)=>new Date(a.exit_time)-new Date(b.exit_time));
    let c=0;
    const data = bt.map(t=>{c+=parseFloat(t.pnl_usdt);return{x:t.exit_time?.slice(11,16),y:parseFloat(c.toFixed(2))};});
    if(data.length>0) data.unshift({x:data[0].x,y:0});
    return {label:BOT_LABELS[bot],data,borderColor:BOT_COLORS[bot],backgroundColor:'transparent',borderWidth:1.5,pointRadius:2,tension:.3};
  });

  // Últimos trades del par
  const last10 = [...pairTrades].reverse().slice(0,10);
  const rows = last10.map(t => {
    const pnl = parseFloat(t.pnl_usdt);
    const rb  = t.exit_reason==='tp'?'<span class="badge badge-tp">TP</span>':t.exit_reason==='sl'?'<span class="badge badge-sl">SL</span>':`<span class="badge badge-other">${t.exit_reason}</span>`;
    const sb  = t.side==='buy'?'<span class="badge badge-buy">BUY</span>':'<span class="badge badge-sell">SELL</span>';
    const dot = BOT_COLORS[t.bot]||'#fff';
    return `<tr>
      <td><span class="bot-dot" style="background:${dot}"></span>${t.bot?.replace('Bot1_','B1 ').replace('Bot2_','B2 ').replace('Bot3_','B3 ')}</td>
      <td>${sb}</td><td>${fmtAbs(t.entry_price,1)}</td><td>${fmtAbs(t.exit_price,1)}</td>
      <td style="color:${pnl>=0?'var(--green)':'var(--red)'}">${fmt(pnl)} USDT</td>
      <td>${rb}</td><td style="color:var(--muted)">${t.exit_time?.slice(11,16)??''}</td>
    </tr>`;
  }).join('');

  const tableHtml = last10.length>0
    ? `<table class="trades-table"><thead><tr><th>Bot</th><th>Lado</th><th>Entrada</th><th>Salida</th><th>PnL</th><th>Razón</th><th>Hora</th></tr></thead><tbody>${rows}</tbody></table>`
    : '<p class="no-data">Sin trades aún</p>';

  return `
    <div class="pair-header">
      <span class="pair-badge pair-${symbol.toLowerCase()}">${symbol}/USDT</span>
    </div>
    <div class="grid-3">${cards}</div>
    <div class="chart-section">
      <p class="section-label">Equity curve — ${symbol}</p>
      <div class="chart-wrap"><canvas id="${chartId}"></canvas></div>
    </div>
    <div class="chart-section">
      <p class="section-label">Últimos trades — ${symbol}</p>
      ${tableHtml}
    </div>`;
}

function initChart(chartId, datasets) {
  const ctx = document.getElementById(chartId)?.getContext('2d');
  if(!ctx) return;
  if(charts[chartId]) charts[chartId].destroy();
  charts[chartId] = new Chart(ctx, {
    type:'line', data:{datasets},
    options:{
      responsive:true, maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{labels:{color:'#5a5a7a',font:{family:'IBM Plex Mono',size:11},boxWidth:12}},
        tooltip:{backgroundColor:'#111118',borderColor:'#1e1e2e',borderWidth:1,titleColor:'#5a5a7a',bodyColor:'#e2e2f0',bodyFont:{family:'IBM Plex Mono',size:12}}
      },
      scales:{
        x:{type:'category',ticks:{color:'#5a5a7a',font:{family:'IBM Plex Mono',size:10},maxTicksLimit:8},grid:{color:'#1e1e2e'}},
        y:{ticks:{color:'#5a5a7a',font:{family:'IBM Plex Mono',size:10},callback:v=>(v>=0?'+':'')+v+' U'},grid:{color:'#1e1e2e'}}
      }
    }
  });
}

async function refresh() {
  try {
    const res   = await fetch('/data');
    const data  = await res.json();
    const bots  = ['Bot1_Trend','Bot2_MeanReversion','Bot3_Momentum'];
    let html    = '';

    SYMBOLS.forEach((sym,i) => {
      html += renderPair(sym, data.trades, data.stats);
      if(i < SYMBOLS.length-1) html += '<hr class="divider">';
    });

    document.getElementById('content').innerHTML = html;

    // Inicializar gráficos después de renderizar
    SYMBOLS.forEach(sym => {
      const chartId  = `chart_${sym}`;
      const pairTrades = data.trades.filter(t=>t.symbol===sym+'/USDT');
      const datasets = bots.map(bot => {
        const bt = pairTrades.filter(t=>t.bot===bot).sort((a,b)=>new Date(a.exit_time)-new Date(b.exit_time));
        let c=0;
        const d = bt.map(t=>{c+=parseFloat(t.pnl_usdt);return{x:t.exit_time?.slice(11,16),y:parseFloat(c.toFixed(2))};});
        if(d.length>0) d.unshift({x:d[0].x,y:0});
        return {label:BOT_LABELS[bot],data:d,borderColor:BOT_COLORS[bot],backgroundColor:'transparent',borderWidth:1.5,pointRadius:2,tension:.3};
      });
      initChart(chartId, datasets);
    });

    document.getElementById('last-update').textContent = 'actualizado: '+new Date().toLocaleTimeString('es-ES');
  } catch(e) {
    document.getElementById('last-update').textContent = 'error de conexión...';
  }
}

refresh();
setInterval(refresh, 15000);
</script>
</body>
</html>"""


def fetch_csv(filename):
    import requests
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{filename}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        return list(reader)
    except Exception:
        return []


def load_all_trades():
    trades = []
    for sym in SYMBOLS:
        trades += fetch_csv(f"trades_{sym}.csv")
    return trades


def calc_stats(trades):
    bots = ["Bot1_Trend", "Bot2_MeanReversion", "Bot3_Momentum"]
    stats = {}
    for bot in bots:
        for sym in SYMBOLS:
            key = f"{bot}_{sym}"
            bt  = [t for t in trades if t["bot"] == bot and t.get("symbol","") == f"{sym}/USDT"]
            if not bt:
                stats[key] = {}
                continue
            pnls  = [float(t["pnl_usdt"]) for t in bt]
            wins  = [p for p in pnls if p > 0]
            losses= [p for p in pnls if p <= 0]
            total = len(pnls)
            gp    = sum(wins) if wins else 0
            gl    = abs(sum(losses)) if losses else 1
            c=0; cumul=[]; peak=0; max_dd=0
            for p in pnls:
                c+=p; cumul.append(c)
            for v in cumul:
                if v>peak: peak=v
                if v-peak<max_dd: max_dd=v-peak
            stats[key] = {
                "trades": total,
                "win_rate": round(len(wins)/total*100 if total else 0, 1),
                "total_pnl": round(sum(pnls), 2),
                "profit_factor": round(gp/gl, 2),
                "max_drawdown": round(max_dd, 2),
            }
    return stats


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == "/data":
            trades  = load_all_trades()
            stats   = calc_stats(trades)
            payload = json.dumps({"trades": trades, "stats": stats})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload.encode())
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    port = 5001
    server = HTTPServer(("localhost", port), Handler)
    print(f"Dashboard en vivo → http://localhost:{port}")
    print("Ctrl+C para detener")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard detenido.")