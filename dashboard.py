# =============================================================================
# dashboard.py — Dashboard web en vivo de los 3 bots
# =============================================================================
# Abre un servidor local en http://localhost:5000
# Muestra en tiempo real: trades, PnL por bot, gráfico de equity curve
#
# Uso (en una terminal separada mientras corren los bots):
#   python dashboard.py
# Luego abre en el navegador: http://localhost:5000
# =============================================================================

import json
import csv
import os
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
from config import LOG_FILE, CAPITAL_PER_BOT

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
    --bg:       #0a0a0f;
    --surface:  #111118;
    --border:   #1e1e2e;
    --text:     #e2e2f0;
    --muted:    #5a5a7a;
    --green:    #00e5a0;
    --red:      #ff4d6d;
    --blue:     #4d9fff;
    --amber:    #ffb347;
    --purple:   #b47fff;
    --bot1:     #4d9fff;
    --bot2:     #00e5a0;
    --bot3:     #ffb347;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 14px;
    min-height: 100vh;
    padding: 24px;
  }

  header {
    display: flex;
    align-items: baseline;
    gap: 16px;
    margin-bottom: 28px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 16px;
  }

  header h1 {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 18px;
    font-weight: 500;
    letter-spacing: 0.05em;
    color: var(--text);
  }

  .live-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
    animation: pulse 1.5s ease-in-out infinite;
    display: inline-block;
    margin-right: 6px;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  .last-update {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--muted);
    margin-left: auto;
  }

  .grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 20px;
  }

  .bot-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    position: relative;
    overflow: hidden;
  }

  .bot-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
  }
  .bot-card.b1::before { background: var(--bot1); }
  .bot-card.b2::before { background: var(--bot2); }
  .bot-card.b3::before { background: var(--bot3); }

  .bot-name {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.08em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 14px;
  }
  .bot-card.b1 .bot-name { color: var(--bot1); }
  .bot-card.b2 .bot-name { color: var(--bot2); }
  .bot-card.b3 .bot-name { color: var(--bot3); }

  .pnl-big {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 28px;
    font-weight: 500;
    margin-bottom: 4px;
  }
  .pnl-big.pos { color: var(--green); }
  .pnl-big.neg { color: var(--red); }
  .pnl-big.neu { color: var(--text); }

  .pnl-pct {
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 16px;
  }

  .metrics-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .metric {
    background: var(--bg);
    border-radius: 8px;
    padding: 10px 12px;
  }

  .metric-label {
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 3px;
  }

  .metric-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 14px;
    font-weight: 500;
    color: var(--text);
  }

  .metric-value.pos { color: var(--green); }
  .metric-value.neg { color: var(--red); }

  .chart-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
  }

  .section-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 16px;
  }

  .chart-wrap {
    position: relative;
    height: 240px;
  }

  .trades-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  .trades-table th {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
  }

  .trades-table td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    font-family: 'IBM Plex Mono', monospace;
    color: var(--text);
  }

  .trades-table tr:last-child td { border-bottom: none; }
  .trades-table tr:hover td { background: rgba(255,255,255,0.02); }

  .badge {
    display: inline-block;
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 4px;
    font-weight: 500;
  }
  .badge-buy  { background: rgba(0,229,160,0.12); color: var(--green); }
  .badge-sell { background: rgba(255,77,109,0.12); color: var(--red); }
  .badge-tp   { background: rgba(0,229,160,0.12); color: var(--green); }
  .badge-sl   { background: rgba(255,77,109,0.12); color: var(--red); }
  .badge-other{ background: rgba(255,179,71,0.12); color: var(--amber); }

  .no-data {
    text-align: center;
    color: var(--muted);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    padding: 48px 0;
  }

  .bot-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
  }
</style>
</head>
<body>

<header>
  <h1><span class="live-dot"></span>TRADING BOTS — LIVE DASHBOARD</h1>
  <span class="last-update" id="last-update">actualizando...</span>
</header>

<div class="grid-3" id="bot-cards">
  <!-- se rellena con JS -->
</div>

<div class="chart-section">
  <p class="section-title">Equity curve — PnL acumulado por bot (USDT)</p>
  <div class="chart-wrap">
    <canvas id="equityChart"></canvas>
  </div>
</div>

<div class="chart-section">
  <p class="section-title">Últimos trades</p>
  <div id="trades-wrap">
    <p class="no-data">Esperando los primeros trades...</p>
  </div>
</div>

