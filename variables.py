"""Definición de las 6 variables de proceso y perfiles predefinidos.

Cada opción de rango envía el PUNTO MEDIO del rango como valor numérico a la API,
garantizando que siempre esté dentro del rango operativo (evita el 422 del backend).
"""
from __future__ import annotations

from typing import NamedTuple


class Option(NamedTuple):
    label: str   # texto del botón
    value: float  # valor numérico enviado a la API (punto medio del rango)


class Variable(NamedTuple):
    key: str       # nombre del campo en la API
    titulo: str    # texto para el operario
    unidad: str
    options: list[Option]


# Orden en el que se preguntan las variables (flujo manual).
VARIABLES: list[Variable] = [
    Variable(
        key="temperatura",
        titulo="🌡️ Temperatura de pulpa",
        unidad="°C",
        options=[
            Option("20–23 °C", 21.5),
            Option("24–27 °C", 25.5),
            Option("28–31 °C", 29.5),
            Option("32–35 °C", 33.5),
        ],
    ),
    Variable(
        key="ph",
        titulo="⚗️ pH de la pulpa",
        unidad="pH",
        options=[
            Option("6.5–6.8", 6.65),
            Option("6.9–7.2", 7.05),
            Option("7.3–7.6", 7.45),
            Option("7.7–8.0", 7.85),
        ],
    ),
    Variable(
        key="ley_mineral",
        titulo="⛏️ Ley de mineral (cobre)",
        unidad="%",
        options=[
            Option("0.70–0.78 %", 0.74),
            Option("0.79–0.88 %", 0.835),
            Option("0.89–0.94 %", 0.915),
            Option("0.95–1.00 %", 0.975),
        ],
    ),
    Variable(
        key="caudal",
        titulo="💧 Caudal de pulpa",
        unidad="m³/h",
        options=[
            Option("400–450", 425.0),
            Option("451–500", 475.0),
            Option("501–550", 525.0),
            Option("551–600", 575.0),
        ],
    ),
    Variable(
        key="turbidez",
        titulo="🌫️ Turbidez",
        unidad="NTU",
        options=[
            Option("20–30", 25.0),
            Option("31–40", 35.0),
            Option("41–50", 45.0),
            Option("51–60", 55.0),
        ],
    ),
    Variable(
        key="colector_actual",
        titulo="🧪 Dosis de colector ACTUAL",
        unidad="L/h",
        options=[
            Option("45–47", 46.0),
            Option("48–50", 49.0),
            Option("51–53", 52.0),
            Option("54–55", 54.5),
        ],
    ),
]

VARIABLES_BY_KEY = {v.key: v for v in VARIABLES}


class Profile(NamedTuple):
    key: str
    label: str
    inputs: dict[str, float]


# Perfiles rápidos para el MVP (menos fricción que 6 preguntas).
PROFILES: list[Profile] = [
    Profile(
        key="tipica",
        label="🟢 Condición típica",
        inputs={
            "temperatura": 28.5,
            "ph": 7.15,
            "ley_mineral": 0.88,
            "caudal": 505.0,
            "turbidez": 39.0,
            "colector_actual": 52.0,
        },
    ),
    Profile(
        key="alta_turbidez",
        label="🌫️ Alta turbidez",
        inputs={
            "temperatura": 28.5,
            "ph": 7.15,
            "ley_mineral": 0.85,
            "caudal": 520.0,
            "turbidez": 55.0,
            "colector_actual": 52.0,
        },
    ),
    Profile(
        key="mineral_pobre",
        label="🔻 Mineral pobre",
        inputs={
            "temperatura": 28.0,
            "ph": 7.2,
            "ley_mineral": 0.74,
            "caudal": 500.0,
            "turbidez": 40.0,
            "colector_actual": 52.0,
        },
    ),
    Profile(
        key="mineral_rico",
        label="🔺 Mineral rico",
        inputs={
            "temperatura": 29.0,
            "ph": 7.1,
            "ley_mineral": 0.97,
            "caudal": 510.0,
            "turbidez": 35.0,
            "colector_actual": 52.0,
        },
    ),
]

PROFILES_BY_KEY = {p.key: p for p in PROFILES}
