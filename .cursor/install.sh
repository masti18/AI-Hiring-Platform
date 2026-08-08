#!/usr/bin/env bash
# Idempotent dependency/setup refresh for the AI Hiring Platform.
# Runs after the repo is checked out. Must terminate (no long-running servers here).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

QDRANT_VERSION="v1.13.2"

echo "==> Ensuring system packages (postgres, redis, python venv, toolchain)"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq \
  postgresql postgresql-contrib \
  redis-server \
  python3-venv python3-dev \
  curl ca-certificates

echo "==> Ensuring Qdrant binary (${QDRANT_VERSION})"
if ! command -v qdrant >/dev/null 2>&1; then
  tmp="$(mktemp -d)"
  curl -sSL -o "${tmp}/qdrant.tar.gz" \
    "https://github.com/qdrant/qdrant/releases/download/${QDRANT_VERSION}/qdrant-x86_64-unknown-linux-gnu.tar.gz"
  sudo tar xzf "${tmp}/qdrant.tar.gz" -C /usr/local/bin
  sudo chmod +x /usr/local/bin/qdrant
  rm -rf "${tmp}"
fi
qdrant --version

echo "==> Ensuring local .env"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "    created .env from .env.example"
fi

echo "==> Backend: virtualenv + dependencies"
cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
deactivate

echo "==> Frontend: node dependencies"
cd "$ROOT/frontend"
npm ci

echo "==> install.sh complete"
