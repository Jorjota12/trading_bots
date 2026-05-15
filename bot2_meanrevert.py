# =============================================================================
# bot2_meanrevert.py — Bot 2: Mean Reversion
# =============================================================================
# Filosofía: "Los precios extremos vuelven a la media"
#
# Indicadores:
#   - RSI (14)                   → detecta sobrecompra/sobreventa
#   - Bandas de Bollinger (20,2) → límites estadísticos del precio
#   - Stochastic (14,3,3)        → confirma el agotamiento del movimiento
#   - ATR (14)                   → Stop Loss y Take Profit dinámicos
#
# Lógica de entrada:
#   COMPRA  si precio < Banda Inferior  AND  RSI < 35  AND  Stoch %K cruza %D al alza
#   VENTA   si precio > Banda Superior  AND  RSI > 65  AND  Stoch %K cruza %D a la baja
#
# Timeframe: 3 minutos
# =============================================================================

import time
import logging
from datetime import datetime
import pandas as pd

from config import SYMBOL, TIMEFRAME_BOT2, CANDLES_LIMIT, LOOP_INTERVAL_BOT2
from exchange import get_exchange, fetch_ohlcv, get_current_price
from risk_manager import calc_position_size, calc_sl_tp, check_sl_tp
from logger import init_log, log_trade

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BOT2-MEAN] %(message)s")
log = logging.getLogger("bot2")

BOT_NAME = "Bot2_MeanReversion"


# ── Indicadores ──────────────────────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # RSI
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # Bandas de Bollinger (20 períodos, 2 desviaciones)
    df["bb_mid"]   = df["close"].rolling(20).mean()
    bb_std         = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std
    df["bb_width"] = df["bb_upper"] - df["bb_lower"]   # útil para medir volatilidad

    # Stochastic (14,3,3)
    low14  = df["low"].rolling(14).min()
    high14 = df["high"].rolling(14).max()
    df["stoch_k"] = 100 * (df["close"] - low14) / (high14 - low14)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    # ATR
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr         = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"]  = tr.rolling(14).mean()

    return df


# ── Señales ───────────────────────────────────────────────────────────────────

def get_signal(df: pd.DataFrame) -> str | None:
    last = df.iloc[-1]
    prev = df.iloc[-2]

    price_below_lower = last["close"] < last["bb_lower"]
    price_above_upper = last["close"] > last["bb_upper"]

    rsi_oversold  = last["rsi"] < 35
    rsi_overbought = last["rsi"] > 65

    # Cruce estocástico alcista (K sube por encima de D)
    stoch_cross_up   = prev["stoch_k"] < prev["stoch_d"] and last["stoch_k"] > last["stoch_d"]
    stoch_cross_down = prev["stoch_k"] > prev["stoch_d"] and last["stoch_k"] < last["stoch_d"]

    if price_below_lower and rsi_oversold and stoch_cross_up:
        return "buy"
    if price_above_upper and rsi_overbought and stoch_cross_down:
        return "sell"
    return None


# ── Bucle principal ───────────────────────────────────────────────────────────

def run():
    init_log()
    exchange = get_exchange()
    position = None

    log.info(f"Iniciado. Par: {SYMBOL} | Timeframe: {TIMEFRAME_BOT2}")

    while True:
        try:
            df = fetch_ohlcv(exchange, TIMEFRAME_BOT2, CANDLES_LIMIT)
            df = compute_indicators(df)

            current_price = get_current_price(exchange)
            atr           = df["atr"].iloc[-1]

            if position is not None:
                result = check_sl_tp(
                    current_price,
                    position["entry_price"],
                    position["stop_loss"],
                    position["take_profit"],
                    position["side"]
                )
                # También cerramos si el precio vuelve a la media (objetivo del bot)
                mean_revert = (
                    position["side"] == "buy"  and current_price >= df["bb_mid"].iloc[-1] or
                    position["side"] == "sell" and current_price <= df["bb_mid"].iloc[-1]
                )

                if result or mean_revert:
                    reason = result if result else "mean_revert"
                    exit_time = datetime.utcnow()
                    pnl, pnl_pct = log_trade(
                        BOT_NAME, SYMBOL, position["side"],
                        position["entry_price"], current_price,
                        position["size"], position["stop_loss"],
                        position["take_profit"], reason,
                        position["entry_time"], exit_time
                    )
                    log.info(f"CIERRE [{reason.upper()}] | Precio: {current_price} | PnL: {pnl:.2f} USDT ({pnl_pct:.2f}%)")
                    position = None

            if position is None:
                signal = get_signal(df)
                if signal:
                    size   = calc_position_size(current_price, atr)
                    sl, tp = calc_sl_tp(current_price, atr, signal)
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

        time.sleep(LOOP_INTERVAL_BOT2)


if __name__ == "__main__":
    run()
