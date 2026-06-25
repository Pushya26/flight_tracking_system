from sqlalchemy import Column, String, Float, Boolean, BigInteger
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class FlightEvent(Base):
    __tablename__ = "flight_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    icao24 = Column(String(10), nullable=False, index=True)
    callsign = Column(String(20), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude_m = Column(Float, nullable=False)
    velocity_ms = Column(Float, nullable=False)
    heading = Column(Float, nullable=False)
    vertical_rate = Column(Float, nullable=False)
    on_ground = Column(Boolean, nullable=False, default=False)
    last_seen = Column(Float, nullable=False)  # Unix timestamp
