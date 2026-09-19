#!/usr/bin/env bash
# Coverage for both apps, then a SonarQube scan. Exits non-zero when the quality gate
# fails (sonar.qualitygate.wait=true). Needs SONAR_TOKEN in .env and the server from
# .docker/compose.sonar.yml running.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
: "${SONAR_TOKEN:?set SONAR_TOKEN in .env (SonarQube → My Account → Security)}"

./.scripts/test-db.sh
(cd backend && uv run pytest -q --cov=. --cov-report=xml)
(cd frontend && bun test --coverage --coverage-reporter=lcov --coverage-dir=coverage)

# The scanner sees the repo at /usr/src: make both reports resolve from there.
perl -pi -e 's|<source>.*?</source>|<source>/usr/src/backend</source>|' backend/coverage.xml
perl -pi -e 's|^SF:(?!frontend/)|SF:frontend/|' frontend/coverage/lcov.info

docker run --rm --network torobcar-sonar_default \
  -e SONAR_HOST_URL=http://sonarqube:9000 -e SONAR_TOKEN="$SONAR_TOKEN" \
  -v "$PWD:/usr/src" sonarsource/sonar-scanner-cli
