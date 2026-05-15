# =============================================================================
# logger.py — Registra todas las operaciones en CSV
# =============================================================================

import csv
import os
from datetime import datetime
from config import LOG_FILE

HEADERS = [
    "bot", "symbol", "side", "entry_price", "exit_price",
    "size", "pnl_usdt", "pnl_pct", "stop_loss", "take_profit",
    "exit_reason", "entry_time", "exit_time", "duration_min"
]


def init_log():
    """Crea el CSV con cabeceras si no existe."""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()


def log_trade(bot_name: str, symbol: str, side: str,
              entry_price: float, exit_price: float, size: float,
              stop_loss: float, take_profit: float,
              exit_reason: str, entry_time: datetime, exit_time: datetime):
    """Registra un trade cerrado en el CSV."""

    pnl_usdt = (exit_price - entry_price) * size if side == "buy" \
               else (entry_price - exit_price) * size
    pnl_pct  = (pnl_usdt / (entry_price * size)) * 100 if entry_price * size > 0 else 0
    duration = round((exit_time - entry_time).total_seconds() / 60, 2)

    row = {
        "bot":          bot_name,
        "symbol":       symbol,
        "side":         side,
        "entry_price":  round(entry_price, 4),
        "exit_price":   round(exit_price, 4),
        "size":         size,
        "pnl_usdt":     round(pnl_usdt, 4),
        "pnl_pct":      round(pnl_pct, 4),
        "stop_loss":    round(stop_loss, 4),
        "take_profit":  round(take_profit, 4),
        "exit_reason":  exit_reason,   # 'tp', 'sl', 'signal'
        "entry_time":   entry_time.strftime("%Y-%m-%d %H:%M:%S"),
        "exit_time":    exit_time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_min": duration,
    }

    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writerow(row)

    return pnl_usdt, pnl_pct
