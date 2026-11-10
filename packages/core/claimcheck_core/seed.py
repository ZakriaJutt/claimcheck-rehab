"""Operator-side publication of the rule catalogue and export profile v1 (T-4.1.5, T-1.1.2).

Runs with the schema owner's connection (the application role can only read these tables).
Publication is refused unless the caller states that the rule fixtures passed in this run.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib import resources
from typing import Any

from sqlalchemy import Connection, text

from claimcheck_core.rules.catalogue import catalogue_versions


def jane_profile() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(resources.files("claimcheck_core.profiles").joinpath("jane_v1.json").read_text())
    return data


def publish_profiles(conn: Connection) -> None:
    prof = jane_profile()
    shared = {k: prof[k] for k in ("payer_map", "state_map", "policy_status_map", "billing_codes")}
    for report in ("sales", "policies"):
        section = prof[report]
        conn.execute(text(
            "INSERT INTO export_profile (report, version, header_map, required, published_at) "
            "VALUES (:r, :v, CAST(:h AS jsonb), :req, now()) ON CONFLICT (report, version) DO NOTHING"),
            {"r": report, "v": section["version"], "h": json.dumps({"columns": section["columns"], **shared}),
             "req": section["required"]})


def publish_rules(conn: Connection, fixtures_passed: bool) -> int:
    if not fixtures_passed:
        raise SystemExit("publication refused: rule fixtures have not passed in this run")
    now = datetime.now(tz=UTC)
    n = 0
    for v in catalogue_versions():
        res = conn.execute(text(
            "INSERT INTO rule_version (id, rule_code, version, effective_from, effective_to, params, "
            "source_citation, source_id, status, fixtures_passed_at, published_at) VALUES "
            "(:id, :c, :ver, :f, :t, CAST(:p AS jsonb), :cite, :src, 'published', :now, :now) "
            "ON CONFLICT (rule_code, version) DO NOTHING"),
            {"id": v.id, "c": v.rule_code, "ver": v.version, "f": v.effective_from, "t": v.effective_to,
             "p": json.dumps(v.params), "cite": v.source_citation, "src": v.source_id, "now": now})
        n += res.rowcount
    return n
