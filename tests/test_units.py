from floodguard.contracts.units import CANONICAL_UNITS, Unit


def test_canonical_units_are_fixed() -> None:
    assert CANONICAL_UNITS == {
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
