# =============================================================================
# bot1_trend.py — Bot 1: Trend Follower (v2) — Multi-par
# =============================================================================

import time
import logging
from datetime import datetime, timedelta
import pandas as pd

from config import TIMEFRAME_BOT1, CANDLES_LIMIT, LOOP_INTERVAL_BOT1, log_file_for
from exchange import get_exchange, fetch_ohlcv, get_current_price
from risk_manager import calc_position_size, calc_sl_tp, check_sl_tp
from logger import init_log, log_trade
from shared_state import try_acquire, release

log = logging.getLogger("bot1")

BOT_NAME       = "Bot1_Trend"
ADX_THRESHOLD  = 25
COOLDOWN_MIN   = 15
TRAIL_FACTOR   = 0.5


def compute_indicators(df):
    df["ema9"]  = df["close"].ewm(span=9,  adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"]        = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = df["macd"] - df["macd_signal"]
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr         = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"]  = tr.rolling(14).mean()
    df["plus_dm"]  = (df["high"] - df["high"].shift()).clip(lower=0)
    df["minus_dm"] = (df["low"].shift() - df["low"]).clip(lower=0)
    df["plus_dm"]  = df["plus_dm"].where(df["plus_dm"] > df["minus_dm"], 0)
    df["minus_dm"] = df["minus_dm"].where(df["minus_dm"] > df["plus_dm"], 0)
    atr14 = tr.rolling(14).mean()
    df["plus_di"]  = 100 * df["plus_dm"].rolling(14).mean() / atr14
    df["minus_di"] = 100 * df["minus_dm"].rolling(14).mean() / atr14
    dx = 100 * (df["plus_di"] - df["minus_di"]).abs() / (df["plus_di"] + df["minus_di"])
    df["adx"] = dx.rolling(14).mean()
    df["vol_avg"]   = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_avg"]
    return df


def get_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    if last["adx"] < ADX_THRESHOLD:
        return None
    trend_up   = last["ema9"] > last["ema21"] > last["ema50"]
    trend_down = last["ema9"] < last["ema21"] < last["ema50"]
    macd_cross_up   = prev["macd"] < prev["macd_signal"] and last["macd"] > last["macd_signal"]
    macd_cross_down = prev["macd"] > prev["macd_signal"] and last["macd"] < last["macd_signal"]
    hist_growing = last["macd_hist"] > prev["macd_hist"]
    hist_falling = last["macd_hist"] < prev["macd_hist"]
    if trend_up and macd_cross_up and hist_growing:
        return "buy"
    if trend_down and macd_cross_down and hist_falling:
        return "sell"
    return None


def update_trailing_stop(position, current_price, atr):
    trail = atr * TRAIL_FACTOR
    if position["side"] == "buy":
        new_sl = current_price - trail
        if new_sl > position["stop_loss"]:
            position["stop_loss"] = round(new_sl, 4)
    else:
        new_sl = current_price + trail
        if new_sl < position["stop_loss"]:
            position["stop_loss"] = round(new_sl, 4)
    return position


def run(symbol: str = "BTC/USDT"):
    log_file      = log_file_for(symbol)
    lock_key      = f"{BOT_NAME}_{symbol}"
    init_log(log_file)
    exchange      = get_exchange()
    position      = None
    last_trade_at = None

    log.info(f"Iniciado v2. Par: {symbol} | TF: {TIMEFRAME_BOT1} | ADX>{ADX_THRESHOLD}")

    while True:
        try:
            df            = fetch_ohlcv(exchange, symbol, TIMEFRAME_BOT1, CANDLES_LIMIT)
            df            = compute_indicators(df)
            current_price = get_current_price(exchange, symbol)
            atr           = df["atr"].iloc[-1]

            if position is not None:
                position = update_trailing_stop(position, current_price, atr)
                result   = check_sl_tp(current_price, position["entry_price"],
                                       position["stop_loss"], position["take_profit"],
                                       position["side"])
                if result:
                    exit_time = datetime.utcnow()
                    pnl, pnl_pct = log_trade(
                        BOT_NAME, symbol, position["side"],
                        position["entry_price"], current_price,
                        position["size"], position["stop_loss"],
                        position["take_profit"], result,
                        position["entry_time"], exit_time, log_file
                    )
                    log.info(f"[{symbol}] CIERRE [{result.upper()}] | {current_price} | PnL: {pnl:.2f} USDT")
                    release(lock_key)
                    last_trade_at = datetime.utcnow()
                    position = None

            if position is None:
                cooldown_ok = not last_trade_at or \
                    (datetime.utcnow() - last_trade_at) >= timedelta(minutes=COOLDOWN_MIN)
                if cooldown_ok:
                    signal = get_signal(df)
                    if signal and try_acquire(lock_key):
                        size   = calc_position_size(current_price, atr)
                        sl, tp = calc_sl_tp(current_price, atr, signal)
                        position = {
                            "side": signal, "entry_price": current_price,
                            "size": size, "stop_loss": sl,
                            "take_profit": tp, "entry_time": datetime.utcnow(),
                        }
                        log.info(f"[{symbol}] ENTRADA [{signal.upper()}] | {current_price} | ADX:{df['adx'].iloc[-1]:.1f} | SL:{sl} | TP:{tp}")

        except Exception as e:
            import traceback
            log.error(f"[{symbol}] Error: {e}\n{traceback.format_exc()}")
            try:
                exchange = get_exchange()
            except Exception:
                pass

        time.sleep(LOOP_INTERVAL_BOT1)


if __name__ == "__main__":
    run()