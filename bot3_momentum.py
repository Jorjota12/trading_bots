# =============================================================================
# bot3_momentum.py — Bot 3: Momentum Breakout
# =============================================================================
# Filosofía: "El momentum se mantiene: entra fuerte, sale rápido"
#
# Indicadores:
#   - VWAP               → precio justo del día ponderado por volumen
#   - EMA 9              → tendencia de corto plazo
#   - Ratio de volumen   → confirma que hay convicción detrás del movimiento
#   - ATR (14)           → Stop Loss y Take Profit dinámicos (más ajustados)
#
# Lógica de entrada:
#   COMPRA  si precio > VWAP  AND  precio > EMA9  AND  volumen actual > 1.5× media volumen
#   VENTA   si precio < VWAP  AND  precio < EMA9  AND  volumen actual > 1.5× media volumen
#
# Timeframe: 1 minuto (el más agresivo de los tres)
# =============================================================================

import time
import logging
from datetime import datetime
import pandas as pd

from config import SYMBOL, TIMEFRAME_BOT3, CANDLES_LIMIT, LOOP_INTERVAL_BOT3
from exchange import get_exchange, fetch_ohlcv, get_current_price
from risk_manager import calc_position_size, calc_sl_tp, check_sl_tp
from logger import init_log, log_trade

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BOT3-MOMENTUM] %(message)s")
log = logging.getLogger("bot3")

BOT_NAME    = "Bot3_Momentum"
VOL_RATIO   = 1.5    # El volumen actual debe ser al menos 1.5× la media
VOLUME_WINDOW = 20   # Ventana para calcular el volumen medio


# ── Indicadores ──────────────────────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # EMA 9
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()

    # VWAP (reinicia cada sesión — aquí lo calculamos acumulado sobre las velas disponibles)
    # En 1m con 200 velas = ~3.3 horas, suficiente para un VWAP intradía útil
    df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()

    # Ratio de volumen: volumen actual vs media de los últimos N períodos
    df["vol_avg"]   = df["volume"].rolling(VOLUME_WINDOW).mean()
    df["vol_ratio"] = df["volume"] / df["vol_avg"]

    # ATR
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr         = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"]  = tr.rolling(14).mean()

    # Pendiente de EMA (¿está acelerando?)
    df["ema9_slope"] = df["ema9"].diff(3)   # diferencia entre hace 3 velas y ahora

    return df


# ── Señales ───────────────────────────────────────────────────────────────────

def get_signal(df: pd.DataFrame) -> str | None:
    last = df.iloc[-1]

    above_vwap = last["close"] > last["vwap"]
    below_vwap = last["close"] < last["vwap"]

    above_ema  = last["close"] > last["ema9"]
    below_ema  = last["close"] < last["ema9"]

    volume_spike = last["vol_ratio"] >= VOL_RATIO

    # Pendiente positiva/negativa de EMA confirma aceleración
    ema_rising  = last["ema9_slope"] > 0
    ema_falling = last["ema9_slope"] < 0

    if above_vwap and above_ema and volume_spike and ema_rising:
        return "buy"
    if below_vwap and below_ema and volume_spike and ema_falling:
        return "sell"
    return None


# ── Bucle principal ───────────────────────────────────────────────────────────

def run():
    init_log()
    exchange = get_exchange()
    position = None

    log.info(f"Iniciado. Par: {SYMBOL} | Timeframe: {TIMEFRAME_BOT3}")

    while True:
        try:
            df = fetch_ohlcv(exchange, TIMEFRAME_BOT3, CANDLES_LIMIT)
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

                # El momentum bot también cierra si la señal se invierte (momentum agotado)
                signal_now = get_signal(df)
                signal_flipped = (
                    position["side"] == "buy"  and signal_now == "sell" or
                    position["side"] == "sell" and signal_now == "buy"
                )

                if result or signal_flipped:
                    reason = result if result else "signal_flip"
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

        time.sleep(LOOP_INTERVAL_BOT3)


if __name__ == "__main__":
    run()
