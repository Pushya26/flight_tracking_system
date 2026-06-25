from src.core.aircraft_state import AircraftState
from src.algorithms.conflict_detector import detect_conflicts, SEPARATION_KM, SEPARATION_M


def make_state(icao: str, lat: float, lon: float, alt: float = 9000.0) -> AircraftState:
    return AircraftState(icao, "", lat, lon, alt, 250.0, 90.0, 0.0)


def test_no_conflicts_when_far_apart():
    aircraft = [
        make_state("A1", 13.0, 77.0),
        make_state("A2", 40.0, 40.0),
    ]
    assert detect_conflicts(aircraft) == []


def test_conflict_detected_when_close():
    # Place two aircraft ~1 km apart at same altitude
    aircraft = [
        make_state("B1", 13.0000, 77.0000),
        make_state("B2", 13.0050, 77.0050),  # ~0.7 km away
    ]
    conflicts = detect_conflicts(aircraft)
    assert len(conflicts) == 1
    assert set(conflicts[0][:2]) == {"B1", "B2"}


def test_no_conflict_when_vertically_separated():
    # Same horizontal position but >2x vertical separation
    aircraft = [
        make_state("C1", 13.0, 77.0, alt=1000.0),
        make_state("C2", 13.0, 77.0, alt=1000.0 + SEPARATION_M * 3),
    ]
    assert detect_conflicts(aircraft) == []


def test_empty_list():
    assert detect_conflicts([]) == []


def test_single_aircraft():
    assert detect_conflicts([make_state("X1", 0.0, 0.0)]) == []
