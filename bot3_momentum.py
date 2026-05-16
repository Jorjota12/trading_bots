# =============================================================================
# bot3_momentum.py — Bot 3: Momentum Breakout (v2)
# =============================================================================
# Filosofía: "Entra en el breakout, protege con trailing, sal rápido"
#
# Mejoras v2:
#   - Breakout de rango → precio rompiendo máximo/mínimo de las últimas 20 velas
#   - Filtro de spread de vela → la vela de breakout debe ser grande (convicción)
#   - Trailing stop agresivo → protege ganancias desde el primer momento
#   - Filtro de hora → evita operar en horas de muy bajo volumen (00:00-04:00 UTC)
#   - Máximo trades por sesión → evita overtrading en días de ruido
#
# Indicadores:
#   - VWAP               → precio de referencia institucional
#   - EMA 9              → tendencia de corto plazo
#   - Ratio de volumen   → convicción del breakout
#   - Breakout de rango  → confirmación del nivel roto
#   - ATR (14)           → SL/TP y trailing dinámicos
#
# Timeframe: 5 minutos
# =============================================================================

import time
import logging
from datetime import datetime, timezone
import pandas as pd

from config import SYMBOL, TIMEFRAME_BOT3, CANDLES_LIMIT, LOOP_INTERVAL_BOT3
from exchange import get_exchange, fetch_ohlcv, get_current_price
from risk_manager import calc_position_size, calc_sl_tp, check_sl_tp
from logger import init_log, log_trade
from shared_state import try_acquire, release

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BOT3-MOMENTUM] %(message)s")
log = logging.getLogger("bot3")

BOT_NAME         = "Bot3_Momentum"
VOL_RATIO        = 2.0    # Volumen debe ser 2× la media (más estricto que antes)
VOLUME_WINDOW    = 20
BREAKOUT_WINDOW  = 20     # Mirar máximos/mínimos de las últimas 20 velas
CANDLE_SIZE_MIN  = 0.4    # La vela de breakout debe ser > 0.4 × ATR
TRAIL_FACTOR     = 0.4    # Trailing stop más agresivo
MAX_TRADES_DAY   = 4      # Máximo trades por día
LOW_VOL_HOURS    = range(0, 4)  # No operar entre 00:00 y 04:00 UTC


# ── Indicadores ──────────────────────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # EMA 9
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()

    # VWAP acumulado
    df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()

    # Ratio de volumen
    df["vol_avg"]   = df["volume"].rolling(VOLUME_WINDOW).mean()
    df["vol_ratio"] = df["volume"] / df["vol_avg"]

    # ATR
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr         = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"]  = tr.rolling(14).mean()

    # Breakout de rango — máximo y mínimo de las últimas N velas (sin contar la actual)
    df["range_high"] = df["high"].shift(1).rolling(BREAKOUT_WINDOW).max()
    df["range_low"]  = df["low"].shift(1).rolling(BREAKOUT_WINDOW).min()

    # Tamaño de vela actual
    df["candle_size"] = df["high"] - df["low"]

    # Pendiente EMA
    df["ema9_slope"] = df["ema9"].diff(3)

    return df


# ── Señales ───────────────────────────────────────────────────────────────────

def get_signal(df: pd.DataFrame) -> str | None:
    last = df.iloc[-1]

    # Filtro de hora — no operar en horas de bajo volumen
    current_hour = datetime.now(timezone.utc).hour
    if current_hour in LOW_VOL_HOURS:
        return None

    # Filtro de volumen
    if last["vol_ratio"] < VOL_RATIO:
        return None

    # Filtro de tamaño de vela — convicción en el movimiento
    if last["candle_size"] < last["atr"] * CANDLE_SIZE_MIN:
        return None

    # Breakout alcista: precio supera el máximo de las últimas N velas
    breakout_up   = last["close"] > last["range_high"]
    # Breakout bajista: precio rompe el mínimo de las últimas N velas
    breakout_down = last["close"] < last["range_low"]

    above_vwap = last["close"] > last["vwap"]
    below_vwap = last["close"] < last["vwap"]
    above_ema  = last["close"] > last["ema9"]
    below_ema  = last["close"] < last["ema9"]
    ema_rising = last["ema9_slope"] > 0
    ema_falling= last["ema9_slope"] < 0

    if breakout_up and above_vwap and above_ema and ema_rising:
        return "buy"
    if breakout_down and below_vwap and below_ema and ema_falling:
        return "sell"
    return None


# ── Trailing Stop ─────────────────────────────────────────────────────────────

def update_trailing_stop(position: dict, current_price: float, atr: float) -> dict:
    trail = atr * TRAIL_FACTOR
    side  = position["side"]

    if side == "buy":
        new_sl = current_price - trail
        if new_sl > position["stop_loss"]:
            position["stop_loss"] = round(new_sl, 4)
            log.info(f"TRAILING SL → {position['stop_loss']}")
    else:
        new_sl = current_price + trail
        if new_sl < position["stop_loss"]:
            position["stop_loss"] = round(new_sl, 4)
            log.info(f"TRAILING SL → {position['stop_loss']}")

    return position


# ── Bucle principal ───────────────────────────────────────────────────────────

def run():
    init_log()
    exchange     = get_exchange()
    position     = None
    trades_today = 0
    last_date    = datetime.now(timezone.utc).date()

    log.info(f"Iniciado v2. Par: {SYMBOL} | Timeframe: {TIMEFRAME_BOT3} | Breakout:{BREAKOUT_WINDOW} velas | Vol:{VOL_RATIO}x")

    while True:
        try:
            # Reset contador diario
            today = datetime.now(timezone.utc).date()
            if today != last_date:
                trades_today = 0
                last_date    = today
                log.info("Nuevo día — contador de trades reseteado")

            df = fetch_ohlcv(exchange, TIMEFRAME_BOT3, CANDLES_LIMIT)
            df = compute_indicators(df)

            current_price = get_current_price(exchange)
            atr           = df["atr"].iloc[-1]

            if position is not None:
                # Trailing stop
                position = update_trailing_stop(position, current_price, atr)

                result = check_sl_tp(
                    current_price,
                    position["entry_price"],
                    position["stop_loss"],
                    position["take_profit"],
                    position["side"]
                )

                # Cierre si la señal se invierte
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
                    release(BOT_NAME)
                    trades_today += 1
                    position = None

            if position is None:
                if trades_today >= MAX_TRADES_DAY:
                    log.info(f"Límite diario alcanzado ({MAX_TRADES_DAY} trades) — esperando mañana")
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
                        log.info(f"ENTRADA [{signal.upper()}] | Breakout confirmado | Precio: {current_price} | Vol: {df['vol_ratio'].iloc[-1]:.1f}x | SL: {sl} | TP: {tp}")

        except Exception as e:
            log.error(f"Error en el bucle: {e}")

        time.sleep(LOOP_INTERVAL_BOT3)


if __name__ == "__main__":
    run()