"""Cliente HTTP asíncrono para el backend FastAPI 'Profeta de Reactivos'.

Reutiliza los mismos endpoints que el frontend web:
  - POST /api/optimizar
  - GET  /api/modelos/status
"""
from __future__ import annotations

from typing import Any

import httpx

from config import API_TIMEOUT, API_URL


class ApiError(Exception):
    """Error legible para mostrar al operario en Telegram."""


async def optimizar(inputs: dict[str, float]) -> dict[str, Any]:
    """Llama a POST /api/optimizar y devuelve el OptimizationResult.

    inputs: temperatura, ph, ley_mineral, caudal, turbidez, colector_actual
    """
    url = f"{API_URL}/api/optimizar"
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.post(url, json=inputs)
    except httpx.TimeoutException as exc:
        raise ApiError(
            "El sistema tardó demasiado en responder. Intenta de nuevo en unos segundos."
        ) from exc
    except httpx.RequestError as exc:
        raise ApiError(
            "No se pudo conectar con el sistema de optimización. Avisa a soporte."
        ) from exc

    if resp.status_code == 422:
        # Rango inválido: no debería pasar con los botones, pero es la red de seguridad.
        detalle = _extract_error(resp)
        raise ApiError(
            "Ese valor está fuera de rango operativo. Por favor elige otra opción.\n"
            f"({detalle})"
        )
    if resp.status_code >= 500:
        raise ApiError(
            "El sistema de optimización tuvo un error interno. Intenta de nuevo."
        )
    if resp.status_code != 200:
        raise ApiError(f"Respuesta inesperada del sistema (HTTP {resp.status_code}).")

    return resp.json()


async def modelos_status() -> dict[str, Any]:
    """Llama a GET /api/modelos/status y devuelve el ModeloStatus."""
    url = f"{API_URL}/api/modelos/status"
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.get(url)
    except httpx.TimeoutException as exc:
        raise ApiError("El sistema tardó demasiado en responder.") from exc
    except httpx.RequestError as exc:
        raise ApiError(
            "No se pudo conectar con el sistema de optimización. Avisa a soporte."
        ) from exc

    if resp.status_code != 200:
        raise ApiError(f"No se pudo leer el estado del sistema (HTTP {resp.status_code}).")

    return resp.json()


def _extract_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            return str(data["error"])
    except Exception:  # noqa: BLE001
        pass
    return "parámetros fuera de rango"
