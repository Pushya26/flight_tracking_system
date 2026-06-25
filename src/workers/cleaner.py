import threading
import time
from src.core.state_store import AircraftStateStore


class StaleAircraftCleaner:
    """Background thread: evicts aircraft not updated within threshold_seconds."""

    def __init__(self, store: AircraftStateStore, threshold_seconds: int = 60):
        self._store = store
        self._threshold = threshold_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()

    def _run(self) -> None:
        while not self._stop.wait(timeout=30):
            now = time.time()
            stale = [
                icao for icao, s in self._store.get_all().items()
                if now - s.last_seen > self._threshold
            ]
            for icao in stale:
                self._store.remove(icao)
            if stale:
                print(f"[Cleaner] Evicted {len(stale)} stale aircraft.")
