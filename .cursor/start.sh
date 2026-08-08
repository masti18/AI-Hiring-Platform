#!/usr/bin/env bash
# Per-boot service reconciliation for the AI Hiring Platform.
# Starts postgres, redis and qdrant, provisions the dev DB, applies migrations,
# then returns. Safe to run repeatedly.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

POSTGRES_USER="hiring"
POSTGRES_PASSWORD="hiring_dev_password"
POSTGRES_DB="hiring"
QDRANT_STORAGE="/var/lib/qdrant/storage"

echo "==> Starting PostgreSQL"
sudo pg_ctlcluster 16 main start 2>/dev/null || true
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then break; fi
  sleep 1
done

echo "==> Ensuring role and database"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='${POSTGRES_USER}') THEN
    CREATE ROLE ${POSTGRES_USER} LOGIN PASSWORD '${POSTGRES_PASSWORD}';
  END IF;
END \$\$;
SQL
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" | grep -q 1; then
  sudo -u postgres createdb -O "${POSTGRES_USER}" "${POSTGRES_DB}"
fi

echo "==> Starting Redis"
if ! redis-cli ping >/dev/null 2>&1; then
  sudo redis-server --daemonize yes --dir /var/lib/redis
fi

echo "==> Starting Qdrant"
if ! curl -sf -o /dev/null http://localhost:6333/readyz; then
  sudo mkdir -p "${QDRANT_STORAGE}"
  sudo chown -R "$(id -u):$(id -g)" "$(dirname "${QDRANT_STORAGE}")"
  QDRANT__STORAGE__STORAGE_PATH="${QDRANT_STORAGE}" nohup qdrant >/tmp/qdrant.log 2>&1 &
fi

echo "==> Applying database migrations"
cd "$ROOT/backend"
# shellcheck disable=SC1091
source .venv/bin/activate
set -a; . "$ROOT/.env"; set +a
alembic upgrade head
deactivate

echo "==> start.sh complete"
