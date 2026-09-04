"""Canonical scientific units for FloodGuard-AI internal contracts."""

from enum import StrEnum


class Unit(StrEnum):
    DISTANCE = "m"
    ELEVATION = "m"
    WATER_DEPTH = "m"
    VELOCITY = "m/s"
    DISCHARGE = "m³/s"
    AREA = "m²"
    VOLUME = "m³"
    SIMULATION_TIME = "s"
    RAIN_RATE = "mm/h"


CANONICAL_UNITS: dict[str, Unit] = {
    "distance": Unit.DISTANCE,
    "elevation": Unit.ELEVATION,
    "water_depth": Unit.WATER_DEPTH,
    "velocity": Unit.VELOCITY,
    "discharge": Unit.DISCHARGE,
    "area": Unit.AREA,
    "volume": Unit.VOLUME,
    "simulation_time": Unit.SIMULATION_TIME,
    "rain_rate": Unit.RAIN_RATE,
}
