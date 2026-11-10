"""Test configuration. Integration tests use the real PostgreSQL test database `claimcheck_test`.

The application code always connects as `claimcheck_app` (NOSUPERUSER, NOBYPASSRLS). The schema owner
connection is used only for test setup (resetting the schema, creating synthetic clinics and sessions),
never by code under test.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_env_file() -> dict[str, str]:
    env: dict[str, str] = {}
    path = ROOT / ".env.local"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


_file_env = _load_env_file()
for key in ("TEST_DATABASE_URL", "TEST_MIGRATION_DATABASE_URL"):
    if key not in os.environ and key in _file_env:
        os.environ[key] = _file_env[key]
os.environ["APP_ENV"] = "test"
os.environ.setdefault("PUBLIC_BASE_URL", "http://localhost:3107")
if "TEST_DATABASE_URL" in os.environ:
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ["MIGRATION_DATABASE_URL"] = os.environ["TEST_MIGRATION_DATABASE_URL"]