<script>
const BOT_COLORS = {
  'Bot1_Trend':         '#4d9fff',
  'Bot2_MeanReversion': '#00e5a0',
  'Bot3_Momentum':      '#ffb347',
};
const BOT_LABELS = {
  'Bot1_Trend':         'BOT 1 — TREND',
  'Bot2_MeanReversion': 'BOT 2 — MEAN REV',
  'Bot3_Momentum':      'BOT 3 — MOMENTUM',
};
const BOT_CLASSES = {
  'Bot1_Trend':         'b1',
  'Bot2_MeanReversion': 'b2',
  'Bot3_Momentum':      'b3',
};

let equityChart = null;

function fmt(n, decimals=2) {
  if (n === undefined || n === null || isNaN(n)) return '—';
  return (n >= 0 ? '+' : '') + Number(n).toFixed(decimals);
}

function fmtAbs(n, decimals=2) {
  return Number(n).toFixed(decimals);
}

function pnlClass(n) {
  if (n > 0) return 'pos';
  if (n < 0) return 'neg';
  return 'neu';
}

function renderCards(stats) {
  const bots = ['Bot1_Trend', 'Bot2_MeanReversion', 'Bot3_Momentum'];
  const container = document.getElementById('bot-cards');
  container.innerHTML = bots.map(bot => {
    const s = stats[bot] || {};
    const pnl = s.total_pnl ?? 0;
    const capital = 1000;
    const pnlPct = (pnl / capital * 100).toFixed(2);
    const wr = s.win_rate != null ? s.win_rate.toFixed(1) + '%' : '—';
    const pf = s.profit_factor != null ? fmtAbs(s.profit_factor) : '—';
    const trades = s.trades ?? 0;
    const dd = s.max_drawdown != null ? fmtAbs(Math.abs(s.max_drawdown)) : '—';

    return `
    <div class="bot-card ${BOT_CLASSES[bot]}">
      <p class="bot-name">${BOT_LABELS[bot]}</p>
      <div class="pnl-big ${pnlClass(pnl)}">${fmt(pnl)} USDT</div>
      <div class="pnl-pct">${pnl >= 0 ? '▲' : '▼'} ${Math.abs(pnlPct)}% del capital</div>
      <div class="metrics-row">
        <div class="metric">
          <div class="metric-label">Trades</div>
          <div class="metric-value">${trades}</div>
        </div>
        <div class="metric">
          <div class="metric-label">Win Rate</div>
          <div class="metric-value ${s.win_rate >= 50 ? 'pos' : 'neg'}">${wr}</div>
        </div>
        <div class="metric">
          <div class="metric-label">Profit Factor</div>
          <div class="metric-value ${s.profit_factor >= 1.5 ? 'pos' : ''}">${pf}</div>
        </div>
        <div class="metric">
          <div class="metric-label">Max Drawdown</div>
          <div class="metric-value neg">${dd} USDT</div>
        </div>
      </div>
    </div>`;
  }).join('');
}

function renderEquityChart(trades) {
  const bots = ['Bot1_Trend', 'Bot2_MeanReversion', 'Bot3_Momentum'];
  const ctx = document.getElementById('equityChart').getContext('2d');

  // Construir equity curve por bot
  const datasets = bots.map(bot => {
    const botTrades = trades.filter(t => t.bot === bot)
      .sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time));

    let cumPnl = 0;
    const data = botTrades.map(t => {
      cumPnl += parseFloat(t.pnl_usdt);
      return { x: t.exit_time, y: parseFloat(cumPnl.toFixed(2)) };
    });

    // Añadir punto inicial
    if (data.length > 0) data.unshift({ x: data[0].x, y: 0 });

    return {
      label: BOT_LABELS[bot],
      data,
      borderColor: BOT_COLORS[bot],
      backgroundColor: 'transparent',
      borderWidth: 1.5,
      pointRadius: 2,
      pointBackgroundColor: BOT_COLORS[bot],
      tension: 0.3,
    };
  });

  if (equityChart) equityChart.destroy();

  equityChart = new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: {
            color: '#5a5a7a',
            font: { family: 'IBM Plex Mono', size: 11 },
            boxWidth: 12,
          }
        },
        tooltip: {
          backgroundColor: '#111118',
          borderColor: '#1e1e2e',
          borderWidth: 1,
          titleColor: '#5a5a7a',
          bodyColor: '#e2e2f0',
          bodyFont: { family: 'IBM Plex Mono', size: 12 },
        }
      },
      scales: {
        x: {
          type: 'category',
          ticks: { color: '#5a5a7a', font: { family: 'IBM Plex Mono', size: 10 }, maxTicksLimit: 8 },
          grid: { color: '#1e1e2e' },
        },
        y: {
          ticks: { color: '#5a5a7a', font: { family: 'IBM Plex Mono', size: 10 },
                   callback: v => (v >= 0 ? '+' : '') + v + ' USDT' },
          grid: { color: '#1e1e2e' },
        }
      }
    }
  });
}

