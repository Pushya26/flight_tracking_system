import threading
import queue
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, Query

from src.core.state_store import AircraftStateStore
from src.core.spatial_index import GridSpatialIndex
from src.ingestion.simulator_source import SimulatorSource
from src.workers.state_updater import StateUpdaterWorker
from src.workers.cleaner import StaleAircraftCleaner
from src.workers.alert_worker import AlertWorker
from src.storage.repository import init_db
from src.config import settings
from .ws_broadcaster import WebSocketBroadcaster
from .routers import flights, alerts

store       = AircraftStateStore()
spatial     = GridSpatialIndex()
broadcaster = WebSocketBroadcaster(store)

data_queue = queue.Queue(maxsize=10_000)
_simulator = SimulatorSource(data_queue, num_flights=200, speed_factor=60.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    updater      = StateUpdaterWorker(data_queue, store, spatial)
    cleaner      = StaleAircraftCleaner(store, settings.stale_threshold_seconds)
    alert_worker = AlertWorker(store)

    threading.Thread(target=_simulator.run, daemon=True).start()
    updater.start()
    cleaner.start()
    alert_worker.start()
    broadcaster.start()

    app.state.store       = store
    app.state.spatial     = spatial
    app.state.alert_worker = alert_worker

    yield

    _simulator.stop()
    updater.stop()
    cleaner.stop()
    alert_worker.stop()
    broadcaster.stop()


app = FastAPI(title="Flight Tracker", lifespan=lifespan)
app.include_router(flights.router, prefix="/flights")
app.include_router(alerts.router, prefix="/alerts")


@app.websocket("/ws/flights")
async def websocket_endpoint(ws: WebSocket):
    await broadcaster.handle(ws)


@app.get("/airports")
def get_airports():
    from src.ingestion.airports import AIRPORTS
    return {icao: {"lat": lat, "lon": lon} for icao, _, lat, lon in AIRPORTS}


@app.get("/simulator/status")
def sim_status():
    return {
        "active_flights": len(_simulator._flights),
        "speed_factor":   _simulator.speed_factor,
    }


@app.post("/simulator/speed")
def sim_speed(factor: float = Query(..., ge=1, le=3600)):
    _simulator.speed_factor = factor
    with _simulator._lock:
        for f in _simulator._flights.values():
            f.speed_factor = factor
    return {"speed_factor": factor}
