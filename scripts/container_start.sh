#!/usr/bin/env sh
set -eu
uv run --no-sync --directory backend python -m app.seed
exec uv run --no-sync --directory backend uvicorn app.main:get_app --factory --host 0.0.0.0 --port 8000
