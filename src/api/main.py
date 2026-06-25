from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from src.core.state_store import AircraftStateStore
from src.core.spatial_index import GridSpatialIndex
from src.ingestion.opensky_source import OpenSkySource
from src.ingestion.source_manager import SourceManager
from src.workers.state_updater import StateUpdaterWorker
from src.workers.cleaner import StaleAircraftCleaner
from src.workers.alert_worker import AlertWorker
from src.storage.repository import init_db
from src.config import settings
from .ws_broadcaster import WebSocketBroadcaster
from .routers import flights, alerts

store = AircraftStateStore()
spatial = GridSpatialIndex()
broadcaster = WebSocketBroadcaster(store)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    sources = [
        OpenSkySource(None, settings.poll_interval_seconds)
        for _ in range(settings.num_ingestion_threads)
    ]
    manager = SourceManager(sources)
    updater = StateUpdaterWorker(manager.output_queue, store, spatial)
    cleaner = StaleAircraftCleaner(store, settings.stale_threshold_seconds)
    alert_worker = AlertWorker(store)

    manager.start_all()
    updater.start()
    cleaner.start()
    alert_worker.start()
    broadcaster.start()

    app.state.store = store
    app.state.spatial = spatial
    app.state.alert_worker = alert_worker

    yield

    manager.stop_all()
    updater.stop()
    cleaner.stop()
    alert_worker.stop()
    broadcaster.stop()


app = FastAPI(title="Flight Tracker", lifespan=lifespan)
app.include_router(flights.router, prefix="/flights")
app.include_router(alerts.router, prefix="/alerts")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await broadcaster.handle(ws)
