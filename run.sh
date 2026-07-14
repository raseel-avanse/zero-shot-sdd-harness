#!/usr/bin/env bash
# Start Sentinel the safe way: always rebuild the frontend before serving so a
# stale frontend/out/ (e.g. a build left behind by another branch) can never be
# served. Run from the repo root: ./run.sh
#
# Honors PORT (default 8003). Postgres is expected in the Docker container
# sec-agent-pg on :5433 (see README / .env).
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8003}"

# Resolve a Docker CLI (WSL: docker.exe; native: docker).
DOCKER="$(command -v docker || command -v docker.exe || true)"

echo "==> Ensuring Postgres (sec-agent-pg) is running"
if [ -n "$DOCKER" ]; then
  "$DOCKER" start sec-agent-pg >/dev/null 2>&1 || \
    echo "    (could not start sec-agent-pg via $DOCKER — start it yourself if the app can't connect)"
else
  echo "    (no docker CLI found — ensure Postgres is reachable on :5433)"
fi

echo "==> Applying database migrations"
uv run alembic upgrade head

echo "==> Rebuilding the frontend (prevents serving a stale build)"
( cd frontend && pnpm install --frozen-lockfile && pnpm build )

echo "==> Starting Sentinel on http://localhost:${PORT}/app/"
PORT="$PORT" exec uv run python -m src
