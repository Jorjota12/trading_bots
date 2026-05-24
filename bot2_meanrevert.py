# =============================================================================
# bot2_meanrevert.py — Bot 2: Mean Reversion (v3) — Multi-par
# =============================================================================
# Cambios v3:
#   - RSI ajustado a 32/68 (era 28/72) — más señales
#   - Eliminado filtro anti-tendencia EMA spread — demasiado restrictivo
#   - Mantenidos: confirmación de vela, ATR mínimo, timeout 60min
# =============================================================================

import time
import logging
from datetime import datetime
import pandas as pd

from config import TIMEFRAME_BOT2, CANDLES_LIMIT, LOOP_INTERVAL_BOT2, log_file_for
from exchange import get_exchange, fetch_ohlcv, get_current_price
from risk_manager import calc_position_size, calc_sl_tp, check_sl_tp
from logger import init_log, log_trade
from shared_state import try_acquire, release

log = logging.getLogger("bot2")

BOT_NAME       = "Bot2_MeanReversion"
RSI_OVERSOLD   = 32     # era 28 — más señales
RSI_OVERBOUGHT = 68     # era 72 — más señales
ATR_MIN_FACTOR = 0.2    # era 0.3 — menos restrictivo
MAX_TRADE_MIN  = 60


def compute_indicators(df):
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    df["bb_mid"]   = df["close"].rolling(20).mean()
    bb_std         = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std
    low14  = df["low"].rolling(14).min()
    high14 = df["high"].rolling(14).max()
    df["stoch_k"] = 100 * (df["close"] - low14) / (high14 - low14)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    return df


def get_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Filtro ATR mínimo
    if (last["atr"] / last["close"] * 100) < ATR_MIN_FACTOR:
        return None

    stoch_up   = prev["stoch_k"] < prev["stoch_d"] and last["stoch_k"] > last["stoch_d"]
    stoch_down = prev["stoch_k"] > prev["stoch_d"] and last["stoch_k"] < last["stoch_d"]
    prev_bull  = prev["close"] > prev["open"]
    prev_bear  = prev["close"] < prev["open"]

    if last["close"] < last["bb_lower"] and last["rsi"] < RSI_OVERSOLD and stoch_up and prev_bull:
        return "buy"
    if last["close"] > last["bb_upper"] and last["rsi"] > RSI_OVERBOUGHT and stoch_down and prev_bear:
        return "sell"
    return None


def should_exit(position, current_price, df):
    last   = df.iloc[-1]
    result = check_sl_tp(current_price, position["entry_price"],
                         position["stop_loss"], position["take_profit"],
                         position["side"])
    if result:
        return result
    if position["side"] == "buy"  and current_price >= last["bb_mid"]:
        return "mean_revert"
    if position["side"] == "sell" and current_price <= last["bb_mid"]:
        return "mean_revert"
    if position["side"] == "buy"  and last["rsi"] > 50:
        return "rsi_normalized"
    if position["side"] == "sell" and last["rsi"] < 50:
        return "rsi_normalized"
    if (datetime.utcnow() - position["entry_time"]).total_seconds() / 60 > MAX_TRADE_MIN:
        return "timeout"
    return None


def run(symbol: str = "SOL/USDT"):
    log_file = log_file_for(symbol)
    lock_key = f"{BOT_NAME}_{symbol}"
    init_log(log_file)
    exchange = get_exchange()
    position = None

    log.info(f"Iniciado v3. Par: {symbol} | TF: {TIMEFRAME_BOT2} | RSI:{RSI_OVERSOLD}/{RSI_OVERBOUGHT}")

    while True:
        try:
            df            = fetch_ohlcv(exchange, symbol, TIMEFRAME_BOT2, CANDLES_LIMIT)
            df            = compute_indicators(df)
            current_price = get_current_price(exchange, symbol)
            atr           = df["atr"].iloc[-1]

            if position is not None:
                reason = should_exit(position, current_price, df)
                if reason:
                    exit_time = datetime.utcnow()
                    pnl, pnl_pct = log_trade(
                        BOT_NAME, symbol, position["side"],
                        position["entry_price"], current_price,
                        position["size"], position["stop_loss"],
                        position["take_profit"], reason,
                        position["entry_time"], exit_time, log_file
                    )
                    log.info(f"[{symbol}] CIERRE [{reason.upper()}] | {current_price} | PnL: {pnl:.2f} USDT")
                    release(lock_key)
                    position = None

            if position is None:
                signal = get_signal(df)
                if signal and try_acquire(lock_key):
                    size   = calc_position_size(current_price, atr)
                    sl, tp = calc_sl_tp(current_price, atr, signal)
                    position = {
                        "side": signal, "entry_price": current_price,
                        "size": size, "stop_loss": sl,
                        "take_profit": tp, "entry_time": datetime.utcnow(),
                    }
                    log.info(f"[{symbol}] ENTRADA [{signal.upper()}] | {current_price} | RSI:{df['rsi'].iloc[-1]:.1f} | SL:{sl} | TP:{tp}")

        except Exception as e:
            import traceback
            log.error(f"[{symbol}] Error: {e}\n{traceback.format_exc()}")
            try:
                exchange = get_exchange()
            except Exception:
                pass

        time.sleep(LOOP_INTERVAL_BOT2)


if __name__ == "__main__":
    run()