# =============================================================================
# main.py — Lanza los 3 bots en paralelo + servidor de datos para el dashboard
# =============================================================================

import threading
import argparse
import logging
import signal
import sys
import json
import csv
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from colorama import init, Fore, Style

import bot1_trend
import bot2_meanrevert
import bot3_momentum
import comparator

init(autoreset=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S"
)

BOTS = {
    1: ("Bot1 — Trend Follower",    bot1_trend.run),
    2: ("Bot2 — Mean Reversion",    bot2_meanrevert.run),
    3: ("Bot3 — Momentum Breakout", bot3_momentum.run),
}


# ── Servidor de datos ─────────────────────────────────────────────────────────

def load_trades():
    from config import LOG_FILE
    trades = []
    if not os.path.exists(LOG_FILE):
        return trades
    with open(LOG_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
    return trades


def calc_stats(trades):
    bots = ["Bot1_Trend", "Bot2_MeanReversion", "Bot3_Momentum"]
    stats = {}
    for bot in bots:
        bot_trades = [t for t in trades if t["bot"] == bot]
        if not bot_trades:
            stats[bot] = {}
            continue
        pnls   = [float(t["pnl_usdt"]) for t in bot_trades]
        wins   = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        total  = len(pnls)
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
            "win_rate":      round(len(wins) / total * 100 if total else 0, 1),
            "total_pnl":     round(sum(pnls), 2),
            "profit_factor": round(pf, 2),
            "max_drawdown":  round(max_dd, 2),
        }
    return stats


class DataHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json",
        }
        if self.path in ["/data", "/"]:
            trades  = load_trades()
            stats   = calc_stats(trades)
            payload = json.dumps({
                "trades": trades,
                "stats":  stats,
                "status": "running",
                "bots":   3,
            })
            self.send_response(200)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(payload.encode())
        else:
            self.send_response(404)
            self.end_headers()


def run_data_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DataHandler)
    logging.info(Fore.CYAN + f"Servidor de datos en puerto {port}")
    server.serve_forever()


# ── Bots ──────────────────────────────────────────────────────────────────────

def launch_bot(name, run_fn):
    while True:
        try:
            logging.info(Fore.CYAN + f"▶ Iniciando {name}...")
            run_fn()
        except Exception as e:
            logging.error(Fore.RED + f"💥 {name} crasheó: {e}. Reiniciando en 10s...")
            import time; time.sleep(10)


def handle_exit(sig, frame):
    print(Fore.YELLOW + "\n\n⏹  Deteniendo todos los bots...")
    print(Fore.CYAN   + "📊 Generando reporte final...\n")
    comparator.main()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot",     type=int, choices=[1, 2, 3])
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    if args.compare:
        comparator.main()
        return

    signal.signal(signal.SIGINT, handle_exit)

    print(Fore.CYAN + Style.BRIGHT + """
╔══════════════════════════════════════════════╗
║      🤖 SISTEMA DE TRADING BOTS — CRYPTO     ║
║         Paper Trading | Binance Testnet      ║
╚══════════════════════════════════════════════╝
    """)

    # Lanzar servidor de datos en background
    t_server = threading.Thread(target=run_data_server, daemon=True, name="data-server")
    t_server.start()

    # Lanzar bots
    bots_to_run = {args.bot: BOTS[args.bot]} if args.bot else BOTS
    threads = []
    for bot_id, (name, run_fn) in bots_to_run.items():
        t = threading.Thread(
            target=launch_bot,
            args=(name, run_fn),
            daemon=True,
            name=f"bot-{bot_id}"
        )
        t.start()
        threads.append(t)
        print(Fore.GREEN + f"  ✅ {name} lanzado")

    print(Fore.YELLOW + "\n  Pulsa Ctrl+C para detener y ver el reporte final.\n")

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()