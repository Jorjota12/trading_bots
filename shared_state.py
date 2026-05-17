# =============================================================================
# shared_state.py — Locks independientes por par
# =============================================================================
# Cada par tiene su propio lock — BTC, ETH y SOL operan de forma independiente
# Dentro de cada par, solo un bot puede tener posición abierta a la vez

import threading

_locks = {}
_active = {}
_lock_meta = threading.Lock()


def _get_lock(key: str) -> threading.Lock:
    with _lock_meta:
        if key not in _locks:
            _locks[key] = threading.Lock()
            _active[key] = None
    return _locks[key]


def try_acquire(bot_key: str) -> bool:
    """
    bot_key tiene formato "Bot1_Trend_BTC" — el lock es por par.
    Extrae el par y bloquea solo ese par.
    """
    pair_key = bot_key.split("_")[-1]  # BTC, ETH, SOL
    lock = _get_lock(pair_key)
    acquired = lock.acquire(blocking=False)
    if acquired:
        with _lock_meta:
            _active[pair_key] = bot_key
    return acquired


def release(bot_key: str):
    pair_key = bot_key.split("_")[-1]
    lock = _get_lock(pair_key)
    with _lock_meta:
        _active[pair_key] = None
    try:
        lock.release()
    except RuntimeError:
        pass


def who_has_position(pair: str) -> str | None:
    return _active.get(pair)