# ACME Employee Salary Management System

Web application for ACME’s HR Manager to maintain employee and salary records and analyze how the organization pays people across countries.

This repository is an Incubyte engineering assessment. Session login/logout, CSRF on mutations, employee create/list with optional server-side search and status filters (no update API), salary create/history/as-of/correction, UPDATE-only correction-history reads, compensation analytics (active employees; groups by currency and pay frequency), a React UI for those workflows, a **1,000-employee** local seed default, and a Vitest + React Testing Library suite (`npm test`, defined in `frontend/package.json`) are in the repository. A **local** `acme_salary` demo database has been inspected at 10,000 employees (see Development seed). Production deployment and a demo video remain **release tasks**. Scope: [`docs/requirements.md`](docs/requirements.md) sections 9–10.

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
| Frontend checks | ESLint, `tsc`, Vitest (`npm run lint`, `npm run build`, `npm test`) |

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
- `GET /api/v1/employees` — paginated list (`limit` default 50, max 100; `offset` default 0). Optional `q` is a case-insensitive substring across `employee_code`, `full_name`, `country`, `department`, and `job_title` (`%`, `_`, and `\` are treated as literals). Optional `status` is `ACTIVE` or `INACTIVE`; omit it, or send empty / `ALL`, for an unfiltered list. Invalid `status` returns 422. `q` and `status` combine with AND. `total` is the filtered match count.

There is no employee update API.

Salary HTTP (session required; create and correction also require CSRF):

- `POST /api/v1/employees/{employee_id}/salaries` — create a salary (`amount` as a decimal string or integer). Duplicate employee + effective date returns 409. An unsupported employee-country / salary-currency combination returns 422 (create always validates the combination).
- `GET /api/v1/employees/{employee_id}/salaries` — salary history for that employee, newest `effective_from` first. Empty list if the employee has no salaries.
- `GET /api/v1/employees/{employee_id}/salaries/as-of?date=YYYY-MM-DD` — salary effective on or before that date, or `null` if none applies.
- `PATCH /api/v1/employees/{employee_id}/salaries/{salary_id}` — correct an existing salary (non-blank `reason` required). Updates the same row and writes an UPDATE audit entry. Keeping that row’s existing `effective_from` is allowed. Using another of the same employee’s dates returns 409. Changing to an unsupported country–currency combination returns 422; a correction may keep a legacy currency already stored on that row.
- `GET /api/v1/employees/{employee_id}/salary-corrections` — UPDATE audit history for that employee (newest `changed_at` first). CREATE audits are not included. GET does not require a CSRF header.

Frontend (`frontend/`): login, logout, paginated directory (dataset-wide search and status filters sent as `q` and `status`; changing either resets to offset 0), employee details, add salary, correct salary, salary history, UPDATE-only correction history, and compensation analytics. Employee-detail current pay is computed from loaded history, not from the as-of endpoint. In development, Vite proxies `/api` to `http://127.0.0.1:8000`. The UI copies `acme_csrf` into `X-CSRF-Token` on POST/PATCH except login.

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

Copy `.env.example` to **`.env` at the repository root** (the same directory as `.venv` and this README) and replace the placeholders (`DATABASE_URL`, HR Manager username and password hash, session cookie settings, CSRF signing secret, and trusted login origins). For local UI login, include the Vite origin (Vite’s default is `http://localhost:5173`) in `CSRF_TRUSTED_ORIGINS`. Do not commit `.env`.

Application `Settings` load `env_file=".env"` from the **process working directory**. Keep the shell at the repository root for migrate, seed, and API commands below so that file is found. You do not need a second `.env` under `backend/`. `acme_test` remains tests-only.

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/acme_salary
```

Create the `acme_test` database once (pytest does not create or drop databases). pytest derives the test URL from `DATABASE_URL` with SQLAlchemy `make_url()`, changing only the database name to `acme_test`. It refuses to run test migrations against any other name and does not fall back to `acme_salary`. `DATABASE_URL` may also be set in the process environment.

Apply application migrations to `acme_salary` before using the API or seed. Alembic config is `backend/alembic.ini`; `migrations/env.py` uses application `DATABASE_URL` (not the pytest `acme_test` URL) when pytest is not running. From the **repository root**:

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

`PYTHONPATH` is required so `app` imports resolve while the working directory stays at the root `.env`. This README documents the command; it does not record a successful `upgrade` run in this documentation edit.

## Local UI and API

The FastAPI application object is `app.main:app` under `backend/`. The Vite proxy expects the API at `http://127.0.0.1:8000`. From the **repository root** (`--app-dir backend` puts `backend/` on the module path; cwd still loads root `.env`):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

From `frontend/`, `npm run dev` starts the UI. The commands above match the configured ASGI app, Vite proxy, and `uvicorn` dependency; this README does not record a live process.

## Development seed

The seed script (`backend/scripts/seed_dev_data.py`) adds `backend/` to `sys.path` itself, then reads `DATABASE_URL` through application settings. Run it from the **repository root** so `.env` loads. It refuses `acme_test` and any database name other than `acme_salary`. It does not run migrations, delete rows, or write sessions.

```powershell
.\.venv\Scripts\python.exe backend\scripts\seed_dev_data.py
```

Default `--count` is 1000. Assessment/demo scale:

```powershell
.\.venv\Scripts\python.exe backend\scripts\seed_dev_data.py --count 10000
```

Repeated runs **skip** employee codes that already exist. They do not fill in missing salaries, remove extra records, or repair a drifted dataset.

**Verified local demo (not a deployed host):** a read-only inspection of `localhost:5432/acme_salary` on 2026-10-21 found schema revision `0004_create_user_sessions`, **10,000** employees (`EMP-000001`–`EMP-010000`), **18,000** salary records, **18,000** `CREATE` audit records (no `UPDATE` audits in that snapshot), and **1,000** employees with no salary records. That profile is not automatically reproduced by rerunning the seed script.

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
npm test
npm run lint
npm run build
```

`npm test` runs `vitest run` as defined in `frontend/package.json`. A full verification pass on HEAD `6dd4488` recorded **25 tests passed** across **7 files**, plus `npm run lint` and `npm run build`. That figure is not re-run as part of this documentation edit.

## Project status

**Present:** Auth, employee create/list APIs with optional `q` and `status`, salary HTTP (including correction, country–currency validation, and UPDATE-only correction history), compensation analytics HTTP/UI, React workflows for those features, 1,000-employee **local** seed default, a verified local 10,000-employee `acme_salary` dataset (not a deployed environment), backend pytest suite, and frontend Vitest (`npm test` in `frontend/package.json`).

**Release tasks:** production deployment (`SESSION_COOKIE_SECURE`, real trusted origins); demo video. Local 10,000-employee seed inspection does **not** prove deployment readiness.

**Deferred (not this submission):** employee-update API/UI, employee-create UI, include-inactive analytics, monthly ×12 annualization, median/pay-band/trend views. See [`docs/requirements.md`](docs/requirements.md) section 10.

## Development approach

- Implement in small steps with tests beside backend behavior.
- Keep HTTP, business rules, and data access separate.
- Use a dedicated test database and roll back test data; do not point tests at `acme_salary`.
- Review AI-generated code and validate it through tests.
- Commit incrementally. Record prompts and trade-offs under `artifacts/` when they occur.

## Open decisions

1. Deployment target and production configuration (`SESSION_COOKIE_SECURE`, real `CSRF_TRUSTED_ORIGINS`)
2. Audit retention and administrative access policy
3. Items listed as future enhancements in `docs/requirements.md` section 10
