import threading
from src.core.spatial_index import GridSpatialIndex
from src.core.aircraft_state import AircraftState


def make_state(icao: str, lat: float, lon: float) -> AircraftState:
    return AircraftState(icao, "", lat, lon, 9000.0, 250.0, 0.0, 0.0)


def test_upsert_and_query():
    idx = GridSpatialIndex()
    idx.upsert(make_state("AAA", 13.5, 77.5))
    result = idx.query_bbox(13.0, 14.0, 77.0, 78.0)
    assert "AAA" in result


def test_query_excludes_out_of_bbox():
    idx = GridSpatialIndex()
    idx.upsert(make_state("IN", 13.5, 77.5))
    idx.upsert(make_state("OUT", 40.0, 40.0))
    result = idx.query_bbox(13.0, 14.0, 77.0, 78.0)
    assert "IN" in result
    assert "OUT" not in result


def test_remove():
    idx = GridSpatialIndex()
    idx.upsert(make_state("DEL", 10.0, 10.0))
    idx.remove("DEL", 10.0, 10.0)
    result = idx.query_bbox(10.0, 11.0, 10.0, 11.0)
    assert "DEL" not in result


def test_concurrent_upserts():
    idx = GridSpatialIndex()
    errors = []

    def inserter(prefix: str):
        for i in range(50):
            try:
                idx.upsert(make_state(f"{prefix}{i}", 13.0 + i * 0.01, 77.0 + i * 0.01))
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=inserter, args=(f"T{t}",)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
