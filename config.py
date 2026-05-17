# =============================================================================
# config.py — Configuración global del sistema de trading bots
# =============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

# --- Credenciales ---
API_KEY    = os.getenv("BINANCE_TESTNET_API_KEY", "")
API_SECRET = os.getenv("BINANCE_TESTNET_SECRET", "")

# --- Pares a operar ---
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

# --- Gestión de riesgo global ---
CAPITAL_PER_BOT    = 1000.0   # USDT simulados por bot por par
RISK_PER_TRADE     = 0.005    # Arriesgar máx. 0.5% del capital por operación
MAX_OPEN_TRADES    = 1        # Máximo de posiciones abiertas simultáneas por bot
ATR_SL_MULTIPLIER  = 2.0      # Stop Loss = entrada ± (ATR × este valor)
ATR_TP_MULTIPLIER  = 4.0      # Take Profit = entrada ± (ATR × este valor)

# --- Timeframes por bot ---
TIMEFRAME_BOT1 = "5m"    # Trend Follower
TIMEFRAME_BOT2 = "3m"    # Mean Reversion
TIMEFRAME_BOT3 = "5m"    # Momentum Breakout

# --- Cuántas velas cargar para calcular indicadores ---
CANDLES_LIMIT = 200

# --- Intervalo de ejecución de cada bot (segundos) ---
LOOP_INTERVAL_BOT1 = 300
LOOP_INTERVAL_BOT2 = 180
LOOP_INTERVAL_BOT3 = 300

# --- Fichero de log por par ---
def log_file_for(symbol: str) -> str:
    """Devuelve el nombre del CSV para cada par. Ej: trades_BTC.csv"""
    return f"trades_{symbol.split('/')[0]}.csv"