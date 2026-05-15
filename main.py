# =============================================================================
# main.py — Lanza los 3 bots en paralelo usando threads
# =============================================================================
# Uso:
#   python main.py              → lanza los 3 bots
#   python main.py --bot 1      → lanza solo el Bot 1
#   python main.py --compare    → muestra el dashboard y sale
# =============================================================================

import threading
import argparse
import logging
import signal
import sys
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


def launch_bot(name: str, run_fn):
    """Wrapper que relanza el bot si peta inesperadamente."""
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
    parser = argparse.ArgumentParser(description="Sistema de trading bots — Crypto Scalping")
    parser.add_argument("--bot",     type=int, choices=[1, 2, 3], help="Lanzar solo un bot concreto")
    parser.add_argument("--compare", action="store_true",          help="Mostrar dashboard y salir")
    args = parser.parse_args()

    # Solo mostrar el dashboard
    if args.compare:
        comparator.main()
        return

    # Capturar Ctrl+C para mostrar reporte al salir
    signal.signal(signal.SIGINT, handle_exit)

    print(Fore.CYAN + Style.BRIGHT + """
╔══════════════════════════════════════════════╗
║      🤖 SISTEMA DE TRADING BOTS — CRYPTO     ║
║         Paper Trading | Binance Testnet      ║
╚══════════════════════════════════════════════╝
    """)

    # Decidir qué bots lanzar
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

    # Mantener el hilo principal vivo
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
