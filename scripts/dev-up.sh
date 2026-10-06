#!/usr/bin/env bash
# Start local infra (postgres, redis, qdrant).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi
docker compose up -d postgres redis qdrant
docker compose ps
