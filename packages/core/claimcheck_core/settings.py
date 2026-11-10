"""One typed settings object, read from the environment and validated at start (R-06, UT-14)."""

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore", case_sensitive=False)

    app_env: Literal["local", "test", "staging", "production"]
    database_url: str = Field(min_length=1)
    public_base_url: str = Field(min_length=1)
    api_port: int = 8107
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    timezone: str = "America/Vancouver"
    session_cookie_name: str = "cc_session"
    session_idle_minutes: int = 30
    job_lease_seconds: int = 120

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("must be a postgresql URL")
        return v

    @field_validator("public_base_url")
    @classmethod
    def _http_url(cls, v: str) -> str:
        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("must be an absolute http(s) URL")
        return v.rstrip("/")


class SettingsError(SystemExit):
    """Raised at start when a setting is missing or malformed; names the variable, never its value."""


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        names = sorted({str(err["loc"][0]).upper() for err in exc.errors() if err.get("loc")})
        msg = "configuration error: missing or invalid setting(s): " + ", ".join(names)
        print(msg, file=sys.stderr)
        raise SettingsError(2) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
