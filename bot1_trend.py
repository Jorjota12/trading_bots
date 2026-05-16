# =============================================================================
# bot1_trend.py — Bot 1: Trend Follower
# =============================================================================
# Filosofía: "La tendencia es tu amiga hasta que se acaba"
#
# Indicadores:
#   - EMA 9 / EMA 21 / EMA 50  → dirección y fuerza de la tendencia
#   - MACD (12,26,9)           → confirmación de momentum
#   - ATR (14)                 → Stop Loss y Take Profit dinámicos
#
# Lógica de entrada:
#   COMPRA  si EMA9 > EMA21 > EMA50  AND  MACD cruza al alza la señal
#   VENTA   si EMA9 < EMA21 < EMA50  AND  MACD cruza a la baja la señal
#
# Timeframe: 5 minutos
# =============================================================================

import time
import logging
from datetime import datetime
import pandas as pd

from config import SYMBOL, TIMEFRAME_BOT1, CANDLES_LIMIT, LOOP_INTERVAL_BOT1, MAX_OPEN_TRADES
from exchange import get_exchange, fetch_ohlcv, get_current_price
from risk_manager import calc_position_size, calc_sl_tp, check_sl_tp
from logger import init_log, log_trade
from shared_state import try_acquire, release

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BOT1-TREND] %(message)s")
log = logging.getLogger("bot1")

BOT_NAME = "Bot1_Trend"


# ── Indicadores ──────────────────────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # EMAs
    df["ema9"]  = df["close"].ewm(span=9,  adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

    # MACD
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"]        = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = df["macd"] - df["macd_signal"]

    # ATR (True Range medio de 14 períodos)
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr         = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"]  = tr.rolling(14).mean()

    return df


# ── Señales ───────────────────────────────────────────────────────────────────

def get_signal(df: pd.DataFrame) -> str | None:
    """Devuelve 'buy', 'sell' o None."""
    last = df.iloc[-1]
    prev = df.iloc[-2]

    trend_up   = last["ema9"] > last["ema21"] > last["ema50"]
    trend_down = last["ema9"] < last["ema21"] < last["ema50"]

    # Cruce alcista MACD: en la vela anterior estaba por debajo, ahora por encima
    macd_cross_up   = prev["macd"] < prev["macd_signal"] and last["macd"] > last["macd_signal"]
    macd_cross_down = prev["macd"] > prev["macd_signal"] and last["macd"] < last["macd_signal"]

    if trend_up and macd_cross_up:
        return "buy"
    if trend_down and macd_cross_down:
        return "sell"
    return None


# ── Bucle principal ───────────────────────────────────────────────────────────

def run():
    init_log()
    exchange = get_exchange()

    # Estado de la posición abierta
    position = None  # None o dict con info del trade

    log.info(f"Iniciado. Par: {SYMBOL} | Timeframe: {TIMEFRAME_BOT1}")

    while True:
        try:
            df = fetch_ohlcv(exchange, TIMEFRAME_BOT1, CANDLES_LIMIT)
            df = compute_indicators(df)

            current_price = get_current_price(exchange)
            atr           = df["atr"].iloc[-1]

            # ── Gestión de posición abierta ──
            if position is not None:
                result = check_sl_tp(
                    current_price,
                    position["entry_price"],
                    position["stop_loss"],
                    position["take_profit"],
                    position["side"]
                )
                if result:
                    exit_time = datetime.utcnow()
                    pnl, pnl_pct = log_trade(
                        BOT_NAME, SYMBOL, position["side"],
                        position["entry_price"], current_price,
                        position["size"], position["stop_loss"],
                        position["take_profit"], result,
                        position["entry_time"], exit_time
                    )
                    log.info(f"CIERRE [{result.upper()}] | Precio: {current_price} | PnL: {pnl:.2f} USDT ({pnl_pct:.2f}%)")
                    release(BOT_NAME)
                    position = None

            # ── Buscar nueva entrada si no hay posición ──
            if position is None:
                signal = get_signal(df)
                if signal and try_acquire(BOT_NAME):
                    size           = calc_position_size(current_price, atr)
                    sl, tp         = calc_sl_tp(current_price, atr, signal)
                    position = {
                        "side":        signal,
                        "entry_price": current_price,
                        "size":        size,
                        "stop_loss":   sl,
                        "take_profit": tp,
                        "entry_time":  datetime.utcnow(),
                    }
                    log.info(f"ENTRADA [{signal.upper()}] | Precio: {current_price} | SL: {sl} | TP: {tp} | Size: {size}")

        except Exception as e:
            log.error(f"Error en el bucle: {e}")

        time.sleep(LOOP_INTERVAL_BOT1)


if __name__ == "__main__":
    run()