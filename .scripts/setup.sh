#!/usr/bin/env bash
# Bootstrap a fresh clone.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || cp example.env .env
if grep -q '^JWT_SECRET=$' .env; then
  secret="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed -i.bak "s|^JWT_SECRET=$|JWT_SECRET=${secret}|" .env && rm -f .env.bak
fi
(cd backend && uv sync)
(cd frontend && bun install)
if command -v pre-commit >/dev/null; then pre-commit install; fi
