import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Event Booking System API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = ""

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://event_admin:event_secure_pass_2026@localhost:5433/event_booking_db"

    # Security
    JWT_SECRET: str = "super_secret_jwt_key_for_event_booking_system_2026_cactro_secure"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Email
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "onboarding@resend.dev"

    # Concurrency mode: "naive" (for baseline demonstration) or "optimized" (production default)
    CONCURRENCY_MODE: str = "naive"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
