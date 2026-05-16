# =============================================================================
# shared_state.py — Estado compartido entre los 3 bots
# =============================================================================
# Evita que dos bots abran posición al mismo tiempo en el mismo par

import threading

# Lock global — solo un bot puede tener posición abierta a la vez
_position_lock = threading.Lock()
_active_bot    = None   # Qué bot tiene la posición ahora mismo


def try_acquire(bot_name: str) -> bool:
    """Intenta adquirir el derecho a abrir una posición. Devuelve True si lo consigue."""
    global _active_bot
    acquired = _position_lock.acquire(blocking=False)
    if acquired:
        _active_bot = bot_name
    return acquired


def release(bot_name: str):
    """Libera el lock cuando el bot cierra su posición."""
    global _active_bot
    if _active_bot == bot_name:
        _active_bot = None
        try:
            _position_lock.release()
        except RuntimeError:
            pass  # ya estaba liberado


def who_has_position() -> str | None:
    """Devuelve el nombre del bot que tiene posición abierta, o None."""
    return _active_bot
