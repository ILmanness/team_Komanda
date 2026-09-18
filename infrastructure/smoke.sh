#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 180
docker compose exec -T backend alembic current
docker compose exec -T -e RUN_DB_TESTS=1 backend pytest -q
docker compose exec -T backend ruff check app tests migrations
docker compose exec -T frontend npm run build
docker compose exec -T frontend npm test
docker compose exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health/ready').read().decode())"
echo 'Smoke checks passed. Containers remain running; use docker compose down to stop.'
