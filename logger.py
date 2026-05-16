# =============================================================================
# logger.py — Registra operaciones en CSV y sube a GitHub automáticamente
# =============================================================================

import csv
import os
import json
import base64
import urllib.request
from datetime import datetime
from config import LOG_FILE

HEADERS = [
    "bot", "symbol", "side", "entry_price", "exit_price",
    "size", "pnl_usdt", "pnl_pct", "stop_loss", "take_profit",
    "exit_reason", "entry_time", "exit_time", "duration_min"
]

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER  = "Jorjota12"
GITHUB_REPO  = "trading_bots"
GITHUB_PATH  = "trades_log.csv"


def push_csv_to_github():
    """Sube el trades_log.csv a GitHub después de cada trade."""
    if not GITHUB_TOKEN:
        return
    try:
        with open(LOG_FILE, "rb") as f:
            content = base64.b64encode(f.read()).decode()

        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Content-Type": "application/json",
        }

        # Obtener SHA del archivo actual (necesario para actualizarlo)
        sha = None
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
                sha = data.get("sha")
        except Exception:
            pass

        payload = {"message": "update trades_log", "content": content}
        if sha:
            payload["sha"] = sha

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="PUT"
        )
        urllib.request.urlopen(req)
    except Exception:
        pass  # No interrumpir los bots si falla el push


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
    """Registra un trade cerrado en el CSV y lo sube a GitHub."""

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
        "exit_reason":  exit_reason,
        "entry_time":   entry_time.strftime("%Y-%m-%d %H:%M:%S"),
        "exit_time":    exit_time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_min": duration,
    }

    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writerow(row)

    # Subir CSV actualizado a GitHub
    push_csv_to_github()

    return pnl_usdt, pnl_pct