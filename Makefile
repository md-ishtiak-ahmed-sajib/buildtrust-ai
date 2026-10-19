.PHONY: setup run test evidence
setup:
	sh scripts/setup.sh
run:
	sh scripts/run_demo.sh
test:
	uv run --project backend pytest backend/tests
	npm --prefix frontend test
	npm --prefix frontend run build
evidence:
	uv run --project backend python scripts/collect_evidence.py
