.PHONY: up down install lint lint-backend lint-frontend format test test-backend test-frontend test-all build build-frontend build-backend ci shell db-upgrade

up:
	docker compose up -d --build

down:
	docker compose down

install:
	poetry install
	cd frontend && npm install

lint-backend:
	poetry run ruff check backend/
	poetry run black --check backend/
	poetry run isort --check-only backend/

lint-frontend:
	cd frontend && npm run lint

lint: lint-backend lint-frontend

format:
	poetry run ruff format backend/
	poetry run black backend/
	poetry run isort backend/

test-backend:
	poetry run pytest

test-frontend:
	cd frontend && npm run test

test-all: test-backend test-frontend

build-frontend:
	docker build -t aegisx-frontend:latest ./frontend

build-backend:
	docker build -t aegisx-backend:latest -f backend/Dockerfile .

build-all: build-backend build-frontend

ci: lint test-all

shell:
	docker compose exec api bash

db-upgrade:
	poetry run alembic upgrade head
