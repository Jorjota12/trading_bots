# =============================================================================
# exchange.py — Conexión a Binance Testnet via ccxt
# =============================================================================

import ccxt
import pandas as pd
from config import API_KEY, API_SECRET, SYMBOL

def get_exchange():
    """Devuelve una instancia conectada a Binance Testnet."""
    exchange = ccxt.binance({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "timeout": 30000,  # 30 segundos máximo por llamada
        "options": {
            "defaultType": "spot",
            "adjustForTimeDifference": True,
        }
    })
    exchange.set_sandbox_mode(True)
    return exchange


def fetch_ohlcv(exchange, timeframe: str, limit: int = 200) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(SYMBOL, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df.astype(float)
    return df


def get_balance(exchange, asset: str = "USDT") -> float:
    """Devuelve el balance disponible del asset indicado."""
    balance = exchange.fetch_balance()
    return balance["free"].get(asset, 0.0)


def place_market_order(exchange, side: str, amount: float) -> dict:
    """
    Lanza una orden de mercado.
    side: 'buy' o 'sell'
    amount: cantidad en la moneda base (ej. BTC)
    """
    order = exchange.create_market_order(SYMBOL, side, amount)
    return order


def get_current_price(exchange) -> float:
    """Devuelve el precio actual (último cierre de ticker)."""
    ticker = exchange.fetch_ticker(SYMBOL)
    return ticker["last"]