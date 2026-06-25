import threading
import queue
from abc import ABC, abstractmethod


class BaseDataSource(ABC):
    """
    Each source runs in its own daemon thread.
    Produces AircraftState objects into a shared queue.
    """

    def __init__(self, output_queue: queue.Queue, poll_interval: int = 10):
        self._queue = output_queue
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.wait(timeout=self._poll_interval):
            try:
                states = self.fetch()
                for state in states:
                    self._queue.put(state, block=False)
            except Exception as e:
                print(f"[{self.__class__.__name__}] fetch error: {e}")

    @abstractmethod
    def fetch(self) -> list:
        raise NotImplementedError
