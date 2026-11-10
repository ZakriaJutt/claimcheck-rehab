"""Migration checks (T-2.1.3 local part, T-2.2.1; R-05, R-08, R-10, R-11). Changes nothing.

1. Exactly one Alembic head.
2. ORM parity: the database at head compared with SQLAlchemy metadata (tables, columns, types,
   indexes, unique constraints, foreign keys).
3. Every table with clinic_id has row-level security forced and at least one policy.
4. No invalid index is left behind.

Usage: MIGRATION_DATABASE_URL=... python scripts/check_migrations.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from claimcheck_core.models import Base

MIGRATIONS = Path(os.environ.get("CLAIMCHECK_MIGRATIONS_DIR")
                  or Path(__file__).resolve().parents[1] / "packages/core/migrations")




def main() -> int:
    problems: list[str] = []
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    if len(heads) != 1:
        problems.append(f"expected one migration head, found {len(heads)}")
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        print("MIGRATION_DATABASE_URL is required", file=sys.stderr)
        return 2
    engine = create_engine(url)
    with engine.connect() as conn:
        current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if heads and current != heads[0]:
            problems.append("database is not at head")
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        for diff in compare_metadata(ctx, Base.metadata):
            problems.append(f"ORM parity: {diff}")
        missing = conn.execute(text(
            "SELECT c.table_name FROM information_schema.columns c "
            "JOIN pg_class k ON k.relname = c.table_name "
            "WHERE c.table_schema='public' AND c.column_name='clinic_id' "
            "AND (NOT k.relrowsecurity OR NOT k.relforcerowsecurity OR NOT EXISTS "
            "(SELECT 1 FROM pg_policies p WHERE p.tablename = c.table_name))")).scalars().all()
        problems += [f"table without forced RLS policy: {t}" for t in missing]
        invalid = conn.execute(text(
            "SELECT i.relname FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid WHERE NOT x.indisvalid"
        )).scalars().all()
        problems += [f"invalid index: {i}" for i in invalid]
        if not conn.execute(text("SELECT 1 FROM pg_constraint WHERE conname='rule_version_no_overlap'")).scalar():
            problems.append("missing exclusion constraint rule_version_no_overlap")
    for p in problems:
        print(p)
    print("migration checks: " + ("FAIL" if problems else "pass"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
