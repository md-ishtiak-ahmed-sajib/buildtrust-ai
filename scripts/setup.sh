#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
uv sync --project backend --locked
npm --prefix frontend ci
npm --prefix frontend run build
uv run --directory backend python -m app.seed
printf '\nCredentials are in data/demo-credentials.json. Run scripts/run_demo.sh\n'
