# ACME Employee Salary Management System

Web application for ACME’s HR Manager to maintain employee and salary records and analyze how the organization pays people across countries.

This repository is an Incubyte engineering assessment. It is a **local** same-origin app (React UI served by FastAPI, PostgreSQL). It is not a public or production deployment. Production HTTPS, a public URL, and a demo video remain **release tasks**. Scope: [`docs/requirements.md`](docs/requirements.md) sections 9–10.

**For a recruiter or reviewer:** use **Docker Compose** below. You choose the HR Manager login username and password locally (they are not stored in git). After first-time migrate and seed, the UI is `http://localhost:8000`.

## Requirements documents

- One-page brief: [`docs/requirements-brief.md`](docs/requirements-brief.md)
- Full specification: [`docs/requirements.md`](docs/requirements.md)
- Architecture: [`docs/architecture.md`](docs/architecture.md)
- Database design: [`docs/database-design.md`](docs/database-design.md)
- Delivery (deploy, demo, submit): [`docs/delivery-checklist.md`](docs/delivery-checklist.md)
- Working notes: [`artifacts/`](artifacts/)

## Technology stack and architecture

| Layer | Choice |
|---|---|
| UI | React 19, TypeScript, Vite 8 (`frontend/`) |
| API | FastAPI, Pydantic |
| Data | PostgreSQL, SQLAlchemy, Alembic |
| Backend tests | pytest, FastAPI TestClient |
| Frontend checks | ESLint, `tsc`, Vitest (`npm run lint`, `npm run build`, `npm test`) |

Backend Python packages are listed in `requirements.txt`. Frontend packages are listed in `frontend/package.json`.

The production-style local image **builds** the Vite app and serves it from FastAPI on port 8000 (same origin as `/api/*` and `/health`). There is no CORS layer. Vite’s `/api` proxy is **development only** (`npm run dev`). Compose PostgreSQL is a separate server on the Docker network (hostname `db`); port 5432 is not published to the host.

## Current capabilities

Public:

- `GET /health` — liveness check; does not use the database

Authentication (configured HR Manager; secrets live in `.env` / `.env.compose`, not in git):

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
├── .dockerignore
├── .env.example
├── .gitignore
├── compose.yaml
├── Dockerfile
├── README.md
└── requirements.txt
```

Git-ignored local files (create these; do not commit them): `.env`, `.env.compose`, `.venv/`, `frontend/node_modules/`, `frontend/dist/`.

## Reviewer setup (Docker Compose)

This is the intended **local** evaluation path. It does not publish the app, provision cloud resources, or enable production TLS. Containers do **not** run migrations or the demo seed on startup.

### Prerequisites

- Docker Engine and Docker Compose v2 (Docker Desktop on Windows is fine)
- PowerShell at the **repository root**

You do **not** need host PostgreSQL, Node, or a Python venv to *run* the Compose app. You still need Python/Node/PostgreSQL on the host to run the test suites (see [Running tests](#running-tests)).

### First-time setup

**1. Environment files**

Copy `.env.example` to `.env` at the repository root. Replace placeholders. Do not commit `.env`.

Required for Compose interpolation (alphanumeric `POSTGRES_PASSWORD`; avoid `@`, `:`, `/`, `$`):

```text
POSTGRES_USER=acme
POSTGRES_PASSWORD=replace_with_local_compose_password
POSTGRES_DB=acme_salary
```

`POSTGRES_DB` must remain `acme_salary` if you want to run the seed script (it refuses any other database **name**, including `acme_test`). That name on the Compose server is not the host’s `localhost:5432/acme_salary`.

Also set in `.env`:

- `HR_MANAGER_USERNAME` — the username you will type on the login screen
- `HR_MANAGER_PASSWORD_HASH` — Argon2id hash of the password you will type (not the plaintext)
- `CSRF_SIGNING_SECRET` — at least 32 characters, no leading/trailing spaces
- `SESSION_COOKIE_SECURE=false` — local HTTP only
- `HR_MANAGER_IDENTITY` — audit label (not the login username)

There is **no shared demo password** in git. Choose a local password, then hash it after you have a venv with `requirements.txt`, or from any environment that has `argon2-cffi`:

```powershell
.\.venv\Scripts\python.exe -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('your-password'))"
```

Create Git-ignored **`.env.compose`** in the same directory with **only**:

- `HR_MANAGER_IDENTITY`
- `HR_MANAGER_USERNAME`
- `HR_MANAGER_PASSWORD_HASH`
- `CSRF_SIGNING_SECRET`
- optional `SESSION_MAX_AGE_SECONDS`

Copy those values from `.env`. Wrap the Argon2 hash in **single quotes** so Compose does not treat `$` fragments as variables. Do **not** copy `DATABASE_URL`, `TEST_DATABASE_URL`, `HOST`, `PORT`, `PASSWORD`, or other host-only keys.

`compose.yaml` sets the app container `DATABASE_URL` to host `db` and `CSRF_TRUSTED_ORIGINS` to `http://localhost:8000`. Host-only keys are not loaded into the app container.

