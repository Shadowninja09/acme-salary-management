# ACME Employee Salary Management System

Web application for ACME’s HR Manager to maintain employee and salary records and, when implemented, analyze how the organization pays about 10,000 people across countries.

This repository is an Incubyte engineering assessment. Session login/logout, CSRF on mutations, employee create/list, salary create/history/as-of/correction, correction-history reads, a React UI for those workflows, and a **1,000-employee** development seed are in the repository. Compensation **analytics**, a **10,000-employee** seed, employee update and server-side search APIs, frontend automated tests, and deployment are **not** done. Intended scope vs current status: [`docs/requirements.md`](docs/requirements.md) section 9.

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
| UI | React 19, TypeScript, Vite 8 (`frontend/`) |
| API | FastAPI, Pydantic |
| Data | PostgreSQL, SQLAlchemy, Alembic |
| Backend tests | pytest, FastAPI TestClient |
| Frontend checks | ESLint, `tsc` (`npm run lint`, `npm run build`). No Vitest suite |

Backend Python packages are listed in `requirements.txt`. Frontend packages are listed in `frontend/package.json`.

## Current capabilities

Public:

- `GET /health` — liveness check; does not use the database

Authentication (configured HR Manager; secrets live in `.env`, not in git):

- `POST /api/v1/auth/login` — trusted-origin check, then credentials. On success, sets HttpOnly `acme_session` and a session-bound `acme_csrf` cookie (not HttpOnly)
- `POST /api/v1/auth/logout` — requires a valid session and CSRF token (`acme_csrf` cookie plus `X-CSRF-Token` header); revokes the session and clears both cookies

Employee HTTP APIs require an authenticated session. Create also requires CSRF validation:

- `POST /api/v1/employees` — create an employee (duplicate `employee_code` returns 409)
- `GET /api/v1/employees/{employee_id}` — fetch by internal database id
- `GET /api/v1/employees` — list with `limit` (default 50, max 100) and `offset` (default 0)

There is no employee update API. List has no search query parameters.

Salary HTTP (session required; create and correction also require CSRF):

- `POST /api/v1/employees/{employee_id}/salaries` — create a salary (`amount` as a decimal string or integer). Duplicate employee + effective date returns 409.
- `GET /api/v1/employees/{employee_id}/salaries` — salary history for that employee, newest `effective_from` first. Empty list if the employee has no salaries.
- `GET /api/v1/employees/{employee_id}/salaries/as-of?date=YYYY-MM-DD` — salary effective on or before that date, or `null` if none applies.
- `PATCH /api/v1/employees/{employee_id}/salaries/{salary_id}` — correct an existing salary (non-blank `reason` required). Updates the same row and writes an UPDATE audit entry. Keeping that row’s existing `effective_from` is allowed. Using another of the same employee’s dates returns 409.
- `GET /api/v1/employees/{employee_id}/salary-corrections` — UPDATE audit history for that employee (newest `changed_at` first). CREATE audits are not included. GET does not require a CSRF header.

Frontend (`frontend/`): login, logout, paginated directory (search/filter apply to the **current page** only), employee details, add salary, correct salary, salary history, and correction history. In development, Vite proxies `/api` to `http://127.0.0.1:8000`. The UI copies `acme_csrf` into `X-CSRF-Token` on POST/PATCH except login.

## Repository structure

```text
acme-salary-management/
├── artifacts/
├── backend/
│   ├── app/
│   ├── migrations/
│   ├── scripts/
│   │   └── seed_dev_data.py
│   ├── tests/
│   ├── alembic.ini
│   └── pytest.ini
├── docs/
├── frontend/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Prerequisites

- Python 3.13 with the packages in `requirements.txt` (this repo uses a `.venv` at the project root)
- Node.js for the frontend (`frontend/package.json`)
- PostgreSQL, with two databases:
  - `acme_salary` — application data and development seed
  - `acme_test` — automated tests only

Copy `.env.example` to `.env` and replace the placeholders (`DATABASE_URL`, HR Manager username and password hash, session cookie settings, CSRF signing secret, and trusted login origins). For local UI login, include the Vite origin (Vite’s default is `http://localhost:5173`) in `CSRF_TRUSTED_ORIGINS`. Do not commit `.env`.

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/acme_salary
```

Create the `acme_test` database once (pytest does not create or drop databases). pytest derives the test URL from `DATABASE_URL` with SQLAlchemy `make_url()`, changing only the database name to `acme_test`. It refuses to run test migrations against any other name and does not fall back to `acme_salary`. `DATABASE_URL` may live in the process environment or in `.env` at the repo root or `backend/`.

Apply application migrations to `acme_salary` before using the API or seed (Alembic from `backend/`, using application `DATABASE_URL`). Ordinary Alembic does not use the pytest test URL. This README does not record a specific migrate command output.

## Local UI and API

The FastAPI application object is `app.main:app` under `backend/`. The Vite proxy expects the API at `http://127.0.0.1:8000`. From `frontend/`, `npm run dev` starts the UI. Exact process-manager flags are not prescribed here.

## Development seed

From `backend/`, with `DATABASE_URL` pointing at `acme_salary`:

```powershell
..\.venv\Scripts\python.exe scripts\seed_dev_data.py
```

Default `--count` is 1000. The script refuses `acme_test` and any database name other than `acme_salary`.

## Running tests

Backend, from PowerShell (no need to export `TEST_DATABASE_URL`):

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest
```

If `DATABASE_URL` is missing or the derived target is not exactly `acme_test`, integration tests fail rather than migrating the application database. `/health` does not need PostgreSQL.

Do not run application migrations as part of pytest setup against `acme_salary`. Tests upgrade the **test** database only.

Frontend checks, from `frontend/`:

```powershell
npm run lint
npm run build
```

## Project status

**Present:** Auth, employee create/list, salary HTTP (including correction and correction history), React workflows for those features, 1,000-employee development seed, backend pytest suite, frontend lint/build.

**Not done:** Employee update API; server-side search/filter; analytics API/UI; 10,000-employee seed; frontend automated tests; production deployment (`SESSION_COOKIE_SECURE`, real trusted origins); demo video.

## Development approach

- Implement in small steps with tests beside backend behavior.
- Keep HTTP, business rules, and data access separate.
- Use a dedicated test database and roll back test data; do not point tests at `acme_salary`.
- Review AI-generated code and validate it through tests.
- Commit incrementally. Record prompts and trade-offs under `artifacts/` when they occur.

## Open decisions

1. Deployment target and production configuration (`SESSION_COOKIE_SECURE`, real `CSRF_TRUSTED_ORIGINS`)
2. Analytics APIs and server-side employee search/filter and employee update
3. Audit retention and administrative access policy
4. UI component library and frontend automated tests
