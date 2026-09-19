#!/usr/bin/env bash
# Load a Divar CSV. Runs INSIDE the backend container: db and redis publish no host port.
set -euo pipefail
csv="${1:?usage: .scripts/ingest.sh <csv-path>}"
csv_dir="$(cd "$(dirname "$csv")" && pwd)"
cd "$(dirname "$0")/.."
docker compose -f .docker/compose.yml run --rm --no-deps \
  -v "$csv_dir:/data:ro" backend python -m ingest "/data/$(basename "$csv")"
