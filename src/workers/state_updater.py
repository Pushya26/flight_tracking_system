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

    @staticmethod
    def _to_aircraft_state(d: dict):
        from src.core.aircraft_state import AircraftState
        import time
        return AircraftState(
            icao24        = d["icao24"],
            callsign      = d.get("callsign"),
            latitude      = d["latitude"],
            longitude     = d["longitude"],
            altitude_m    = d.get("altitude", d.get("altitude_m", 0.0)),
            velocity_ms   = d.get("velocity", d.get("velocity_ms", 0.0)),
            heading       = d.get("true_track", d.get("heading", 0.0)),
            vertical_rate = d.get("vertical_rate", 0.0),
            on_ground     = d.get("on_ground", False),
            last_seen     = d.get("last_contact", time.time()),
            origin_icao   = d.get("origin_icao"),
            dest_icao     = d.get("dest_icao"),
            progress      = d.get("progress"),
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                payload = self._queue.get(timeout=1)
                # Accept both a dict envelope {"states": [...]} and bare AircraftState objects
                if isinstance(payload, dict):
                    items = payload.get("states") or payload.get("flights") or []
                    states = [self._to_aircraft_state(d) for d in items]
                else:
                    states = [payload]

                for state in states:
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
