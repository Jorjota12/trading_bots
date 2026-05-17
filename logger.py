# =============================================================================
# logger.py — Registra operaciones en CSV y sube a GitHub automáticamente
# =============================================================================

import csv
import os
import json
import base64
import urllib.request
from datetime import datetime

HEADERS = [
    "bot", "symbol", "side", "entry_price", "exit_price",
    "size", "pnl_usdt", "pnl_pct", "stop_loss", "take_profit",
    "exit_reason", "entry_time", "exit_time", "duration_min"
]

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER  = "Jorjota12"
GITHUB_REPO  = "trading_bots"


def push_csv_to_github(log_file: str):
    if not GITHUB_TOKEN:
        return
    try:
        with open(log_file, "rb") as f:
            content = base64.b64encode(f.read()).decode()

        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{log_file}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Content-Type": "application/json",
        }
        sha = None
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
                sha = data.get("sha")
        except Exception:
            pass

        payload = {"message": f"update {log_file}", "content": content}
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
        pass


def init_log(log_file: str):
    if not os.path.exists(log_file):
        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()


def log_trade(bot_name: str, symbol: str, side: str,
              entry_price: float, exit_price: float, size: float,
              stop_loss: float, take_profit: float,
              exit_reason: str, entry_time: datetime, exit_time: datetime,
              log_file: str = "trades_BTC.csv"):

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

    with open(log_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writerow(row)

    push_csv_to_github(log_file)
    return pnl_usdt, pnl_pct