from collections import deque
from typing import Tuple, Optional
import threading


class PositionRingBuffer:
    """Fixed-size circular buffer of (lat, lon, timestamp) tuples."""

    def __init__(self, maxlen: int = 100):
        self._buffer: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def push(self, lat: float, lon: float, ts: float) -> None:
        with self._lock:
            self._buffer.append((lat, lon, ts))

    def snapshot(self) -> list:
        with self._lock:
            return list(self._buffer)

    def latest(self) -> Optional[Tuple[float, float, float]]:
        with self._lock:
            return self._buffer[-1] if self._buffer else None
