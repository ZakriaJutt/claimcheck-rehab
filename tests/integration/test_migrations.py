"""IT-13 (partial): parity check passes; a missing index is detected; a second head fails the check.
Not covered in B1: interrupted backfill resume and a failed concurrent index (no backfill exists yet)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, text

from claimcheck_core.models import Base
from tests.conftest import ROOT

SCRIPT = ROOT / "scripts/check_migrations.py"


def _check(env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **env_extra}
    return subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=120)


def test_it13_parity_check_passes(owner_engine: Engine) -> None:
    r = _check({})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "migration checks: pass" in r.stdout


def test_it13_missing_index_is_detected(owner_engine: Engine) -> None:
    with owner_engine.connect() as conn:
        trans = conn.begin()
        conn.execute(text("DROP INDEX ix_visit_claim"))
        diffs = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
        trans.rollback()
    assert any("ix_visit_claim" in str(d) for d in diffs)


def test_it13_second_head_fails_the_check(owner_engine: Engine, tmp_path: Path) -> None:
    mig = tmp_path / "migrations"
    shutil.copytree(ROOT / "packages/core/migrations", mig, ignore=shutil.ignore_patterns("__pycache__"))
    (mig / "versions" / "202611111000_branch.py").write_text(
        'revision = "202611111000"\ndown_revision = None\nbranch_labels = None\ndepends_on = None\n'
        "def upgrade():\n    pass\n\ndef downgrade():\n    pass\n")
    r = _check({"CLAIMCHECK_MIGRATIONS_DIR": str(mig)})
    assert r.returncode == 1
    assert "expected one migration head, found 2" in r.stdout
