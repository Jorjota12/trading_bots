# =============================================================================
# bot3_momentum.py — Bot 3: Momentum Breakout (v2) — Multi-par
# =============================================================================

import time
import logging
from datetime import datetime, timezone
import pandas as pd

from config import TIMEFRAME_BOT3, CANDLES_LIMIT, LOOP_INTERVAL_BOT3, log_file_for
from exchange import get_exchange, fetch_ohlcv, get_current_price
from risk_manager import calc_position_size, calc_sl_tp, check_sl_tp
from logger import init_log, log_trade
from shared_state import try_acquire, release

log = logging.getLogger("bot3")

BOT_NAME        = "Bot3_Momentum"
VOL_RATIO       = 1.2
VOLUME_WINDOW   = 20
BREAKOUT_WINDOW = 20
CANDLE_SIZE_MIN = 0.4
TRAIL_FACTOR    = 0.4
MAX_TRADES_DAY  = 4
LOW_VOL_HOURS   = range(0, 4)


def compute_indicators(df):
    df["ema9"]  = df["close"].ewm(span=9, adjust=False).mean()
    df["vwap"]  = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
    df["vol_avg"]    = df["volume"].rolling(VOLUME_WINDOW).mean()
    df["vol_ratio"]  = df["volume"] / df["vol_avg"]
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"]        = tr.rolling(14).mean()
    df["range_high"] = df["high"].shift(1).rolling(BREAKOUT_WINDOW).max()
    df["range_low"]  = df["low"].shift(1).rolling(BREAKOUT_WINDOW).min()
    df["candle_size"]= df["high"] - df["low"]
    df["ema9_slope"] = df["ema9"].diff(3)
    return df


def get_signal(df):
    last = df.iloc[-1]
    if datetime.now(timezone.utc).hour in LOW_VOL_HOURS:
        return None
    if last["vol_ratio"] < VOL_RATIO:
        return None
    if last["candle_size"] < last["atr"] * CANDLE_SIZE_MIN:
        return None
    breakout_up   = last["close"] > last["range_high"]
    breakout_down = last["close"] < last["range_low"]
    if breakout_up and last["close"] > last["vwap"] and last["close"] > last["ema9"] and last["ema9_slope"] > 0:
        return "buy"
    if breakout_down and last["close"] < last["vwap"] and last["close"] < last["ema9"] and last["ema9_slope"] < 0:
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
    log_file     = log_file_for(symbol)
    lock_key     = f"{BOT_NAME}_{symbol}"
    init_log(log_file)
    exchange     = get_exchange()
    position     = None
    trades_today = 0
    last_date    = datetime.now(timezone.utc).date()

    log.info(f"Iniciado v2. Par: {symbol} | TF: {TIMEFRAME_BOT3} | Breakout:{BREAKOUT_WINDOW} | Vol:{VOL_RATIO}x")

    while True:
        try:
            today = datetime.now(timezone.utc).date()
            if today != last_date:
                trades_today = 0
                last_date    = today

            df            = fetch_ohlcv(exchange, symbol, TIMEFRAME_BOT3, CANDLES_LIMIT)
            df            = compute_indicators(df)
            current_price = get_current_price(exchange, symbol)
            atr           = df["atr"].iloc[-1]

            if position is not None:
                position = update_trailing_stop(position, current_price, atr)
                result   = check_sl_tp(current_price, position["entry_price"],
                                       position["stop_loss"], position["take_profit"],
                                       position["side"])
                signal_now     = get_signal(df)
                signal_flipped = (position["side"] == "buy"  and signal_now == "sell") or \
                                 (position["side"] == "sell" and signal_now == "buy")
                if result or signal_flipped:
                    reason    = result if result else "signal_flip"
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
                    trades_today += 1
                    position = None

            if position is None and trades_today < MAX_TRADES_DAY:
                signal = get_signal(df)
                if signal and try_acquire(lock_key):
                    size   = calc_position_size(current_price, atr)
                    sl, tp = calc_sl_tp(current_price, atr, signal)
                    position = {
                        "side": signal, "entry_price": current_price,
                        "size": size, "stop_loss": sl,
                        "take_profit": tp, "entry_time": datetime.utcnow(),
                    }
                    log.info(f"[{symbol}] ENTRADA [{signal.upper()}] | {current_price} | Vol:{df['vol_ratio'].iloc[-1]:.1f}x | SL:{sl} | TP:{tp}")

        except Exception as e:
            import traceback
            log.error(f"[{symbol}] Error: {e}\n{traceback.format_exc()}")
            try:
                exchange = get_exchange()
            except Exception:
                pass

        time.sleep(LOOP_INTERVAL_BOT3)


if __name__ == "__main__":
    run()