**2. Start (build + run)**

```powershell
docker compose up --build
```

**3. Migrate the Compose database only**

Confirm the target **before** any write. The printed host must be `db`, not `localhost`:

```powershell
docker compose exec app python -c "from sqlalchemy.engine.url import make_url; from app.core.config import get_settings; u = make_url(get_settings().database_url); print(u.host, u.port, u.database)"
docker compose exec app python -m alembic -c backend/alembic.ini upgrade head
```

Do not run that Alembic command against the host. Do not migrate `acme_test`.

**4. Seed 10,000 employees (optional but expected for the assessment demo scale)**

Only after migrations, and only against Compose `POSTGRES_DB=acme_salary`:

```powershell
docker compose exec app python backend/scripts/seed_dev_data.py --count 10000
```

Default without `--count` is **1,000** employees. The script skips employee codes that already exist. It does not fill missing salaries, delete extra rows, or repair a drifted dataset. It refuses `acme_test`.

**5. Open and sign in**

Open `http://localhost:8000`. Sign in with the `HR_MANAGER_USERNAME` and **plaintext password** you hashed in step 1. `/api/*` and `/health` are the API; unknown UI paths serve the SPA `index.html`.

### Subsequent startup

If the named volume still exists, you do **not** need to migrate or seed again:

```powershell
docker compose up
```

Then open `http://localhost:8000` and sign in with the same local credentials.

### Stop

```powershell
docker compose down
```

The named volume `acme_compose_pgdata` keeps Compose Postgres data.

`docker compose down -v` **deletes** that volume. It does not touch host `acme_salary` or `acme_test`. After a volume delete you must repeat **migrate** and **seed** (first-time steps 3–4) before the directory has data.

## Host development (optional)

Use this path for local Vite/`uvicorn` or pytest. It is separate from Compose.

### Prerequisites

- Python 3.13 with the packages in `requirements.txt` (this repo uses a `.venv` at the project root)
- Node.js for the frontend (`frontend/package.json`)
- PostgreSQL, with two databases:
  - `acme_salary` — application data and development seed on the host
  - `acme_test` — automated tests only

Copy `.env.example` to **`.env` at the repository root** if you have not already, and set `DATABASE_URL` to host PostgreSQL. For Vite UI login, include `http://localhost:5173` in `CSRF_TRUSTED_ORIGINS`. If `.env` already exists for Compose, **append** host keys; do not overwrite `POSTGRES_*` or HR secrets.

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/acme_salary
```

Application `Settings` load `env_file=".env"` from the **process working directory**. Keep the shell at the repository root for migrate, seed, and API commands so that file is found. You do not need a second `.env` under `backend/`.

Create the `acme_test` database once (pytest does not create or drop databases). pytest derives the test URL from `DATABASE_URL` with SQLAlchemy `make_url()`, changing only the database name to `acme_test`. It refuses to run test migrations against any other name and does not fall back to `acme_salary`.

Host migrations (repository root):

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

From `frontend/`, `npm run dev` starts the Vite UI (proxies `/api` to `http://127.0.0.1:8000`).

Host seed (refuses any database name other than `acme_salary`):

```powershell
.\.venv\Scripts\python.exe backend\scripts\seed_dev_data.py --count 10000
```

## Running tests

