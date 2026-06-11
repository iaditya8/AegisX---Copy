# Project Structure

This document defines the strict directory and file structure for the AegisX backend platform, adhering to the Clean Architecture and Domain-Driven Design (DDD) principles defined in `09_CodingStandards.md`.

All AI agents and contributors must follow this structure exactly.

## Repository Root

```text
AegisX/
├── backend/                  # Python backend application
├── frontend/                 # Next.js frontend (deferred for MVP foundation)
├── plugins/                  # Independent plugin wrappers and manifests
├── Docs/                     # Documentation and Blueprints
├── .github/                  # GitHub Actions CI/CD workflows
├── docker-compose.yml        # Local development stack
├── Makefile                  # Utility commands (build, test, lint)
└── README.md                 # Project entry point
```

## Backend Application (`backend/`)

The backend is built with FastAPI, PostgreSQL, and Celery. The code is organized into layers pointing inward (Infrastructure -> API -> Services -> Domain).

```text
backend/
├── alembic/                  # Database migration scripts
│   ├── versions/
│   └── env.py
├── src/                      # Application source code
│   ├── api/                  # Presentation Layer (FastAPI Routers)
│   │   └── v1/
│   │       ├── routers/      # HTTP endpoints (e.g., users.py, scopes.py)
│   │       └── dependencies/ # FastAPI dependencies (auth, db session)
│   ├── core/                 # Cross-cutting concerns & Config
│   │   ├── config.py         # Pydantic BaseSettings for env vars
│   │   ├── security.py       # JWT creation, hashing
│   │   ├── logging.py        # Structured JSON logger setup
│   │   └── exceptions.py     # Global exception handlers
│   ├── domain/               # Domain Layer (Enterprise Business Logic)
│   │   ├── entities/         # Pydantic models (Asset, Scope, Finding)
│   │   └── repositories/     # Interface definitions for data access (Protocols)
│   ├── services/             # Service Layer (Application Business Logic)
│   │   ├── auth_service.py   # Login, RBAC
│   │   ├── recon_service.py  # Orchestrates recon logic
│   │   └── workflows.py      # Workflow state machine logic
│   ├── infrastructure/       # Data Layer & External Adapters
│   │   ├── database/
│   │   │   ├── models.py     # SQLAlchemy ORM definitions
│   │   │   └── session.py    # Postgres connection setup
│   │   ├── repositories/     # SQLAlchemy implementations of Domain protocols
│   │   ├── celery/           # Celery worker and task definitions
│   │   │   ├── worker.py     # Celery app initialization
│   │   │   └── tasks/        # Background tasks (e.g., run_nuclei.py)
│   │   └── events/           # Redis pub/sub or stream clients
│   ├── main.py               # FastAPI application entry point
│   └── requirements.txt      # Python dependencies (or pyproject.toml)
├── tests/                    # Testing suite (Pytest)
│   ├── unit/                 # Tests for services, domain, core
│   ├── integration/          # Tests for API endpoints and DB repos
│   └── conftest.py           # Pytest fixtures
└── Dockerfile                # Backend container image definition
```

## Plugin Structure (`plugins/`)

Plugins run out-of-process or inside Celery workers using a sandbox. Each plugin defines its own manifest.

```text
plugins/
├── subfinder/
│   ├── manifest.json         # Plugin capabilities, version, permissions
│   ├── wrapper.py            # Python wrapper implementing the plugin interface
│   └── test_wrapper.py       # Plugin-specific tests
├── nuclei/
│   ├── manifest.json
│   └── wrapper.py
└── ...
```

## Rules for Code Placement

1. **No Business Logic in API Layer**: `src/api/v1/routers/` files should only handle HTTP validation, invoke a service from `src/services/`, and return responses adhering to the Standard Success Response shape.
2. **Domain Layer is Pure**: Files in `src/domain/` must not import anything from `src/infrastructure/` or `src/api/`. They contain data models (`dataclasses` or `Pydantic`) and abstract repository protocols.
3. **Infrastructure Implements Domain**: `src/infrastructure/repositories/` contains the actual SQLAlchemy code, implementing the abstract protocols defined in the Domain layer.
4. **Services Tie It Together**: `src/services/` orchestrates flow by taking in domain entities, calling infrastructure repositories, and enforcing business rules.
5. **Config & Environment**: All environment variables and settings must be centralized in `src/core/config.py`.

---
Prepared by the Principal Software Architect for AegisX.
