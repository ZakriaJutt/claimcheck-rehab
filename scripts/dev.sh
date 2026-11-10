#!/usr/bin/env bash
# Local start (T-2.1.2; R-17): migrate, publish rules, start API (8107) and worker, check health.
# Stops and names the first unhealthy service. The TRD's Compose setup stays proposed: Docker is not
# installed on this machine, so services run directly against the local PostgreSQL.
set -euo pipefail
cd "$(dirname "$0")/.."
VENV=dev/.venv/bin
RUN=.run
mkdir -p "$RUN"
set -a; . ./.env.local; set +a
export APP_ENV PUBLIC_BASE_URL DATABASE_URL MIGRATION_DATABASE_URL

pg_isready -h localhost -p 5432 -q || { echo "unhealthy: postgresql (localhost:5432)"; exit 1; }
(cd packages/core && ../../$VENV/alembic upgrade head) >/dev/null || { echo "unhealthy: migrations"; exit 1; }
$VENV/pytest -q -p no:cacheprovider tests/unit/test_rules.py >/dev/null \
  && $VENV/python scripts/publish_rules.py --fixtures-passed \
  || { echo "unhealthy: rule fixtures failed, nothing published"; exit 1; }

"$0"-stop 2>/dev/null || true
nohup $VENV/uvicorn --factory claimcheck_api.main:create_app --host 127.0.0.1 --port "${API_PORT:-8107}" \
  > "$RUN/api.log" 2>&1 & echo $! > "$RUN/api.pid"
nohup $VENV/python -m claimcheck_worker.main > "$RUN/worker.log" 2>&1 & echo $! > "$RUN/worker.pid"

for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:${API_PORT:-8107}/readyz" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -fsS "http://127.0.0.1:${API_PORT:-8107}/healthz" >/dev/null || { echo "unhealthy: api /healthz"; exit 1; }
curl -fsS "http://127.0.0.1:${API_PORT:-8107}/readyz" >/dev/null || { echo "unhealthy: api /readyz"; exit 1; }
sleep 2
[ -f "$RUN/worker-heartbeat" ] && kill -0 "$(cat "$RUN/worker.pid")" 2>/dev/null \
  || { echo "unhealthy: worker (no heartbeat)"; exit 1; }
echo "healthy: postgresql, migrations at head, rules published, api :${API_PORT:-8107}, worker heartbeat"
echo "frontend :3107 not started (no UI in B1); Redis db 6 unused (AD-05: jobs in PostgreSQL)"
