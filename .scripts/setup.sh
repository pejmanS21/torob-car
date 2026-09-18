#!/usr/bin/env bash
# Bootstrap a fresh clone.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || cp example.env .env
(cd backend && uv sync)
(cd frontend && bun install)
if command -v pre-commit >/dev/null; then pre-commit install; fi
