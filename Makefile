.PHONY: install test lint verify ingest inspect
install:
	python -m pip install -e ".[dev]"
test:
	pytest -q
lint:
	ruff check .
verify:
	python -m bankrisk.cli verify
ingest:
	python -m bankrisk.cli ingest
inspect:
	python -m bankrisk.cli inspect
