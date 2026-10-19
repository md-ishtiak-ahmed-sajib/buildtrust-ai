#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
uv run --directory backend python -m app.seed
exec uv run --directory backend uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8000
