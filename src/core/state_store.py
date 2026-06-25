import threading
from typing import Dict, Optional
from .aircraft_state import AircraftState


class AircraftStateStore:
    """
    Thread-safe store for live aircraft states.
    Uses a readers-writer lock pattern:
    - Multiple concurrent readers allowed
    - Exclusive access for writers
    """

    def __init__(self):
        self._states: Dict[str, AircraftState] = {}
        self._lock = threading.RLock()  # Reentrant for nested calls

    def update(self, state: AircraftState) -> None:
        with self._lock:
            self._states[state.icao24] = state

    def get(self, icao24: str) -> Optional[AircraftState]:
        with self._lock:
            return self._states.get(icao24)

    def get_all(self) -> Dict[str, AircraftState]:
        with self._lock:
            return dict(self._states)  # Snapshot copy — safe to read outside lock

    def remove(self, icao24: str) -> None:
        with self._lock:
            self._states.pop(icao24, None)

    def count(self) -> int:
        with self._lock:
            return len(self._states)
