# Flight Tracking System

A multi-threaded, large-scale, real-time flight tracking system with a 3D globe frontend. Built around concurrent ingestion, thread-safe data structures, spatial algorithms, a producer-consumer pipeline, and a CesiumJS visualisation layer.

## Architecture

```
SimulatorSource (Thread)         ← synthetic great-circle flights, no API key needed
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
  GET  /airports              ICAO → lat/lon lookup (used by frontend)
  GET  /simulator/status      active flight count + speed factor
  POST /simulator/speed       adjust simulation speed at runtime
  WS   /ws/flights            streams full state snapshot every 2s

React + Vite (frontend)
  └── CesiumJS Globe
       ├── OSM base map           (free, no key)
       ├── ArcGIS satellite       (free, no key — or with Ion token)
       ├── Cesium World Terrain   (free Ion token)
       ├── OSM 3-D Buildings      (free Ion token)
       └── FlightLayer
            ├── CallbackProperty  → live aircraft icons, update every 2s
            ├── Route arc         → great-circle path split at progress point
            └── Selection         → yellow highlight + origin/dest markers
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

### Backend

```bash
# Start Redis and PostgreSQL first
docker-compose -f docker/docker-compose.yml up redis db

# Then start the API
uvicorn src.api.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`

> Before running, paste your free Cesium Ion token into `frontend/index.html`:
> ```html
> <meta name="cesium-token" content="YOUR_TOKEN_HERE" />
> ```
> Get a free token at [cesium.com/ion](https://cesium.com/ion) → Access Tokens.
> The globe works without a token (falls back to OSM tiles), but terrain and satellite imagery require one.

## Run everything in Docker

```bash
docker-compose -f docker/docker-compose.yml up --build
```

| Service | Port |
|---------|------|
| FastAPI backend | 8002 |
| Frontend (nginx) | 3000 |
| Redis | 6379 |
| PostgreSQL | 5433 |

## Run tests

```bash
pytest tests/ -v
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OPENSKY_URL` | OpenSky API URL | Data source endpoint (unused with simulator) |
| `POLL_INTERVAL_SECONDS` | `10` | How often each source thread polls |
| `STALE_THRESHOLD_SECONDS` | `60` | Evict aircraft not seen for this long |
| `NUM_INGESTION_THREADS` | `3` | Number of concurrent source threads |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |

## Simulator speed control

The simulator runs at `speed_factor = 60` by default (1 real second = 1 simulated minute).

```bash
# Check status
curl http://localhost:8000/simulator/status

# Change speed at runtime (1–3600)
curl -X POST "http://localhost:8000/simulator/speed?factor=600"
```

| `speed_factor` | Effect |
|---|---|
| `1` | Real time — flights take 8–12 hours |
| `60` | Default — flights finish in ~10 minutes |
| `600` | Demo mode — flights finish in ~1 minute |

## Frontend controls

| Action | How |
|--------|-----|
| Rotate globe | Left-drag |
| Zoom | Scroll wheel |
| Tilt | Middle-drag or Ctrl + left-drag |
| Select aircraft | Click icon on globe, or click row in search list |
| Fly to aircraft | Select from list → camera animates there |
| Show route arc | Automatic on selection — flown portion dimmed, remaining portion glowing |
| Lock camera + trail | Click "Lock Camera & Show Trail" in info panel |
| Release lock | Click button again or ✕ |
| Filter by altitude | ⚙ icon in search panel |
| Recentre globe | ⊕ button (bottom-left) — flies back to full globe overview |

## Known issues & challenges

See [ISSUES.md](./ISSUES.md) for a detailed log of every significant problem encountered during development, including root cause analysis and the fix applied for each.

## Project structure

```
flight_tracking_system/
├── src/
│   ├── api/
│   │   ├── main.py               ← FastAPI app, SimulatorSource wiring, control endpoints
│   │   ├── ws_broadcaster.py     ← WebSocket broadcast loop
│   │   └── routers/
│   │       ├── flights.py
│   │       └── alerts.py
│   ├── core/
│   │   ├── aircraft_state.py     ← AircraftState dataclass (incl. origin/dest/progress)
│   │   ├── state_store.py
│   │   ├── spatial_index.py
│   │   └── ring_buffer.py
│   ├── ingestion/
│   │   ├── airports.py           ← 50 major airports for simulator routes
│   │   ├── simulator_source.py   ← synthetic flight generator
│   │   └── opensky_source.py     ← original real-data source (kept for reference)
│   ├── workers/
│   │   ├── state_updater.py      ← consumes queue, converts dicts → AircraftState
│   │   ├── alert_worker.py
│   │   └── cleaner.py
│   └── storage/
│       ├── models.py
│       └── repository.py
├── frontend/
│   ├── index.html                ← Cesium Ion token goes here (gitignored)
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── App.jsx
│       ├── globe/
│       │   ├── CesiumGlobe.jsx   ← viewer setup, imagery/terrain, fallback
│       │   └── FlightLayer.js    ← entity management, route arcs, selection
│       ├── hooks/
│       │   └── useFlightWebSocket.js
│       └── components/
│           ├── SearchPanel.jsx
│           └── FlightInfoPanel.jsx
├── docker/
│   ├── docker-compose.yml
│   └── Dockerfile
├── tests/
├── ISSUES.md                     ← development challenges log
└── README.md
```
