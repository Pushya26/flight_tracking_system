import threading
from src.core.state_store import AircraftStateStore
from src.core.aircraft_state import AircraftState


def make_state(icao: str) -> AircraftState:
    return AircraftState(icao, "TEST", 13.0, 77.0, 9000.0, 250.0, 90.0, 0.0)


def test_concurrent_writes_no_corruption():
    store = AircraftStateStore()
    errors = []

    def writer(prefix: str, n: int):
        for i in range(n):
            try:
                store.update(make_state(f"{prefix}{i:04d}"))
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=writer, args=(f"T{t}", 200)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent write errors: {errors}"
    assert store.count() <= 5 * 200


def test_concurrent_reads_while_writing():
    store = AircraftStateStore()
    for i in range(50):
        store.update(make_state(f"SEED{i:04d}"))

    read_errors = []

    def reader():
        for _ in range(100):
            try:
                snapshot = store.get_all()
                assert isinstance(snapshot, dict)
            except Exception as e:
                read_errors.append(e)

    def writer():
        for i in range(100):
            store.update(make_state(f"W{i:04d}"))

    threads = (
        [threading.Thread(target=reader) for _ in range(4)] +
        [threading.Thread(target=writer) for _ in range(2)]
    )
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not read_errors, f"Concurrent read errors: {read_errors}"


def test_remove_is_safe_under_concurrency():
    store = AircraftStateStore()
    for i in range(100):
        store.update(make_state(f"R{i:04d}"))

    def remover():
        for i in range(100):
            store.remove(f"R{i:04d}")

    threads = [threading.Thread(target=remover) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert store.count() == 0
