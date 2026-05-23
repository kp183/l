"""Application settings loaded from environment variables / .env file.

Uses pydantic-settings so every field can be overridden by an environment
variable with the same name (case-insensitive).  A .env file in the working
directory is also read automatically.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the AgentLens API.

    All fields can be supplied via environment variables or a .env file.
    Field names are matched case-insensitively (e.g. DATABASE_URL or database_url).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #
    # Must use the asyncpg driver: postgresql+asyncpg://user:pass@host/db
    database_url: str

    # ------------------------------------------------------------------ #
    # Redis                                                                #
    # ------------------------------------------------------------------ #
    redis_url: str = "redis://localhost:6379/0"

    # ------------------------------------------------------------------ #
    # Clerk authentication                                                 #
    # ------------------------------------------------------------------ #
    clerk_secret_key: str
    clerk_publishable_key: str
    # e.g. https://<instance>.clerk.accounts.dev/.well-known/jwks.json
    clerk_jwks_url: str

    # ------------------------------------------------------------------ #
    # Application                                                          #
    # ------------------------------------------------------------------ #
    # "development" or "production"
    environment: str = "development"
    api_version: str = "v1"

    # Explicit CORS origin allowlist.  Never use wildcard "*".
    # Supply as a comma-separated string in the environment:
    #   CORS_ORIGINS="http://localhost:3000,https://app.example.com"
    # Declared as str so pydantic-settings doesn't try to JSON-decode it.
    cors_origins: str = "http://localhost:3000"

    # ------------------------------------------------------------------ #
    # Rate limiting                                                        #
    # ------------------------------------------------------------------ #
    # Maximum ingest requests per minute per API key.
    ingest_rate_limit: int = 1000

    # ------------------------------------------------------------------ #
    # Validators                                                           #
    # ------------------------------------------------------------------ #

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> str:
        """Accept either a list or a comma-separated string and normalise to str.

        pydantic-settings v2 tries to JSON-decode list fields from env vars,
        which breaks when the value is a plain comma-separated string like
        ``http://localhost:3000,https://app.example.com``.  We store the raw
        string and expose a parsed property instead.
        """
        if isinstance(value, list):
            return ",".join(value)
        return str(value)

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS origins as a list, split on commas."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    The result is cached after the first call so that the .env file and
    environment variables are only read once per process.  Use
    ``get_settings.cache_clear()`` in tests to force re-evaluation.
    """
    return Settings()
