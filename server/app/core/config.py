from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "资源智能调度平台"
    DATABASE_URL: str = "sqlite:///./cro_scheduler.db"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000"

    FROZEN_DAYS: int = 3
    CONFIRMED_DAYS: int = 14
    STATS_WINDOW_DAYS: int = 7
    HOURS_PER_DAY: int = 24
    PERCENT_SCALE: float = 100.0
    BOTTLENECK_BUFFER_RATE: float = 0.85
    NON_BOTTLENECK_BUFFER_RATE: float = 0.95
    SOLVER_TIMEOUT_SECONDS: int = 60
    DEVIATION_THRESHOLD_HOURS: int = 2
    DEVIATION_RATIO_THRESHOLD: float = 1.5

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
