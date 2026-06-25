import queue
from typing import List
from .base_source import BaseDataSource


class SourceManager:
    """
    Manages a pool of data source threads.
    All sources write into a single shared queue (producer side).
    """

    def __init__(self, sources: List[BaseDataSource]):
        self.output_queue: queue.Queue = queue.Queue(maxsize=10_000)
        self._sources = sources
        for src in self._sources:
            src._queue = self.output_queue  # point all sources at the same queue

    def start_all(self) -> None:
        for src in self._sources:
            src.start()
        print(f"[SourceManager] Started {len(self._sources)} source thread(s).")

    def stop_all(self) -> None:
        for src in self._sources:
            src.stop()
