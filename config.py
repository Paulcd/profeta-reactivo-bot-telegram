"""Configuración del bot leída desde variables de entorno."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _parse_chat_ids(raw: str | None) -> set[int]:
    """Convierte '123,456' en {123, 456}. Vacío => sin restricción."""
    if not raw:
        return set()
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            continue
    return ids


# --- Telegram ---
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# --- Backend FastAPI (mismo que consume el frontend web) ---
API_URL: str = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
API_TIMEOUT: float = float(os.getenv("API_TIMEOUT", "15"))

# --- Modo de ejecución ---
# WEBHOOK_URL vacío  => polling (ideal para local / Background Worker).
# WEBHOOK_URL puesto => webhook (necesario en un Web Service de Render, que exige
#                        abrir un puerto). Debe ser la URL pública del servicio,
#                        ej: https://profeta-reactivo-bot-telegram.onrender.com
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")
# Render inyecta PORT automáticamente; en local cae a 8080.
PORT: int = int(os.getenv("PORT", "8080"))

# --- Control de acceso: whitelist de chat_id autorizados ---
# Vacío = cualquiera puede usar el bot (útil solo en desarrollo).
ALLOWED_CHAT_IDS: set[int] = _parse_chat_ids(os.getenv("ALLOWED_CHAT_IDS"))

# --- Anti-spam: segundos mínimos entre optimizaciones por usuario ---
MIN_SECONDS_BETWEEN_QUERIES: float = float(os.getenv("MIN_SECONDS_BETWEEN_QUERIES", "2"))


def validate() -> None:
    """Falla temprano si falta configuración crítica."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "Falta TELEGRAM_BOT_TOKEN. Configúralo como variable de entorno "
            "(BotFather te da el token)."
        )
