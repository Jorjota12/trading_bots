# =============================================================================
# risk_manager.py — Gestión de riesgo compartida por los 3 bots
# =============================================================================

from config import CAPITAL_PER_BOT, RISK_PER_TRADE, ATR_SL_MULTIPLIER, ATR_TP_MULTIPLIER


def calc_position_size(entry_price: float, atr: float) -> float:
    """
    Calcula cuántas unidades de la moneda base comprar.

    Lógica:
      - Riesgo máximo por trade = CAPITAL × RISK_PER_TRADE  (ej. 1000 × 0.01 = 10 USDT)
      - Stop Loss distance = ATR × ATR_SL_MULTIPLIER
      - Tamaño = Riesgo / SL_distance

    Así, si el SL salta, perdemos exactamente el % configurado.
    """
    capital_at_risk = CAPITAL_PER_BOT * RISK_PER_TRADE
    sl_distance     = atr * ATR_SL_MULTIPLIER
    if sl_distance <= 0:
        return 0.0
    size = capital_at_risk / sl_distance
    return round(size, 6)


def calc_sl_tp(entry_price: float, atr: float, side: str):
    """
    Calcula niveles de Stop Loss y Take Profit dinámicos basados en ATR.

    side: 'buy' o 'sell'
    Devuelve: (stop_loss, take_profit)
    """
    sl_dist = atr * ATR_SL_MULTIPLIER
    tp_dist = atr * ATR_TP_MULTIPLIER

    if side == "buy":
        stop_loss   = entry_price - sl_dist
        take_profit = entry_price + tp_dist
    else:
        stop_loss   = entry_price + sl_dist
        take_profit = entry_price - tp_dist

    return round(stop_loss, 4), round(take_profit, 4)


def check_sl_tp(current_price: float, entry_price: float,
                stop_loss: float, take_profit: float, side: str) -> str | None:
    """
    Comprueba si el precio actual ha tocado SL o TP.
    Devuelve: 'sl', 'tp', o None si no hay que cerrar.
    """
    if side == "buy":
        if current_price <= stop_loss:
            return "sl"
        if current_price >= take_profit:
            return "tp"
    else:  # sell / short
        if current_price >= stop_loss:
            return "sl"
        if current_price <= take_profit:
            return "tp"
    return None
