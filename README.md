# AegisX — Cyber Resilience & Autonomous Security Operations Platform

AegisX is an enterprise-grade security operations, threat intelligence, and autonomous resilience platform designed to unify asset discovery, vulnerability correlation, incident remediation, and continuous compliance governance.

---

## Architecture Overview

```
AegisX/
├── .github/                      # CI/CD workflows (Continuous Integration & Delivery)
├── ADR/                          # Architecture Decision Records
├── Docs/                         # Product Specifications, Architecture & API Documentation
├── Implementation/               # Sprint reviews, implementation blueprints & plans
├── audits/                       # Security & quality certification audits
│   ├── cad-01/                   # CAD-01 certification records
│   └── reports/                  # Runtime, UAT, and performance benchmark reports
├── screenshots/                  # Platform evidence & verification captures
│   └── phases/                   # Phase 01–11 validation screenshots
├── backend/                      # FastAPI async backend service
│   ├── alembic/                  # Database schema migrations
│   ├── src/                      # Clean architecture: Domain, Services, Repositories, API
│   ├── tests/                    # Integration & unit test suite (Pytest)
│   ├── scripts/                  # CLI and administrative utilities
│   └── Dockerfile                # Production container definition
├── frontend/                     # Next.js 16 + React 19 web application
│   ├── src/                      # App router, UI components, hooks, stores
│   ├── public/                   # Static assets & MSW mock worker
│   └── Dockerfile                # Multi-stage standalone production container
├── Makefile                      # Standardized project CLI workflows
├── pyproject.toml                # Poetry dependencies & tool configurations
├── poetry.lock                   # Deterministic Python dependency lockfile
└── docker-compose.yml            # Local orchestration (API, Worker, DB, Redis)
```

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2.0 (Async), PostgreSQL 15, Redis 7, Celery, Alembic |
| **Frontend** | Next.js 16 (Turbopack, App Router), React 19, TypeScript 5, TailwindCSS 4, TanStack Query |
| **Packaging & CI/CD** | Poetry 2.x, GitHub Actions, Docker (Multi-stage), GitHub Container Registry (GHCR) |
| **Testing & Quality** | Pytest, Pytest-Asyncio, Ruff, Black, isort, Vitest, Playwright, ESLint |

---

## Quick Start

### 1. Prerequisites
- [Docker](https://www.docker.com/) & Docker Compose
- [Poetry](https://python-poetry.org/) (version 2.x)
- [Node.js](https://nodejs.org/) (version 20.x or 22.x)

### 2. Local Infrastructure with Docker Compose
Start PostgreSQL, Redis, FastAPI Backend, and Celery Worker:
```bash
make up
```

Stop services:
```bash
make down
```

### 3. Local Development Setup

#### Backend (Python / Poetry)
```bash
# Install dependencies
poetry install

# Run database migrations
poetry run alembic upgrade head

# Run tests
poetry run pytest

# Run linting
poetry run ruff check backend/
```

#### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to access the UI.

---

## Makefile Commands

| Command | Description |
| :--- | :--- |
| `make install` | Install all Python (Poetry) and Frontend (npm) dependencies |
| `make up` | Build and start container services in the background |
| `make down` | Tear down container services |
| `make lint` | Run backend and frontend linting |
| `make format` | Auto-format backend code with Ruff, Black, and isort |
| `make test-backend` | Run backend Pytest suite |
| `make test-frontend` | Run frontend Vitest test suite |
| `make test-all` | Run all backend and frontend tests |
| `make build-all` | Build backend and frontend production Docker images |
| `make ci` | Run full local CI check (lint + test suites) |
| `make db-upgrade` | Apply latest Alembic database migrations |

---

## Documentation Links

- [Product Requirements Document](Docs/01_PRD.md)
- [System Architecture Specification](Docs/03_Architecture.md)
- [Database Schema & Data Model](Docs/04_Database.md)
- [REST API Reference](Docs/05_API.md)
- [Engineering Roadmap](Docs/06_Roadmap.md)
