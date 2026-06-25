import threading
import queue
from typing import Dict
from src.core.state_store import AircraftStateStore
from src.core.spatial_index import GridSpatialIndex
from src.core.ring_buffer import PositionRingBuffer


class StateUpdaterWorker:
    """
    Consumer: drains the shared queue and updates the state store.
    Maintains per-aircraft ring buffers for position history.
    """

    def __init__(self, input_queue: queue.Queue, store: AircraftStateStore,
                 spatial_index: GridSpatialIndex):
        self._queue = input_queue
        self._store = store
        self._spatial = spatial_index
        self._buffers: Dict[str, PositionRingBuffer] = {}
        self._buf_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                state = self._queue.get(timeout=1)
                self._store.update(state)
                self._spatial.upsert(state)
                with self._buf_lock:
                    if state.icao24 not in self._buffers:
                        self._buffers[state.icao24] = PositionRingBuffer()
                    self._buffers[state.icao24].push(
                        state.latitude, state.longitude, state.last_seen
                    )
                self._queue.task_done()
            except queue.Empty:
                continue
