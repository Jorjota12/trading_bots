# =============================================================================
# config.py — Configuración global del sistema de trading bots
# =============================================================================
# Crea un archivo .env en la misma carpeta con:
#   BINANCE_TESTNET_API_KEY=tu_api_key
#   BINANCE_TESTNET_SECRET=tu_secret
# Consigue las keys en: https://testnet.binance.vision/
# =============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

# --- Credenciales ---
API_KEY    = os.getenv("BINANCE_TESTNET_API_KEY", "")
API_SECRET = os.getenv("BINANCE_TESTNET_SECRET", "")

# --- Par a operar ---
SYMBOL = "BTC/USDT"   # Cambia a "ETH/USDT", "BNB/USDT", etc. si quieres

# --- Gestión de riesgo global ---
CAPITAL_PER_BOT    = 1000.0   # USDT simulados que asignas a cada bot
RISK_PER_TRADE     = 0.01     # Arriesgar máx. 1% del capital por operación
MAX_OPEN_TRADES    = 1        # Máximo de posiciones abiertas simultáneas por bot
ATR_SL_MULTIPLIER  = 1.5      # Stop Loss = entrada ± (ATR × este valor)
ATR_TP_MULTIPLIER  = 3.0      # Take Profit = entrada ± (ATR × este valor)

# --- Timeframes por bot ---
TIMEFRAME_BOT1 = "5m"    # Trend Follower
TIMEFRAME_BOT2 = "3m"    # Mean Reversion
TIMEFRAME_BOT3 = "1m"    # Momentum

# --- Cuántas velas cargar para calcular indicadores ---
CANDLES_LIMIT = 200

# --- Intervalo de ejecución de cada bot (segundos) ---
# Bot 1 revisa cada 5 min, Bot 2 cada 3, Bot 3 cada 1
LOOP_INTERVAL_BOT1 = 300
LOOP_INTERVAL_BOT2 = 180
LOOP_INTERVAL_BOT3 = 60

# --- Fichero de log de operaciones ---
LOG_FILE = "trades_log.csv"
