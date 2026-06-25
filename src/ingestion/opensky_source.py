import time
import requests
from .base_source import BaseDataSource
from src.core.aircraft_state import AircraftState


class OpenSkySource(BaseDataSource):
    URL = "https://opensky-network.org/api/states/all"

    def fetch(self) -> list:
        response = requests.get(self.URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        states = []
        for s in (data.get("states") or []):
            # s[5]=lat, s[6]=lon — skip if missing (aircraft on ground w/o GPS)
            if s[5] is None or s[6] is None:
                continue
            states.append(AircraftState(
                icao24=s[0],
                callsign=(s[1] or "").strip(),
                latitude=s[5],
                longitude=s[6],
                altitude_m=s[7] or 0.0,
                velocity_ms=s[9] or 0.0,
                heading=s[10] or 0.0,
                vertical_rate=s[11] or 0.0,
                on_ground=s[8] or False,
                last_seen=s[3] or time.time(),
            ))
        return states
