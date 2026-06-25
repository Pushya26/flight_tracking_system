import threading
from collections import defaultdict
from typing import Set, Tuple
from .aircraft_state import AircraftState


class GridSpatialIndex:
    """
    Divides the world into GRID_SIZE-degree cells.
    Aircraft are bucketed by cell. Bounding-box queries check only relevant cells.
    O(1) insert/update, O(k) bbox query where k = aircraft in overlapping cells.
    """

    GRID_SIZE = 1.0  # degrees

    def __init__(self):
        self._grid: dict = defaultdict(set)  # cell_key -> set of icao24
        self._lock = threading.Lock()

    def _cell_key(self, lat: float, lon: float) -> Tuple[int, int]:
        return (int(lat // self.GRID_SIZE), int(lon // self.GRID_SIZE))

    def upsert(self, state: AircraftState) -> None:
        key = self._cell_key(state.latitude, state.longitude)
        with self._lock:
            self._grid[key].add(state.icao24)

    def remove(self, icao24: str, lat: float, lon: float) -> None:
        key = self._cell_key(lat, lon)
        with self._lock:
            self._grid[key].discard(icao24)

    def query_bbox(self, lat_min: float, lat_max: float,
                   lon_min: float, lon_max: float) -> Set[str]:
        """Return all icao24 codes whose cell overlaps the bounding box."""
        results: Set[str] = set()
        row_min = int(lat_min // self.GRID_SIZE)
        row_max = int(lat_max // self.GRID_SIZE)
        col_min = int(lon_min // self.GRID_SIZE)
        col_max = int(lon_max // self.GRID_SIZE)
        with self._lock:
            for r in range(row_min, row_max + 1):
                for c in range(col_min, col_max + 1):
                    results |= self._grid.get((r, c), set())
        return results
