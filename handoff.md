# Handoff — Torobcar

_Last updated: 2026-09-23_

## Start here

Read [CLAUDE.md](CLAUDE.md) for architecture, conventions, and commands.
The root [AGENTS.md](AGENTS.md) is a relative symlink to that file.
For frontend work, also follow [frontend/AGENTS.md](frontend/AGENTS.md), including
its requirement to consult the installed Next.js documentation before changing code.
[README.md](README.md) covers setup and the API; avoid duplicating those references here.

## Delivery state

- Repository: [pejmanS21/torob-car](https://github.com/pejmanS21/torob-car), public
  when checked on 2026-09-23. Its About description and topics have been configured.
- [PR #3](https://github.com/pejmanS21/torob-car/pull/3) merged into `main` on
  2026-09-22 as [`a7f2637`](https://github.com/pejmanS21/torob-car/commit/a7f263780eb4e41dbc3fae007ae44e786292b579).
  It includes accounts/authentication, protected administration, assistant chat,
  and the quality/coverage fixes. [PR #2](https://github.com/pejmanS21/torob-car/pull/2)
  was also marked merged because its commits are included.
- The last feature commit is
  [`c028158`](https://github.com/pejmanS21/torob-car/commit/c0281584c23d62aefb033e1a4fb63a33654c7b23).
  The local checkout is still `feat/admin-panel`; the merged work is already on
  `origin/main`. Check `git status` and fetch before starting another change.
- This documentation update adds live `main` workflow badges to README, refreshes
  this handoff, and creates the root guidance symlink. It follows the application
  merge on `feat/admin-panel`; check GitHub before assuming it is also on `main`.
- Untracked local material includes `brag-output*/`, `demo-script.md`,
  `graphify-out/`, `output/`, and `prototype/`. Preserve it; it was not included in
  the application commit. Do not assume the code graph reflects the latest code.

## Verified results

The following GitHub Actions runs for merge commit `a7f2637` completed successfully,
verified on 2026-09-23:

| Workflow | Run |
|---|---|
| CI: backend and frontend | [35737593434](https://github.com/pejmanS21/torob-car/actions/runs/35737593434) |
| Security: Semgrep and Gitleaks | [35737593070](https://github.com/pejmanS21/torob-car/actions/runs/35737593070) |
| Docker image build and publishing | [35737593081](https://github.com/pejmanS21/torob-car/actions/runs/35737593081) |

Local validation of the merged application on 2026-09-22:

- Backend: **463 passed, 1 skipped**. Frontend: **135 passed**.
- TypeScript, ESLint, Ruff, Black, production frontend build, and commit hooks passed.
- [Local SonarQube project](http://localhost:9000/dashboard?id=torobcar):
  **100% line coverage**, **0 uncovered lines**, **0 Reliability issues**,
  **0 Maintainability issues**, and a passing quality gate. These are recorded
  results for that scan, not a guarantee for future changes or branch coverage.
- One existing low-severity Security finding remains: `typescript:S5332` for the
  internal HTTP backend URL in `frontend/src/lib/api/base.ts`. Internal networking
  is documented in `CLAUDE.md`; HTTPS cannot simply be substituted without configuring it.
- `pre-commit.ci` reported that private repositories require its paid plan during
  the merge. Local hooks passed. The repository is now public; recheck the current
  integration status if it reports an error again.

## Behavior to preserve

- Search can use the deterministic rules parser when a model is unavailable.
  The buying assistant requires a working model and returns
  `assistant_unavailable` instead of inventing a fallback answer.
- The reported query `دنا پلاس اتمات` led to fixes for inaccurate car details:
  recommendations retain exact-match metadata, expose known listing details, and
  distinguish seller claims, conflicting gearbox/trim information, and installment
  or allocation offers. See `backend/llm/assistant_agent.py`,
  `backend/services/assistant_service.py`, and their tests.
- Chat uses POST SSE with readable Persian text snapshots, a committed final answer,
  and account-owned saved conversations. Anonymous replies are limited per client IP
  in PostgreSQL. Streaming failures before the first text do not consume quota.
  See `backend/api/assistant_stream.py`, `backend/services/chat_service.py`,
  `backend/services/anonymous_chat_limit.py`, and `frontend/src/lib/api/assistant-stream.ts`.
- Admin actions require fresh authentication, prevent self/last-admin lockout,
  and write an audit entry in the same transaction. UI includes filtering and
  pagination. See `backend/api/v1/admin/`, `backend/services/admin_user_service.py`,
  and `frontend/src/app/admin/`.
- An obsolete successful request must not overwrite the latest result in `useApi`.
  The regression test is `frontend/src/lib/api/useApi.test.tsx`.
- Listings come from Divar, Bama, Karnameh, and Hamrah Mechanic. Only Divar listings
  establish the price baseline. Live row counts and the running container revision
  were not rechecked for this handoff.

## Development and validation

Use **uv** from `backend/` and **Bun** from `frontend/`. The supported local stack
is served through Traefik at `http://localhost`; backend/frontend ports are internal.
The backend container applies Alembic migrations at startup, currently through
`0006_anonymous_chat_quotas`. A successfully published image does not establish
that an existing local or deployed stack has been updated.

```bash
# From the repository root:
./.scripts/test-db.sh
(cd backend && uv run pytest -q --cov=. --cov-report=xml)
(cd frontend && bun test --coverage --coverage-reporter=lcov --coverage-dir=coverage)
(cd frontend && bunx tsc --noEmit && bun run lint && bun run build)
pre-commit run --all-files
./.scripts/sonar.sh
```

- Frontend interaction tests use Happy DOM and React Testing Library. Shared setup
  and network fixtures are in `frontend/test/`; preload configuration is in
  `frontend/bunfig.toml`.
- Coverage includes Alembic's environment/startup code. Applied migration version
  files remain excluded under the existing project policy. Do not exclude
  application code or alter reports to meet the coverage target.
- `sonar.sh` runs tests before loading `.env`, then adjusts coverage paths for
  the scanner container. Exporting the entire application environment before tests
  previously caused model/settings tests to fail.
- SonarQube runs via `.docker/compose.sonar.yml` at `http://localhost:9000`.
  `SONAR_TOKEN` belongs in the ignored `.env`; never print or commit credentials.
- Docker's frontend builder uses Node because Next/Turbopack builds under Bun's
  Node shim previously failed on linux/arm64. See `.docker/frontend.Dockerfile`.
- The in-app browser was unavailable in the prior session. Check availability before
  promising live UI validation; the component tests do not replace a browser smoke run.

## Next work

No application feature task is currently assigned. The requested reliability,
maintainability, coverage, commit, merge, and About-section work is complete.
For the next task, start from current `main`, preserve local artifacts, and verify
any assumptions about the running stack. Admin listing moderation, catalog editing,
and ingest-job management are later phases, not implemented by the merged Phase 1;
see [the admin design](docs/superpowers/specs/2026-09-21-torobcar-admin-panel-design.md).

## Suggested skills

- `handoff`: refresh this document when project state changes; the user requested
  this repository-local handoff explicitly.
- `review`: when asked to review a future diff against repository standards and its spec.
- `browser:control-in-app-browser` or `playwright`: for requested live UI validation,
  subject to the available browser tools in that session.
