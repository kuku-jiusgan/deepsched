from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "CRO仪器排程系统"
    DATABASE_URL: str = "sqlite:///./cro_scheduler.db"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

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
