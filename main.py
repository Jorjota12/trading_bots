# =============================================================================
# main.py — Lanza los 3 bots × 3 pares en paralelo (9 threads total)
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

from config import SYMBOLS, log_file_for

BOTS = {
    1: ("Trend Follower",    bot1_trend.run),
    2: ("Mean Reversion",    bot2_meanrevert.run),
    3: ("Momentum Breakout", bot3_momentum.run),
}


# ── Servidor de datos ─────────────────────────────────────────────────────────

def load_all_trades():
    """Carga todos los CSVs de todos los pares."""
    trades = []
    for symbol in SYMBOLS:
        fname = log_file_for(symbol)
        if not os.path.exists(fname):
            continue
        with open(fname, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append(row)
    return trades


def calc_stats(trades):
    bots = ["Bot1_Trend", "Bot2_MeanReversion", "Bot3_Momentum"]
    symbols = SYMBOLS
    stats = {}

    for bot in bots:
        for symbol in symbols:
            key = f"{bot}_{symbol.split('/')[0]}"
            bt = [t for t in trades if t["bot"] == bot and t["symbol"] == symbol]
            if not bt:
                stats[key] = {}
                continue
            pnls   = [float(t["pnl_usdt"]) for t in bt]
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
                if val > peak: peak = val
                dd = val - peak
                if dd < max_dd: max_dd = dd
            stats[key] = {
                "bot": bot, "symbol": symbol,
                "trades": total,
                "win_rate": round(len(wins) / total * 100 if total else 0, 1),
                "total_pnl": round(sum(pnls), 2),
                "profit_factor": round(pf, 2),
                "max_drawdown": round(max_dd, 2),
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
            trades  = load_all_trades()
            stats   = calc_stats(trades)
            payload = json.dumps({
                "trades":  trades,
                "stats":   stats,
                "symbols": SYMBOLS,
                "status":  "running",
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

def launch_bot(name, run_fn, symbol):
    while True:
        try:
            logging.info(Fore.CYAN + f"▶ Iniciando {name} [{symbol}]...")
            run_fn(symbol)
        except Exception as e:
            logging.error(Fore.RED + f"💥 {name} [{symbol}] crasheó: {e}. Reiniciando en 10s...")
            import time; time.sleep(10)


def handle_exit(sig, frame):
    print(Fore.YELLOW + "\n\n⏹  Deteniendo todos los bots...")
    comparator.main()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    if args.compare:
        comparator.main()
        return

    signal.signal(signal.SIGINT, handle_exit)

    print(Fore.CYAN + Style.BRIGHT + """
╔══════════════════════════════════════════════════════════╗
║      🤖 SISTEMA DE TRADING BOTS — CRYPTO MULTI-PAR      ║
║      BTC/USDT · ETH/USDT · SOL/USDT  |  Paper Trading  ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Servidor de datos
    t_server = threading.Thread(target=run_data_server, daemon=True, name="data-server")
    t_server.start()

    # Lanzar 3 bots × 3 pares = 9 threads
    threads = []
    for symbol in SYMBOLS:
        for bot_id, (name, run_fn) in BOTS.items():
            t = threading.Thread(
                target=launch_bot,
                args=(f"Bot{bot_id} {name}", run_fn, symbol),
                daemon=True,
                name=f"bot{bot_id}-{symbol.split('/')[0]}"
            )
            t.start()
            threads.append(t)
            print(Fore.GREEN + f"  ✅ Bot{bot_id} {name} [{symbol}] lanzado")

    print(Fore.YELLOW + "\n  Pulsa Ctrl+C para detener y ver el reporte final.\n")

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()