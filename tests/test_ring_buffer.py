import threading
from src.core.ring_buffer import PositionRingBuffer


def test_push_and_snapshot():
    buf = PositionRingBuffer(maxlen=5)
    for i in range(5):
        buf.push(float(i), float(i), float(i))
    assert len(buf.snapshot()) == 5


def test_maxlen_eviction():
    buf = PositionRingBuffer(maxlen=3)
    for i in range(6):
        buf.push(float(i), float(i), float(i))
    snap = buf.snapshot()
    assert len(snap) == 3
    assert snap[0] == (3.0, 3.0, 3.0)  # oldest three evicted


def test_latest_empty():
    buf = PositionRingBuffer()
    assert buf.latest() is None


def test_latest_returns_last():
    buf = PositionRingBuffer()
    buf.push(1.0, 2.0, 3.0)
    buf.push(4.0, 5.0, 6.0)
    assert buf.latest() == (4.0, 5.0, 6.0)


def test_concurrent_push_no_corruption():
    buf = PositionRingBuffer(maxlen=200)
    errors = []

    def pusher(offset: int):
        for i in range(50):
            try:
                buf.push(float(offset + i), float(offset + i), float(offset + i))
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=pusher, args=(t * 100,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(buf.snapshot()) == 200  # maxlen capped
