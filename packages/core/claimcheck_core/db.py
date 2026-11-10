"""Database engine. The application connects as the non-superuser role claimcheck_app (NOBYPASSRLS)."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from claimcheck_core.settings import get_settings


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, future=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return make_engine(get_settings().database_url)
