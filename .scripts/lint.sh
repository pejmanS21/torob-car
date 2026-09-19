#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && uv run ruff check . --fix && uv run black .)
(cd frontend && bun run lint)
