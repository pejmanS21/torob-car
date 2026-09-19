#!/usr/bin/env bash
# Start (or stop with `down`) the throwaway Postgres used by `uv run pytest`.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-up}" == "down" ]]; then
  docker compose -f .docker/compose.test.yml down -v
else
  docker compose -f .docker/compose.test.yml up -d --wait
fi
