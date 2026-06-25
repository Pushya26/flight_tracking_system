from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    opensky_url: str = "https://opensky-network.org/api/states/all"
    poll_interval_seconds: int = 10
    stale_threshold_seconds: int = 60
    redis_url: str = "redis://localhost:6379"
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/flights"
    num_ingestion_threads: int = 3

    class Config:
        env_file = ".env"

settings = Settings()
