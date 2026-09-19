# ponytail: `bun run build` segfaults Bun's node-compat shim under Next 16 + Turbopack
# in this container (confirmed: crashes right after static-page generation finishes,
# every run, on linux/arm64). Bun still installs deps fine, so keep it for that; run
# the actual `next build` — and serve — with real Node (CLAUDE.md §11.2 fallback).
# Upgrade path: retry `bun run build` when a Bun release fixes the crash.
FROM oven/bun:1 AS deps
WORKDIR /app
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
RUN node node_modules/.bin/next build

FROM node:22-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
