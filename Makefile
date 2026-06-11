.PHONY: up down lint test shell db-upgrade

up:
	docker compose up -d --build

down:
	docker compose down

lint:
	ruff check backend/
	black --check backend/

test:
	docker compose exec api pytest

shell:
	docker compose exec api bash

db-upgrade:
	docker compose exec api alembic upgrade head
