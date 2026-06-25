# Flight Tracking System

A multi-threaded, real-time flight tracking system built around concurrent ingestion, thread-safe data structures, spatial algorithms, and a producer-consumer pipeline.

## Architecture

```
OpenSkySource (Thread 1..N)  ← polls OpenSky REST API every 10s
       │
       │  queue.Queue (maxsize=10,000)   ← backpressure boundary
       ▼
StateUpdaterWorker (Consumer Thread)
       ├── AircraftStateStore   RLock, snapshot-on-read
       ├── GridSpatialIndex     1° grid cells, O(1) insert / O(k) bbox query
       └── PositionRingBuffer   per-aircraft, deque(maxlen=100)

StaleAircraftCleaner  (every 30s) → evicts aircraft not seen for >60s
AlertWorker           (every 15s) → O(n²) CPA conflict detection, cached

FastAPI + WebSocket
  GET  /flights/              all live aircraft
  GET  /flights/{icao24}      single aircraft
  GET  /flights/bbox/search   spatial bounding-box query
  GET  /alerts/               current conflict list
  WS   /ws                    streams full state every 2s
```

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run locally

```bash
uvicorn src.api.main:app --reload
```

> Requires Redis and PostgreSQL. Start them via Docker:
> ```bash
> docker-compose -f docker/docker-compose.yml up redis db
> ```

## Run everything in Docker

```bash
docker-compose -f docker/docker-compose.yml up --build
```

## Run tests

```bash
pytest tests/ -v
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OPENSKY_URL` | OpenSky API URL | Data source endpoint |
| `POLL_INTERVAL_SECONDS` | `10` | How often each source thread polls |
| `STALE_THRESHOLD_SECONDS` | `60` | Evict aircraft not seen for this long |
| `NUM_INGESTION_THREADS` | `3` | Number of concurrent source threads |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
