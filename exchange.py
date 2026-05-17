# =============================================================================
# exchange.py — Conexión a Binance Testnet via ccxt
# =============================================================================

import ccxt
import pandas as pd
from config import API_KEY, API_SECRET


def get_exchange():
    exchange = ccxt.binance({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "timeout": 30000,
        "options": {
            "defaultType": "spot",
            "adjustForTimeDifference": True,
        }
    })
    exchange.set_sandbox_mode(True)
    return exchange


def fetch_ohlcv(exchange, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df.astype(float)
    return df


def get_balance(exchange, asset: str = "USDT") -> float:
    balance = exchange.fetch_balance()
    return balance["free"].get(asset, 0.0)


def get_current_price(exchange, symbol: str) -> float:
    ticker = exchange.fetch_ticker(symbol)
    return ticker["last"]