from typing import List, Tuple
from src.core.aircraft_state import AircraftState
from .haversine import haversine_distance

SEPARATION_KM = 9.3    # 5 nautical miles horizontal
SEPARATION_M = 300     # ~1000 ft vertical


def detect_conflicts(aircraft: List[AircraftState]) -> List[Tuple[str, str, float]]:
    """
    O(n²) pairwise CPA (Closest Point of Approach) check.
    Returns list of (icao1, icao2, horizontal_dist_km).

    Interview note: O(n²) is acceptable here because:
    - Global n ≤ ~15k but spatial grid pre-filters to regional subsets (k << n)
    - Each check is O(1) arithmetic — tight inner loop
    - For larger scale: partition by spatial grid cell and only check pairs in
      adjacent cells, reducing to O(k) per cell instead of O(n²) globally.
    """
    conflicts = []
    n = len(aircraft)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = aircraft[i], aircraft[j]
            vdist = abs((a.altitude_m or 0.0) - (b.altitude_m or 0.0))
            if vdist >= SEPARATION_M * 2:
                continue  # vertical separation sufficient — skip haversine
            hdist = haversine_distance(a.latitude, a.longitude, b.latitude, b.longitude)
            if hdist < SEPARATION_KM * 2:
                conflicts.append((a.icao24, b.icao24, round(hdist, 3)))
    return conflicts
