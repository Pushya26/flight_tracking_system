import math
import time
from src.core.aircraft_state import AircraftState


def interpolate_position(state: AircraftState, at_time: float = None) -> tuple[float, float]:
    """
    Dead-reckoning: project lat/lon forward from last_seen using velocity + heading.
    Returns (lat, lon) estimate at at_time (defaults to now).
    """
    at_time = at_time or time.time()
    dt = at_time - state.last_seen  # seconds elapsed
    if dt <= 0 or state.velocity_ms <= 0:
        return state.latitude, state.longitude

    distance_m = state.velocity_ms * dt
    heading_rad = math.radians(state.heading)
    R = 6_371_000.0  # Earth radius in metres

    lat_rad = math.radians(state.latitude)
    lon_rad = math.radians(state.longitude)

    new_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(distance_m / R) +
        math.cos(lat_rad) * math.sin(distance_m / R) * math.cos(heading_rad)
    )
    new_lon_rad = lon_rad + math.atan2(
        math.sin(heading_rad) * math.sin(distance_m / R) * math.cos(lat_rad),
        math.cos(distance_m / R) - math.sin(lat_rad) * math.sin(new_lat_rad)
    )

    return math.degrees(new_lat_rad), math.degrees(new_lon_rad)