Backend, from PowerShell (no need to export `TEST_DATABASE_URL`). Requires host PostgreSQL database `acme_test` and a `.venv`:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest
```

If `DATABASE_URL` is missing or the derived target is not exactly `acme_test`, integration tests fail rather than migrating the application database. `/health` does not need PostgreSQL.

Do not run application migrations as part of pytest setup against `acme_salary`. Tests upgrade the **test** database only.

Frontend checks, from `frontend/` (requires Node.js):

```powershell
npm test
npm run lint
npm run build
```

`npm test` runs `vitest run` as defined in `frontend/package.json`.

## Project status

**Present:** Auth, employee create/list APIs with optional `q` and `status`, salary HTTP (including correction, country–currency validation, and UPDATE-only correction history), compensation analytics HTTP/UI, React workflows for those features, 1,000-employee seed default, `--count 10000` for assessment scale, backend pytest suite, frontend Vitest, and a local Docker Compose recipe.

**Release tasks** (not product gaps): recording a demo video and emailing the repository link. Production HTTPS (`SESSION_COOKIE_SECURE`, real trusted origins, public URL) is optional and unverified. Local Compose on `http://localhost:8000` is not a public deployment. See [`docs/delivery-checklist.md`](docs/delivery-checklist.md).

A **local** host `acme_salary` database was inspected on 2026-10-21 at 10,000 employees / 18,000 salaries (Alembic `0004_create_user_sessions`). That snapshot is not created by cloning the repo; reviewers seed Compose (or host) themselves.

## Future Improvements and Deliberate Exclusions

This is a local HR Manager tool for salary records and honest compensation grouping. It is not a full HRIS or payroll system. Full lists live in [`docs/requirements.md`](docs/requirements.md) (§6, §10) and [`docs/architecture.md`](docs/architecture.md). The items below are **not** claims that implemented APIs are missing: employee **create** HTTP, salary history, as-of HTTP, and **server-side** directory `q` / `status` are already in the product.

### Deliberate exclusions

- **Employee-update API/UI and employee-create UI.** Seed plus list/view is enough to maintain salaries on a large dataset. Create remains on HTTP for seed and API callers.
- **Include-inactive analytics; multiplying monthly pay by 12; medians, pay bands, and trends.** Mixing inactive staff, monthly with annual, or currencies would misstate pay. Groups stay `(currency, pay_frequency)` for **active** employees.
- **Payroll, tax, attendance, self-service, CSV import/export, FX conversion, hourly pay, and natural-language analytics in this submission.** Those need payment, FX, or working-hours rules this assessment does not define. This release keeps analytics as explicit, testable queries. An authenticated HR analytics chatbot is listed below as **planned future work**, not as a current feature.
- **Multi-user roles** beyond the one configured HR Manager.

### Known limitations of this implementation

- The seed script **skips** existing employee codes. It does not fill missing salaries, remove extra rows, or reset the database.
- Employee-detail “current compensation” uses loaded salary history. The as-of HTTP API exists and is tested; the panel does not call it yet.
- Correction history lists **UPDATE** audits only. CREATE events are omitted on purpose.
- No query timings are recorded for the 10,000-employee dataset ([`artifacts/performance.md`](artifacts/performance.md)).
- Directory search is server-side ILIKE on five columns, with no dedicated search index.
- The country–currency allow-list is an extra six-country rule, duplicated in backend and frontend.

### Possible later improvements

These would extend the product; they do not mean the current app is broken.

- Wire the as-of endpoint into the employee-detail current-pay display.
- Add a carefully scoped employee **status** update so HR can inactivate people in the UI.
- Consider include-inactive analytics, clearly labeled, still without mixing currencies or frequencies.
- Measure directory, search, and analytics at 10,000 employees before adding indexes or other optimizations.
- If the app is ever served over HTTPS, set `SESSION_COOKIE_SECURE` and real `CSRF_TRUSTED_ORIGINS`.
- **Planned, not implemented:** an AI-powered HR salary analytics chatbot. The HR Manager would ask natural-language questions (for example how active employees are paid by country or currency) and receive **validated** summaries, tables, or charts. Access would require the existing authenticated HR session. The assistant would call only **approved read-only analytics operations** (not ad-hoc SQL, salary writes, or seed/migrate). Queries would be validated before execution, and responses would avoid leaking sensitive salary data beyond what the HR Manager is already allowed to see. This is future work, not present in the current UI or API.

## Development approach

- Implement in small steps with tests beside backend behavior.
- Keep HTTP, business rules, and data access separate.
- Use a dedicated test database and roll back test data; do not point tests at `acme_salary`.
- Review AI-generated code and validate it through tests.
- Commit incrementally. Record prompts and trade-offs under `artifacts/` when they occur.
