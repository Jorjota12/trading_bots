# =============================================================================
# bot2_meanrevert.py — Bot 2: Mean Reversion (v2)
# =============================================================================
# Filosofía: "Los precios extremos vuelven a la media — pero solo en rangos"
#
# Mejoras v2:
#   - Filtro de ATR mínimo → evita entrar cuando no hay movimiento suficiente
#   - Filtro anti-tendencia → no opera si hay tendencia fuerte (EMA divergiendo)
#   - RSI ajustado → umbrales más extremos (28/72) para señales más fiables
#   - Confirmación de vela → la vela anterior debe cerrar en dirección correcta
#   - Salida optimizada → cierra en la media Bollinger o cuando RSI se normaliza
#   - Máximo tiempo en trade → cierra si lleva demasiado tiempo sin moverse
#
# Indicadores:
#   - RSI (14)                   → sobrecompra/sobreventa
#   - Bandas de Bollinger (20,2) → límites estadísticos
#   - Stochastic (14,3,3)        → agotamiento del movimiento
#   - EMA 50                     → filtro anti-tendencia
#   - ATR (14)                   → SL/TP dinámicos
#
# Timeframe: 3 minutos
# =============================================================================

import time
import logging
from datetime import datetime, timedelta
import pandas as pd

from config import SYMBOL, TIMEFRAME_BOT2, CANDLES_LIMIT, LOOP_INTERVAL_BOT2
from exchange import get_exchange, fetch_ohlcv, get_current_price
from risk_manager import calc_position_size, calc_sl_tp, check_sl_tp
from logger import init_log, log_trade
from shared_state import try_acquire, release

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BOT2-MEAN] %(message)s")
log = logging.getLogger("bot2")

BOT_NAME        = "Bot2_MeanReversion"
RSI_OVERSOLD    = 28     # Más extremo que antes (era 35)
RSI_OVERBOUGHT  = 72     # Más extremo que antes (era 65)
ATR_MIN_FACTOR  = 0.3    # ATR mínimo como % del precio para confirmar volatilidad
MAX_TRADE_MIN   = 60     # Cerrar trade si lleva más de 60 min abierto sin resultado


# ── Indicadores ──────────────────────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # RSI
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # Bandas de Bollinger
    df["bb_mid"]   = df["close"].rolling(20).mean()
    bb_std         = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std
    df["bb_width"] = df["bb_upper"] - df["bb_lower"]

    # Stochastic (14,3,3)
    low14  = df["low"].rolling(14).min()
    high14 = df["high"].rolling(14).max()
    df["stoch_k"] = 100 * (df["close"] - low14) / (high14 - low14)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    # EMA 50 para filtro anti-tendencia
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()

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

    # Filtro ATR mínimo — necesitamos algo de volatilidad para que haya reversión
    atr_pct = last["atr"] / last["close"] * 100
    if atr_pct < ATR_MIN_FACTOR:
        return None

    # Filtro anti-tendencia — si las EMAs divergen mucho, no es un mercado de rango
    ema_spread = abs(last["ema20"] - last["ema50"]) / last["close"] * 100
    if ema_spread > 0.3:  # más de 0.3% de diferencia = tendencia, no rango
        return None

    price_below_lower = last["close"] < last["bb_lower"]
    price_above_upper = last["close"] > last["bb_upper"]

    rsi_oversold   = last["rsi"] < RSI_OVERSOLD
    rsi_overbought = last["rsi"] > RSI_OVERBOUGHT

    # Cruce estocástico
    stoch_cross_up   = prev["stoch_k"] < prev["stoch_d"] and last["stoch_k"] > last["stoch_d"]
    stoch_cross_down = prev["stoch_k"] > prev["stoch_d"] and last["stoch_k"] < last["stoch_d"]

    # Confirmación de vela: la vela anterior debe ser de color correcto
    prev_candle_bullish = prev["close"] > prev["open"]
    prev_candle_bearish = prev["close"] < prev["open"]

    if price_below_lower and rsi_oversold and stoch_cross_up and prev_candle_bullish:
        return "buy"
    if price_above_upper and rsi_overbought and stoch_cross_down and prev_candle_bearish:
        return "sell"
    return None


# ── Condiciones de salida ─────────────────────────────────────────────────────

def should_exit(position: dict, current_price: float, df: pd.DataFrame) -> str | None:
    last = df.iloc[-1]

    # Salida por SL/TP
    result = check_sl_tp(
        current_price,
        position["entry_price"],
        position["stop_loss"],
        position["take_profit"],
        position["side"]
    )
    if result:
        return result

    # Salida cuando el precio vuelve a la media de Bollinger (objetivo cumplido)
    if position["side"] == "buy" and current_price >= last["bb_mid"]:
        return "mean_revert"
    if position["side"] == "sell" and current_price <= last["bb_mid"]:
        return "mean_revert"

    # Salida si RSI se normaliza (ya no está en extremo)
    if position["side"] == "buy" and last["rsi"] > 50:
        return "rsi_normalized"
    if position["side"] == "sell" and last["rsi"] < 50:
        return "rsi_normalized"

    # Salida por tiempo máximo
    elapsed = (datetime.utcnow() - position["entry_time"]).total_seconds() / 60
    if elapsed > MAX_TRADE_MIN:
        return "timeout"

    return None


# ── Bucle principal ───────────────────────────────────────────────────────────

def run():
    init_log()
    exchange = get_exchange()
    position = None

    log.info(f"Iniciado v2. Par: {SYMBOL} | Timeframe: {TIMEFRAME_BOT2} | RSI:{RSI_OVERSOLD}/{RSI_OVERBOUGHT}")

    while True:
        try:
            df = fetch_ohlcv(exchange, TIMEFRAME_BOT2, CANDLES_LIMIT)
            df = compute_indicators(df)

            current_price = get_current_price(exchange)
            atr           = df["atr"].iloc[-1]

            if position is not None:
                reason = should_exit(position, current_price, df)
                if reason:
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
                    position = None

            if position is None:
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
                    log.info(f"ENTRADA [{signal.upper()}] | Precio: {current_price} | RSI: {df['rsi'].iloc[-1]:.1f} | SL: {sl} | TP: {tp}")

        except Exception as e:
            log.error(f"Error en el bucle: {e}")

        time.sleep(LOOP_INTERVAL_BOT2)


if __name__ == "__main__":
    run()