from dataclasses import dataclass, field
from typing import Optional
import time

@dataclass
class AircraftState:
    icao24: str
    callsign: Optional[str]
    latitude: float
    longitude: float
    altitude_m: float
    velocity_ms: float
    heading: float
    vertical_rate: float
    last_seen: float = field(default_factory=time.time)
    on_ground: bool = False
