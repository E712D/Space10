.PHONY: up down db-reset seed test test-integration lint e2e export-openapi

up:
	docker compose up --build -d

down:
	docker compose down

db-reset:
	docker compose exec backend python manage.py flush --no-input
	docker compose exec backend python manage.py migrate

seed:
	docker compose exec backend python manage.py load_seeds

test:
	pytest -m "not integration"

test-integration:
	pytest -m integration

lint:
	ruff check .

e2e:
	python tests/e2e_smoke.py

export-openapi:
	docker compose exec backend python manage.py spectacular --file contracts/openapi.json