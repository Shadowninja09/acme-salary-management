# ACME Employee Salary Management System

Web application for ACME’s HR Manager to maintain employee and salary records and analyze how the organization pays about 10,000 people across countries.

This repository is an Incubyte engineering assessment. The backend can create, fetch, and paginate employees behind session authentication; login, logout, and CSRF protection are in place. Salary creation, history, and applicable-as-of lookup are available over HTTP. Correction APIs are not. Analytics, the frontend, seeding, and deployment are not implemented yet.

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

Public:

- `GET /health` — liveness check; does not use the database

Authentication (configured HR Manager; secrets live in `.env`, not in git):

- `POST /api/v1/auth/login` — trusted-origin check, then credentials. On success, sets HttpOnly `acme_session` and a session-bound `acme_csrf` cookie (not HttpOnly)
- `POST /api/v1/auth/logout` — requires a valid session and CSRF token (`acme_csrf` cookie plus `X-CSRF-Token` header); revokes the session and clears both cookies

Employee HTTP APIs require an authenticated session. Create also requires CSRF validation:

- `POST /api/v1/employees` — create an employee (duplicate `employee_code` returns 409)
- `GET /api/v1/employees/{employee_id}` — fetch by internal database id
- `GET /api/v1/employees` — list with `limit` (default 50, max 100) and `offset` (default 0)

Salary HTTP (session required; create also requires CSRF):

- `POST /api/v1/employees/{employee_id}/salaries` — create a salary (`amount` as a decimal string or integer). Duplicate employee + effective date returns 409.
- `GET /api/v1/employees/{employee_id}/salaries` — salary history for that employee, newest `effective_from` first. Empty list if the employee has no salaries.
- `GET /api/v1/employees/{employee_id}/salaries/as-of?date=YYYY-MM-DD` — salary effective on or before that date, or `null` if none applies.

Correction HTTP is not implemented yet. Create/correct/applicable-salary lookup and audit logging exist in the salary service.

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

Copy `.env.example` to `.env` and replace the placeholders (database URLs, HR Manager username and password hash, session cookie settings, CSRF signing secret, and trusted login origins). Do not commit `.env`.

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

**Phase:** Backend employee HTTP API, create-salary HTTP API, salary-history HTTP API, and applicable-as-of HTTP API, with session authentication and CSRF on mutations.

Not done: employee update/search APIs; salary correction HTTP; analytics; 10k seed; frontend; deployment; video demo.

## Development approach

- Implement in small steps with tests beside each behavior.
- Keep HTTP, business rules, and data access separate.
- Use a dedicated test database and roll back test data; do not point tests at `acme_salary`.
- Review AI-generated code and validate it through tests.
- Commit incrementally. Record prompts and trade-offs under `artifacts/` when they occur.

## Open decisions

1. Deployment target and production configuration (`SESSION_COOKIE_SECURE`, real `CSRF_TRUSTED_ORIGINS`)
2. Remaining salary HTTP contract (correction), analytics APIs, and employee search/filter
3. Audit retention and administrative access policy
4. UI component library
