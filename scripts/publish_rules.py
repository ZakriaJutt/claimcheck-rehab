"""Publish export profile v1 and the rule catalogue (operator step; T-4.1.5 partial, T-1.1.2).

The Makefile runs the rule fixtures first and passes --fixtures-passed only if they passed.
Usage: MIGRATION_DATABASE_URL=... python scripts/publish_rules.py --fixtures-passed
"""

from __future__ import annotations

import argparse
import os

from sqlalchemy import create_engine

from claimcheck_core.seed import publish_profiles, publish_rules


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-passed", action="store_true")
    args = parser.parse_args()
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        raise SystemExit("configuration error: missing or invalid setting(s): MIGRATION_DATABASE_URL")
    engine = create_engine(url)
    with engine.begin() as conn:
        publish_profiles(conn)
        n = publish_rules(conn, fixtures_passed=args.fixtures_passed)
    print(f"published rule versions: {n} new")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
