# =============================================================================
# comparator.py — Dashboard de comparación de rendimiento de los 3 bots
# =============================================================================
# Ejecuta este script en cualquier momento para ver el estado actual:
#   python comparator.py
# =============================================================================

import pandas as pd
import numpy as np
from tabulate import tabulate
from colorama import init, Fore, Style

from config import LOG_FILE, CAPITAL_PER_BOT

init(autoreset=True)


def load_trades() -> pd.DataFrame:
    try:
        df = pd.read_csv(LOG_FILE)
        df["entry_time"] = pd.to_datetime(df["entry_time"])
        df["exit_time"]  = pd.to_datetime(df["exit_time"])
        return df
    except FileNotFoundError:
        print(Fore.RED + f"No se encontró {LOG_FILE}. ¿Has ejecutado los bots ya?")
        return pd.DataFrame()


def calc_metrics(trades: pd.DataFrame, bot_name: str) -> dict:
    """Calcula todas las métricas para un bot."""
    bot_trades = trades[trades["bot"] == bot_name].copy()

    if bot_trades.empty:
        return {"bot": bot_name, "trades": 0}

    total_trades = len(bot_trades)
    wins         = bot_trades[bot_trades["pnl_usdt"] > 0]
    losses       = bot_trades[bot_trades["pnl_usdt"] <= 0]

    win_rate     = len(wins) / total_trades * 100
    total_pnl    = bot_trades["pnl_usdt"].sum()
    avg_win      = wins["pnl_usdt"].mean() if len(wins) > 0 else 0
    avg_loss     = losses["pnl_usdt"].mean() if len(losses) > 0 else 0

    # Profit Factor = suma ganancias / suma pérdidas absolutas
    gross_profit = wins["pnl_usdt"].sum() if len(wins) > 0 else 0
    gross_loss   = abs(losses["pnl_usdt"].sum()) if len(losses) > 0 else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Expectancy = ganancia esperada por trade
    expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)

    # Max Drawdown
    cumulative = bot_trades["pnl_usdt"].cumsum()
    rolling_max = cumulative.cummax()
    drawdown    = cumulative - rolling_max
    max_drawdown = drawdown.min()

    # Sharpe Ratio (simplificado, asume risk-free = 0)
    returns = bot_trades["pnl_pct"] / 100
    sharpe  = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

    # Duración media de los trades
    avg_duration = bot_trades["duration_min"].mean()

    # Desglose de cierres
    tp_count    = len(bot_trades[bot_trades["exit_reason"] == "tp"])
    sl_count    = len(bot_trades[bot_trades["exit_reason"] == "sl"])
    other_count = total_trades - tp_count - sl_count

    return {
        "bot":           bot_name,
        "trades":        total_trades,
        "win_rate":      round(win_rate, 1),
        "total_pnl":     round(total_pnl, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy":    round(expectancy, 2),
        "max_drawdown":  round(max_drawdown, 2),
        "sharpe":        round(sharpe, 2),
        "avg_win":       round(avg_win, 2),
        "avg_loss":      round(avg_loss, 2),
        "avg_duration":  round(avg_duration, 1),
        "tp_exits":      tp_count,
        "sl_exits":      sl_count,
        "other_exits":   other_count,
    }


def color_value(val, good_if_positive=True):
    """Colorea un valor en verde si es bueno, rojo si es malo."""
    if isinstance(val, (int, float)):
        if good_if_positive:
            color = Fore.GREEN if val > 0 else Fore.RED
        else:
            color = Fore.RED if val > 0 else Fore.GREEN
        return f"{color}{val}{Style.RESET_ALL}"
    return val


def print_dashboard(metrics_list: list[dict]):
    print("\n" + "="*70)
    print(Fore.CYAN + Style.BRIGHT + "  📊 DASHBOARD DE COMPARACIÓN DE BOTS — PAPER TRADING")
    print("="*70)

    if not metrics_list or metrics_list[0].get("trades", 0) == 0:
        print(Fore.YELLOW + "Aún no hay trades registrados.")
        return

    # Tabla principal
    headers = ["Métrica", "Bot1 Trend", "Bot2 MeanRev", "Bot3 Momentum"]
    rows = []

    metrics_keys = [
        ("trades",        "Nº Trades",          True),
        ("win_rate",      "Win Rate (%)",        True),
        ("total_pnl",     "PnL Total (USDT)",    True),
        ("profit_factor", "Profit Factor",       True),
        ("expectancy",    "Expectancy (USDT)",   True),
        ("max_drawdown",  "Max Drawdown (USDT)", False),
        ("sharpe",        "Sharpe Ratio",        True),
        ("avg_win",       "Ganancia Media",      True),
        ("avg_loss",      "Pérdida Media",       False),
        ("avg_duration",  "Duración Media (min)",True),
        ("tp_exits",      "Cierres por TP",      True),
        ("sl_exits",      "Cierres por SL",      False),
    ]

    for key, label, good_positive in metrics_keys:
        row = [label]
        for m in metrics_list:
            val = m.get(key, "N/A")
            row.append(color_value(val, good_positive) if val != "N/A" else "N/A")
        rows.append(row)

    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))

    # Ranking
    print("\n" + Fore.CYAN + Style.BRIGHT + "  🏆 RANKING")
    ranked = sorted(
        [m for m in metrics_list if m.get("trades", 0) > 0],
        key=lambda x: x.get("total_pnl", 0),
        reverse=True
    )
    for i, m in enumerate(ranked, 1):
        medal = ["🥇", "🥈", "🥉"][i-1]
        pnl_color = Fore.GREEN if m["total_pnl"] > 0 else Fore.RED
        print(f"  {medal} {m['bot']:25s} | PnL: {pnl_color}{m['total_pnl']:+.2f} USDT{Style.RESET_ALL} | "
              f"WR: {m['win_rate']}% | PF: {m['profit_factor']}")

    # Recomendación automática
    print("\n" + Fore.CYAN + Style.BRIGHT + "  💡 ANÁLISIS AUTOMÁTICO")
    for m in metrics_list:
        if m.get("trades", 0) < 5:
            print(f"  {m['bot']}: Pocos trades aún — necesita más datos para evaluar.")
        elif m.get("profit_factor", 0) > 1.5 and m.get("win_rate", 0) > 50:
            print(f"  {Fore.GREEN}{m['bot']}: ✅ Buen rendimiento. Profit Factor > 1.5 y WR > 50%")
        elif m.get("max_drawdown", 0) < -50:
            print(f"  {Fore.RED}{m['bot']}: ⚠️  Drawdown elevado. Revisar gestión de riesgo.")
        else:
            print(f"  {m['bot']}: 🔄 Rendimiento neutro. Sigue acumulando datos.")

    print("="*70 + "\n")


def main():
    trades = load_trades()
    if trades.empty:
        return

    bot_names    = ["Bot1_Trend", "Bot2_MeanReversion", "Bot3_Momentum"]
    metrics_list = [calc_metrics(trades, name) for name in bot_names]

    print_dashboard(metrics_list)

    # Exportar resumen a CSV
    summary_df = pd.DataFrame(metrics_list)
    summary_df.to_csv("comparison_summary.csv", index=False)
    print(f"Resumen exportado a comparison_summary.csv")


if __name__ == "__main__":
    main()