function renderTrades(trades) {
  const wrap = document.getElementById('trades-wrap');
  const last20 = [...trades].reverse().slice(0, 20);

  if (last20.length === 0) {
    wrap.innerHTML = '<p class="no-data">Esperando los primeros trades...</p>';
    return;
  }

  const rows = last20.map(t => {
    const pnl = parseFloat(t.pnl_usdt);
    const reasonBadge = t.exit_reason === 'tp'
      ? '<span class="badge badge-tp">TP</span>'
      : t.exit_reason === 'sl'
        ? '<span class="badge badge-sl">SL</span>'
        : `<span class="badge badge-other">${t.exit_reason}</span>`;
    const sideBadge = t.side === 'buy'
      ? '<span class="badge badge-buy">BUY</span>'
      : '<span class="badge badge-sell">SELL</span>';
    const dot = BOT_COLORS[t.bot] || '#fff';
    return `<tr>
      <td><span class="bot-dot" style="background:${dot}"></span>${t.bot.replace('Bot1_','B1 ').replace('Bot2_','B2 ').replace('Bot3_','B3 ')}</td>
      <td>${sideBadge}</td>
      <td>${fmtAbs(t.entry_price, 1)}</td>
      <td>${fmtAbs(t.exit_price, 1)}</td>
      <td class="${pnl >= 0 ? 'pos' : 'neg'}" style="color:${pnl >= 0 ? 'var(--green)' : 'var(--red)'}">
        ${fmt(pnl)} USDT
      </td>
      <td>${reasonBadge}</td>
      <td style="color:var(--muted)">${t.exit_time?.slice(11,16) ?? ''}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `
    <table class="trades-table">
      <thead>
        <tr>
          <th>Bot</th><th>Lado</th><th>Entrada</th><th>Salida</th>
          <th>PnL</th><th>Razón</th><th>Hora</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function refresh() {
  try {
    const res  = await fetch('/data');
    const data = await res.json();
    renderCards(data.stats);
    renderEquityChart(data.trades);
    renderTrades(data.trades);
    document.getElementById('last-update').textContent =
      'actualizado: ' + new Date().toLocaleTimeString('es-ES');
  } catch(e) {
    document.getElementById('last-update').textContent = 'error de conexión...';
  }
}

refresh();
setInterval(refresh, 10000);  // Refresca cada 10 segundos
</script>
</body>
</html>
"""


GITHUB_USER  = "Jorjota12"
GITHUB_REPO  = "trading_bots"
GITHUB_PATH  = "trades_log.csv"


def load_data():
    import requests, io
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{GITHUB_PATH}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        return list(reader)
    except Exception:
        return []


def calc_stats(trades):
    bots = ["Bot1_Trend", "Bot2_MeanReversion", "Bot3_Momentum"]
    stats = {}

    for bot in bots:
        bot_trades = [t for t in trades if t["bot"] == bot]
        if not bot_trades:
            stats[bot] = {}
            continue

        pnls    = [float(t["pnl_usdt"]) for t in bot_trades]
        wins    = [p for p in pnls if p > 0]
        losses  = [p for p in pnls if p <= 0]
        total   = len(pnls)

        gross_profit = sum(wins) if wins else 0
        gross_loss   = abs(sum(losses)) if losses else 1
        pf = gross_profit / gross_loss if gross_loss > 0 else 0

        cumulative = []
        c = 0
        for p in pnls:
            c += p
            cumulative.append(c)

        peak = cumulative[0] if cumulative else 0
        max_dd = 0
        for val in cumulative:
            if val > peak:
                peak = val
            dd = val - peak
            if dd < max_dd:
                max_dd = dd

        stats[bot] = {
            "trades":        total,
            "win_rate":      len(wins) / total * 100 if total else 0,
            "total_pnl":     round(sum(pnls), 2),
            "profit_factor": round(pf, 2),
            "max_drawdown":  round(max_dd, 2),
        }

    return stats


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silenciar logs HTTP

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode())

        elif self.path == "/data":
            trades = load_data()
            stats  = calc_stats(trades)
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