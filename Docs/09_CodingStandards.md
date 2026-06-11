# Coding Standards

## Purpose

This document defines the engineering standards for AegisX.

All contributors, AI agents, and developers must follow these standards to ensure consistency, maintainability, scalability, and security.

---

# 1. Engineering Principles

## Clean Architecture

The project must follow Clean Architecture principles.

Layers:

* Presentation Layer
* API Layer
* Service Layer
* Domain Layer
* Data Layer

Dependencies must always point inward.

---

## SOLID Principles

All code must follow:

* Single Responsibility Principle
* Open/Closed Principle
* Liskov Substitution Principle
* Interface Segregation Principle
* Dependency Inversion Principle

---

## Domain Driven Design

Business logic belongs in domain services.

Avoid placing business logic inside:

* API routes
* Controllers
* Database models

---

# 2. Python Standards

## Python Version

Python 3.13

---

## Formatting

Use:

* Black
* isort

Required before every commit.

---

## Linting

Use:

* Ruff
* Flake8

Code must pass linting checks.

---

## Typing

Type hints are mandatory.

Example:

def create_asset(asset: AssetCreate) -> Asset:
pass

Avoid untyped functions.

---

## Async Programming

Use async/await for:

* HTTP requests
* Database operations
* Background tasks

Avoid blocking operations.

---

# 3. API Standards

## API Versioning

All APIs must be versioned.

Example:

/api/v1/assets
/api/v1/findings

---

## REST Naming

Use nouns.

Good:

/assets
/projects
/findings

Bad:

/getAssets
/createProject

---

## Response Format

Success:

{
"success": true,
"data": {}
}

Error:

{
"success": false,
"error": {
"code": "NOT_FOUND",
"message": "Asset not found"
}
}

---

## Pagination

Required for list endpoints.

Use:

* page
* page_size

---

# 4. Database Standards

## Primary Keys

Use UUIDs.

Never use auto-increment integers for public-facing identifiers.

---

## Naming Convention

Tables:

snake_case

Example:

assets
projects
findings

Columns:

snake_case

---

## Migrations

All schema changes must use Alembic.

Never modify production databases manually.

---

## Soft Deletes

Use soft deletion where appropriate.

Fields:

deleted_at
deleted_by

---

# 5. Security Standards

## Secret Management

Never hardcode:

* API Keys
* Tokens
* Passwords

Use environment variables.

---

## Authentication

JWT required.

All protected endpoints require authentication.

---

## Authorization

RBAC required.

Roles:

* Admin
* Analyst
* Viewer

---

## Input Validation

Validate all inputs using Pydantic models.

Never trust user input.

---

## Dependency Security

Run:

* Trivy
* Safety
* pip-audit

Regularly.

---

# 6. Logging Standards

## Format

Structured JSON logging only.

---

## Levels

Use:

* DEBUG
* INFO
* WARNING
* ERROR
* CRITICAL

---

## Sensitive Data

Never log:

* Passwords
* Secrets
* Tokens
* Session IDs

---

# 7. Testing Standards

## Unit Tests

Required for:

* Services
* Utilities
* Business Logic

---

## Integration Tests

Required for:

* APIs
* Database interactions
* Plugin integrations

---

## Coverage

Minimum:

80%

Target:

90%

---

# 8. Plugin Development Standards

## Plugin Isolation

Every tool integration must be a plugin.

Examples:

* SubfinderPlugin
* AmassPlugin
* NucleiPlugin

---

## Standard Interface

Plugins must implement:

* initialize()
* run()
* validate()
* health_check()

---

## Failure Handling

Plugin failure must never crash the workflow engine.

---

# 9. Documentation Standards

Every module must contain:

README.md

Include:

* Purpose
* Dependencies
* Usage
* Examples

---

## Architecture Updates

Architecture.md must be updated whenever:

* New service added
* Major design changes occur

---

# 10. Git Standards

## Branch Naming

feature/<name>

bugfix/<name>

hotfix/<name>

---

## Commit Format

feat:

fix:

docs:

test:

refactor:

---

# 11. AI Agent Rules

AI-generated code is not trusted by default.

All generated code must:

* Pass linting
* Pass tests
* Follow architecture
* Follow database standards

---

## Source of Truth Priority

1. PRD.md
2. Vision.md
3. Architecture.md
4. Database.md
5. API.md
6. CodingStandards.md

If conflicts exist, follow higher priority documents.

---

# 12. Production Readiness Checklist

Before release:

* Tests pass
* Documentation updated
* Security scan completed
* Docker build succeeds
* CI/CD pipeline succeeds
* No critical vulnerabilities
* Architecture review completed
