"""Alembic environment. Runs as the schema owner (MIGRATION_DATABASE_URL), with lock and statement
timeouts (schema.md section 11)."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, text

from claimcheck_core.models import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        raise SystemExit("configuration error: missing or invalid setting(s): MIGRATION_DATABASE_URL")
    engine = create_engine(url)
    with engine.connect() as connection:
        connection.execute(text("SET lock_timeout = '5s'"))
        connection.execute(text("SET statement_timeout = '60s'"))
        context.configure(connection=connection, target_metadata=target_metadata, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


run_migrations_online()
