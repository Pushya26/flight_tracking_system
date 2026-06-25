from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.core.aircraft_state import AircraftState
from src.config import settings
from .models import Base, FlightEvent

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def save_flight_event(state: AircraftState) -> None:
    """Persist a single AircraftState snapshot to the DB."""
    async with AsyncSessionLocal() as session:
        event = FlightEvent(
            icao24=state.icao24,
            callsign=state.callsign,
            latitude=state.latitude,
            longitude=state.longitude,
            altitude_m=state.altitude_m,
            velocity_ms=state.velocity_ms,
            heading=state.heading,
            vertical_rate=state.vertical_rate,
            on_ground=state.on_ground,
            last_seen=state.last_seen,
        )
        session.add(event)
        await session.commit()
