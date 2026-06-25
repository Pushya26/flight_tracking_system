import threading
import time
from typing import List, Tuple
from src.core.state_store import AircraftStateStore
from src.algorithms.conflict_detector import detect_conflicts


class AlertWorker:
    """Background thread: runs conflict detection every cycle and stores results."""

    def __init__(self, store: AircraftStateStore, interval_seconds: int = 15):
        self._store = store
        self._interval = interval_seconds
        self._alerts: List[Tuple[str, str, float]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def get_alerts(self) -> List[Tuple[str, str, float]]:
        with self._lock:
            return list(self._alerts)

    def _run(self) -> None:
        while not self._stop.wait(timeout=self._interval):
            aircraft = list(self._store.get_all().values())
            conflicts = detect_conflicts(aircraft)
            with self._lock:
                self._alerts = conflicts
            if conflicts:
                print(f"[AlertWorker] {len(conflicts)} conflict(s) detected.")
