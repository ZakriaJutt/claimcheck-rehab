"""The migration head this code expects; readiness compares it with the database (TRD /readyz)."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def head_revision() -> str:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    if len(heads) != 1:
        raise RuntimeError("migration history must have exactly one head")
    return heads[0]
