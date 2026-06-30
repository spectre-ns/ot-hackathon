test:
	.venv/bin/python -m pytest tests/ -v

seed:
	.venv/bin/python -m app.seed

dev:
	.venv/bin/uvicorn app.main:app --reload --port 8000
