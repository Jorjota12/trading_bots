# =============================================================================
# bot1_trend.py — Bot 1: Trend Follower (v2)
# =============================================================================
# Filosofía: "Solo operar cuando hay tendencia real y confirmada"
#
# Mejoras v2:
#   - ADX (14) → solo entra si hay tendencia real (ADX > 25)
#   - Filtro de volumen → confirma convicción detrás del movimiento
#   - Cooldown entre trades → evita overtrading en mercado lateral
#   - Trailing Stop → protege ganancias cuando la tendencia se agota
#   - Confirmación de vela → espera cierre de vela antes de entrar
#
# Indicadores:
#   - EMA 9 / EMA 21 / EMA 50  → dirección de tendencia
#   - MACD (12,26,9)           → momentum y cruces
#   - ADX (14)                 → fuerza de la tendencia
#   - Volumen relativo         → convicción del movimiento
#   - ATR (14)                 → SL/TP dinámicos y trailing
#
# Timeframe: 5 minutos
# =============================================================================

import time
import logging
from datetime import datetime, timedelta
import pandas as pd

from config import SYMBOL, TIMEFRAME_BOT1, CANDLES_LIMIT, LOOP_INTERVAL_BOT1
from exchange import get_exchange, fetch_ohlcv, get_current_price
from risk_manager import calc_position_size, calc_sl_tp, check_sl_tp
from logger import init_log, log_trade
from shared_state import try_acquire, release

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BOT1-TREND] %(message)s")
log = logging.getLogger("bot1")

BOT_NAME        = "Bot1_Trend"
ADX_THRESHOLD   = 25      # Mínimo ADX para considerar que hay tendencia
COOLDOWN_MIN    = 15      # Minutos mínimos entre trades
TRAIL_FACTOR    = 0.5     # Trailing stop: mover SL cuando ganancia > 0.5 × ATR
VOL_FILTER      = 1.2     # Volumen debe ser 1.2× la media para entrar


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

    # ATR
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr         = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"]  = tr.rolling(14).mean()

    # ADX — mide la fuerza de la tendencia (sin importar dirección)
    df["plus_dm"]  = (df["high"] - df["high"].shift()).clip(lower=0)
    df["minus_dm"] = (df["low"].shift() - df["low"]).clip(lower=0)
    df["plus_dm"]  = df["plus_dm"].where(df["plus_dm"] > df["minus_dm"], 0)
    df["minus_dm"] = df["minus_dm"].where(df["minus_dm"] > df["plus_dm"], 0)
    atr14          = tr.rolling(14).mean()
    df["plus_di"]  = 100 * df["plus_dm"].rolling(14).mean() / atr14
    df["minus_di"] = 100 * df["minus_dm"].rolling(14).mean() / atr14
    dx             = 100 * (df["plus_di"] - df["minus_di"]).abs() / (df["plus_di"] + df["minus_di"])
    df["adx"]      = dx.rolling(14).mean()

    # Volumen relativo
    df["vol_avg"]   = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_avg"]

    return df


# ── Señales ───────────────────────────────────────────────────────────────────

def get_signal(df: pd.DataFrame) -> str | None:
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Filtro ADX — solo operar si hay tendencia real
    if last["adx"] < ADX_THRESHOLD:
        return None

    # Filtro de volumen — confirmar convicción
    if last["vol_ratio"] < VOL_FILTER:
        return None

    trend_up   = last["ema9"] > last["ema21"] > last["ema50"]
    trend_down = last["ema9"] < last["ema21"] < last["ema50"]

    macd_cross_up   = prev["macd"] < prev["macd_signal"] and last["macd"] > last["macd_signal"]
    macd_cross_down = prev["macd"] > prev["macd_signal"] and last["macd"] < last["macd_signal"]

    # Confirmación adicional: histograma MACD creciendo
    hist_growing    = last["macd_hist"] > prev["macd_hist"]
    hist_falling    = last["macd_hist"] < prev["macd_hist"]

    if trend_up and macd_cross_up and hist_growing:
        return "buy"
    if trend_down and macd_cross_down and hist_falling:
        return "sell"
    return None


# ── Trailing Stop ─────────────────────────────────────────────────────────────

def update_trailing_stop(position: dict, current_price: float, atr: float) -> dict:
    """Mueve el SL en dirección favorable cuando hay suficiente ganancia."""
    entry  = position["entry_price"]
    side   = position["side"]
    trail  = atr * TRAIL_FACTOR

    if side == "buy":
        unrealized = current_price - entry
        if unrealized > trail:
            new_sl = current_price - trail
            if new_sl > position["stop_loss"]:
                position["stop_loss"] = round(new_sl, 4)
                log.info(f"TRAILING SL actualizado → {position['stop_loss']}")
    else:
        unrealized = entry - current_price
        if unrealized > trail:
            new_sl = current_price + trail
            if new_sl < position["stop_loss"]:
                position["stop_loss"] = round(new_sl, 4)
                log.info(f"TRAILING SL actualizado → {position['stop_loss']}")

    return position


# ── Bucle principal ───────────────────────────────────────────────────────────

def run():
    init_log()
    exchange      = get_exchange()
    position      = None
    last_trade_at = None  # Para el cooldown

    log.info(f"Iniciado v2. Par: {SYMBOL} | Timeframe: {TIMEFRAME_BOT1} | ADX>{ADX_THRESHOLD} | Cooldown:{COOLDOWN_MIN}min")

    while True:
        try:
            df = fetch_ohlcv(exchange, TIMEFRAME_BOT1, CANDLES_LIMIT)
            df = compute_indicators(df)

            current_price = get_current_price(exchange)
            atr           = df["atr"].iloc[-1]

            # ── Gestión de posición abierta ──
            if position is not None:
                # Actualizar trailing stop
                position = update_trailing_stop(position, current_price, atr)

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
                    last_trade_at = datetime.utcnow()
                    position = None

            # ── Buscar nueva entrada ──
            if position is None:
                # Cooldown — esperar N minutos desde el último trade
                if last_trade_at and (datetime.utcnow() - last_trade_at) < timedelta(minutes=COOLDOWN_MIN):
                    mins_left = COOLDOWN_MIN - (datetime.utcnow() - last_trade_at).seconds // 60
                    log.info(f"Cooldown activo — {mins_left} min restantes")
                else:
                    signal = get_signal(df)
                    if signal and try_acquire(BOT_NAME):
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
                        log.info(f"ENTRADA [{signal.upper()}] | Precio: {current_price} | ADX: {df['adx'].iloc[-1]:.1f} | SL: {sl} | TP: {tp}")

        except Exception as e:
            log.error(f"Error en el bucle: {e}")

        time.sleep(LOOP_INTERVAL_BOT1)


if __name__ == "__main__":
    run()