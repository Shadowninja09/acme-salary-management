# ACME Employee Salary Management System

Web application for ACME’s HR Manager to maintain employee and salary records and analyze how the organization pays about 10,000 people across countries.

This repository is an Incubyte engineering assessment. Design documents exist; application features are not implemented yet.

## Requirements

- One-page brief: [`docs/requirements-brief.md`](docs/requirements-brief.md)
- Full specification: [`docs/requirements.md`](docs/requirements.md)
- Architecture: [`docs/architecture.md`](docs/architecture.md)
- Database design: [`docs/database-design.md`](docs/database-design.md)
- Delivery (deploy, demo, submit): [`docs/delivery-checklist.md`](docs/delivery-checklist.md)
- Working notes: [`artifacts/`](artifacts/)

## Technology stack

Chosen in architecture; not all of it exists in the repo yet.

| Layer | Choice |
|---|---|
| UI | React, Vite (component library not chosen) |
| API | FastAPI, Pydantic |
| Data | PostgreSQL, SQLAlchemy, Alembic |
| Backend tests | pytest, FastAPI TestClient |
| Frontend tests | Vitest, React Testing Library (planned; no frontend package yet) |

Backend Python packages are listed in `requirements.txt`. That file has not been verified by installing or running the application in this environment.

## Current repository structure

```text
acme-salary-management/
├── artifacts/
│   ├── README.md
│   ├── ai-usage.md
│   ├── trade-offs.md
│   └── performance.md
├── backend/
│   └── app/
│       ├── core/
│       │   └── config.py
│       ├── db/
│       └── main.py
├── docs/
│   ├── requirements-brief.md
│   ├── requirements.md
│   ├── architecture.md
│   ├── database-design.md
│   └── delivery-checklist.md
├── .gitignore
├── README.md
└── requirements.txt
```

Also present at the repo root: the original assessment Word document. Planned but **not created**: `frontend/`, `backend/migrations/`, `backend/tests/`, `scripts/`, and most backend packages described in architecture.

`backend/app/main.py` is empty. `backend/app/core/config.py` defines a `database_url` setting only.

## Project status

**Phase:** Documentation aligned with the assessment. Implementation has not started.

Not done: employee/salary APIs, UI, migrations, seed, tests, deployment, video demo.

## Development and testing approach

- Implement in small steps with tests beside each behavior.
- Keep HTTP, business rules, and data access separate (see architecture).
- Prefer fast, deterministic unit tests; add API/database integration tests for constraints and transactions.
- Use AI to draft code and tests; review and verify before keeping changes.
- Commit incrementally so the history shows how the solution evolved.
- Capture prompts, trade-offs, and performance results under `artifacts/` when they actually occur.

Setup, test, seed, and deploy commands will be added here after they have been run successfully.

## Open decisions

These remain unresolved on purpose:

1. Authentication for the single HR Manager
2. Test-database and transaction strategy
3. API contracts, errors, and pagination conventions
4. Deployment target and configuration
5. Audit snapshot details and retention
6. UI component library
