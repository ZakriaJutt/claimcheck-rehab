"""UT-14 settings; worker starts without a web framework (T-2.1.5, R-07); import boundaries (T-2.1.1,
R-04); logs withhold row values (R-12); the contract has exactly 16 fields (MH-01 b)."""

from __future__ import annotations

import ast
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from claimcheck_core.intake.contract import ALLOWED_FIELDS, CLAIM_KEYS, VISIT_KEYS
from claimcheck_core.logging import JsonFormatter
from tests.conftest import ROOT

BASE_ENV = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT)}


def _run(code: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", code], env={**BASE_ENV, **env}, capture_output=True, text=True,
                          timeout=60)


def test_ut14_missing_setting_exits_naming_the_variable() -> None:
    r = _run("from claimcheck_core.settings import load_settings; load_settings()",
             {"APP_ENV": "test", "PUBLIC_BASE_URL": "http://localhost:3107"})
    assert r.returncode == 2
    assert "DATABASE_URL" in r.stderr
    r = _run("from claimcheck_core.settings import load_settings; load_settings()",
             {"APP_ENV": "test", "DATABASE_URL": "mysql://secret-value@x/y", "PUBLIC_BASE_URL": "x"})
    assert r.returncode == 2 and "DATABASE_URL" in r.stderr and "PUBLIC_BASE_URL" in r.stderr
    assert "secret-value" not in r.stderr


def test_worker_imports_with_web_framework_blocked() -> None:
    code = (
        "import sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in ('fastapi', 'starlette', 'uvicorn', 'claimcheck_api'):\n"
        "            raise ImportError('blocked ' + name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "import claimcheck_worker.main as m\n"
        "assert callable(m.main)\n"
        "print('ok')\n"
    )
    r = _run(code, {"APP_ENV": "test", "DATABASE_URL": "postgresql://x@localhost/none",
                    "PUBLIC_BASE_URL": "http://localhost:3107"})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "ok"


def _imports(pkg_dir: Path) -> set[str]:
    names: set[str] = set()
    for f in pkg_dir.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
    return names


def test_import_boundaries() -> None:
    api = _imports(ROOT / "apps/api/claimcheck_api")
    worker = _imports(ROOT / "apps/worker/claimcheck_worker")
    core = _imports(ROOT / "packages/core/claimcheck_core")
    assert not any(n.startswith("claimcheck_worker") for n in api)
    assert not any(n.startswith(("claimcheck_api", "fastapi", "starlette", "uvicorn")) for n in worker)
    assert not any(n.startswith(("claimcheck_api", "claimcheck_worker", "fastapi", "starlette")) for n in core)
    for n in api | worker:  # only the public interface of core: no module or name with a leading underscore
        if n.startswith("claimcheck_core"):
            assert not any(part.startswith("_") for part in n.split(".")), n


def test_logs_withhold_row_values() -> None:
    rec = logging.LogRecord("claimcheck.x", logging.INFO, __file__, 1, "evt", None, None)
    rec.fields = {"invoice_ref": "HV-000001", "amount": "97.00", "rows": 3}
    out = json.loads(JsonFormatter().format(rec))
    assert out["invoice_ref"] == "[withheld]" and out["amount"] == "[withheld]" and out["rows"] == 3


def test_contract_is_exactly_the_16_fields_plus_two_ordinals() -> None:
    assert len(ALLOWED_FIELDS) == 16
    assert (VISIT_KEYS | CLAIM_KEYS) == ALLOWED_FIELDS | {"row_no", "line_no"}
