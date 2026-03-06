# ─────────────────────────────────────────────────────────────────
# config.py – Centralised application settings via pydantic-settings
# All values are loaded from environment variables / .env file.
# ─────────────────────────────────────────────────────────────────

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """
    Application-wide settings.
    Reads from environment variables or a .env file at the project root.
    """

    # ── Database ──────────────────────────────────────────────────
    DATABASE_URL: str  # e.g. postgresql+asyncpg://user:pass@host/db

    # ── Groq / LLM ────────────────────────────────────────────────
    GROQ_API_KEY: str
    LLM_MODEL: str = "llama-3.1-8b-instant"

    # ── App ───────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # ── CORS ──────────────────────────────────────────────────────
    # Stored as a comma-separated string in .env; parsed into a list.
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS_ORIGINS as a Python list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # ── Security ──────────────────────────────────────────────────
    SECRET_KEY: str = "change_this_to_a_random_secret_key"

    # Tell pydantic-settings to read from .env in the backend root
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Return a cached Settings instance.
    Using @lru_cache ensures the .env file is read only once per process.
    """
    return Settings()


# Convenience singleton used across the codebase
settings = get_settings()
