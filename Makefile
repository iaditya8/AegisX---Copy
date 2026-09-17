.PHONY: up down lint lint-backend lint-frontend format test test-backend test-frontend test-all build build-frontend build-backend ci shell db-upgrade

up:
	docker compose up -d --build

down:
	docker compose down

lint-backend:
	ruff check backend/
	black --check backend/
	isort --check-only backend/

lint-frontend:
	cd frontend && npm run lint

lint: lint-backend lint-frontend

format:
	ruff format backend/
	black backend/
	isort backend/

test-backend:
	docker compose exec api pytest

test-frontend:
	cd frontend && npm run test

test-all: test-backend test-frontend

build-frontend:
	docker build -t aegisx-frontend:latest ./frontend

build-backend:
	docker build -t aegisx-backend:latest ./backend

build-all: build-backend build-frontend

ci: lint test-all

shell:
	docker compose exec api bash

db-upgrade:
	docker compose exec api alembic upgrade head
