# ACME Employee Salary Management System

Web application for ACME’s HR Manager to maintain employee and salary records and analyze how the organization pays about 10,000 people across countries.

This repository is an Incubyte engineering assessment. The backend can create, fetch, and paginate employees. Salary workflows, authentication, the frontend, seeding, and deployment are not implemented yet.

## Requirements

- One-page brief: [`docs/requirements-brief.md`](docs/requirements-brief.md)
- Full specification: [`docs/requirements.md`](docs/requirements.md)
- Architecture: [`docs/architecture.md`](docs/architecture.md)
- Database design: [`docs/database-design.md`](docs/database-design.md)
- Delivery (deploy, demo, submit): [`docs/delivery-checklist.md`](docs/delivery-checklist.md)
- Working notes: [`artifacts/`](artifacts/)

## Technology stack

| Layer | Choice |
|---|---|
| UI | React and Vite (planned; not in the repository yet) |
| API | FastAPI, Pydantic |
| Data | PostgreSQL, SQLAlchemy, Alembic |
| Backend tests | pytest, FastAPI TestClient |

Backend Python packages are listed in `requirements.txt`.

## Current backend capabilities

- `GET /health` — liveness check; does not use the database
- `POST /api/v1/employees` — create an employee (duplicate `employee_code` returns 409)
- `GET /api/v1/employees/{employee_id}` — fetch by internal database id
- `GET /api/v1/employees` — list with `limit` (default 50, max 100) and `offset` (default 0)

## Repository structure

```text
acme-salary-management/
├── artifacts/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   ├── alembic.ini
│   └── pytest.ini
├── docs/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

There is no `frontend/` package yet.

## Prerequisites

- Python 3.13 with the packages in `requirements.txt` (this repo uses a `.venv` at the project root)
- PostgreSQL, with two databases:
  - `acme_salary` — application data
  - `acme_test` — automated tests only

Copy `.env.example` to `.env` and replace the placeholders. Do not commit `.env`.

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/acme_salary
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/acme_test
```

**`TEST_DATABASE_URL` must point at `acme_test`, never at `acme_salary`.** Integration tests apply Alembic migrations to that URL and would otherwise change the application database.

pytest reads `TEST_DATABASE_URL` from the process environment. A value only in `.env` is not enough.

## Running tests

From PowerShell, in the current terminal session (use your real username and password, not these placeholders):

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@localhost:5432/acme_test"
Set-Location backend
..\.venv\Scripts\python.exe -m pytest
```

If `TEST_DATABASE_URL` is not set, `/health` still runs and passes. Employee persistence and API tests skip with: `TEST_DATABASE_URL is not configured; skipping database integration tests`.

Do not run application migrations as part of pytest setup against `acme_salary`. Tests upgrade the **test** database only.

## Project status

**Phase:** Backend employee persistence and HTTP API.

Not done: authentication, salary records, analytics, 10k seed, frontend, deployment, video demo.

## Development approach

- Implement in small steps with tests beside each behavior.
- Keep HTTP, business rules, and data access separate.
- Use a dedicated test database and roll back test data; do not point tests at `acme_salary`.
- Review AI-generated code and validate it through tests.
- Commit incrementally. Record prompts and trade-offs under `artifacts/` when they occur.

## Open decisions

1. Authentication for the single HR Manager
2. Deployment target and configuration
3. Audit snapshot details and retention
4. UI component library
