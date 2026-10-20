# ACME Employee Salary Management System — Architecture

## 1. Purpose

This document describes the technical architecture for the ACME Employee Salary Management System.

The application will allow ACME's HR Manager to manage employee information, maintain salary history, and analyze compensation across approximately 10,000 employees in multiple countries.

The architecture prioritizes maintainability, testability, data integrity, auditability, and clear separation of responsibilities.

The initial release supports one configured HR Manager. The backend authenticates that user with a database-backed session. Multi-user management and additional roles are outside the initial scope.

## 2. Technology Stack

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | React 19 and TypeScript (`frontend/`) | HR Manager UI: login, directory, salary history, add/correct salary, correction history |
| Frontend build tool | Vite 8 | Dev server (proxies `/api` to FastAPI), production build |
| Backend API | FastAPI | HTTP endpoints and request handling |
| Request/response validation | Pydantic | Validate API inputs and outputs |
| ORM | SQLAlchemy | Database access and object-relational mapping |
| Database migrations | Alembic | Version and apply database schema changes |
| Database | PostgreSQL | Persistent employee and salary data |
| Backend testing | pytest | Unit and integration tests |
| API testing | FastAPI TestClient | Test HTTP endpoints |
| Frontend checks | ESLint and `tsc` (`npm run lint`, `npm run build`) | Lint and typecheck/build. Vitest / React Testing Library are **not** in the frontend package |
| Version control | Git | Track and review changes |

## 3. High-Level Architecture

The application follows a client-server architecture. The FastAPI backend, PostgreSQL schema, and React frontend are in the repository. Compensation **analytics** HTTP and UI are not implemented.

```text
+----------------------------------+
|     React + Vite Frontend        |
|                                  |
| Login / Logout                   |
| Employee Directory (paginated)   |
| Salary History, Add, Correct     |
| Correction History               |
| Analytics (not implemented)      |
+----------------+-----------------+
                 |
                 | HTTP / JSON (Vite proxies /api in development)
                 v
+----------------------------------+
|          FastAPI Backend         |
|                                  |
| Auth, Employee, Salary Routes    |
| Request / Response Validation    |
| Business Service Layer           |
| Data Access Layer                |
+----------------+-----------------+
                 |
                 | SQLAlchemy
                 v
+----------------------------------+
|            PostgreSQL            |
|                                  |
| Employees                        |
| Salary Records                   |
| Salary Audit Logs                |
| User Sessions                    |
+----------------------------------+
```

The frontend communicates with the backend through REST APIs (`credentials: 'include'`). In local development, Vite proxies `/api` to `http://127.0.0.1:8000` so session cookies stay on the same origin as the UI. The backend validates requests, enforces business rules, executes database operations, and returns structured responses.

The frontend does not access PostgreSQL directly.

## 4. Backend Architecture

The backend will use a layered structure to separate HTTP handling, business logic, and database operations.

### 4.1 API Layer

Responsibilities:

- Define REST API endpoints.
- Accept requests and validate request data.
- Invoke the appropriate business services.
- Return structured responses and appropriate HTTP status codes.
- Apply session authentication and, for state-changing authenticated routes, CSRF validation.

API routes must not contain complex salary calculations or database business rules.

### 4.2 Service Layer

Responsibilities:

- Implement employee and salary management use cases.
- Enforce salary-history and effective-date rules.
- Determine the applicable salary for a specified date.
- Normalize monthly and annual salaries for analytics **when analytics is implemented**.
- Apply employment-status, reporting-date, and currency rules to analytics **when analytics is implemented**.
- Coordinate operations involving multiple database records.
- Ensure salary changes and their corresponding audit entries are persisted atomically.
- Ensure salary corrections retain their before-and-after values and reason.
- Apply business rules independently of HTTP request handling.
- Business rules should be testable independently of HTTP request handling.

### 4.3 Data Access Layer

Responsibilities:

- Perform database queries using SQLAlchemy.
- Create, retrieve, and update persisted records.
- Support filtering, pagination, and analytics queries.
- Apply database transactions where required. `get_db` commits after a successful request and rolls back on error.
- Services currently issue SQLAlchemy queries directly. There is no separate `repositories` package.
- Keep database access details out of HTTP handlers where practical.

### 4.4 Schema Layer

- Pydantic schemas will define API request and response structures.
- They will be separate from SQLAlchemy database models so that API contracts do not depend directly on the database representation.
- Validation will be applied at the API and business-logic layers as appropriate. Database constraints will provide an additional layer of protection for data integrity.

## 5. Frontend Architecture

The React application lives in `frontend/`. Implemented workflows:

- HR Manager login and logout.
- Employee directory with `limit`/`offset` pagination. Search and employment-status controls filter the **current page of API results**, not the full dataset (there is no search query on `GET /api/v1/employees`).
- Employee details, salary history, add salary, and salary correction (reason required). After a successful correction, history and correction history refresh and the correction form closes.
- Correction history table from `GET /api/v1/employees/{id}/salary-corrections` (UPDATE audits only). Displays `changed_at`, salary record id, old/new snapshots, reason, and `changed_by` from the API. The UI does not send `changed_by`.

Compensation analytics views are **not** implemented.

The shared API client (`frontend/src/api/client.ts`) sends cookies on every request. For POST and PATCH other than login, it copies the `acme_csrf` cookie into `X-CSRF-Token` when that header is not already set. GET requests do not attach a CSRF header.

Frontend validation (for example salary amount format) improves usability but does not replace backend validation or access restrictions. There is no frontend unit/component test runner in `frontend/package.json`.

## 6. Initial Domain Model

- The persisted domain model contains four entities: `Employee`, `SalaryRecord`, `SalaryAuditLog`, and `UserSession`.

### 6.1 Employee

Represents an employee within ACME.

Proposed fields:

- `id`: PostgreSQL-generated `BIGINT` primary key.
- `employee_code`: Unique business identifier, such as `EMP-000001`.
- `full_name`: Required employee name.
- `country`: Required country associated with the employee.
- `department`: Required department.
- `job_title`: Required job title.
- `employment_status`: Required current status, restricted to `ACTIVE` or `INACTIVE`.
- `created_at`: Record creation timestamp.
- `updated_at`: Last update timestamp.
- The internal `id` will be used for database relationships. The `employee_code` will be used as the human-readable employee identifier.
- Country, department, and job title will initially be stored as text fields. Separate lookup tables can be considered if future requirements justify them.
- Employees who leave the organization should ordinarily be marked `INACTIVE` rather than deleted.

### 6.2 SalaryRecord

Represents a salary record for an employee from a specified effective date.

Proposed fields:

- `id`: PostgreSQL-generated `BIGINT` primary key.
- `employee_id`: Foreign key referencing `Employee.id`.
- `amount`: Positive `NUMERIC(12,2)` salary amount, handled as Python `Decimal`.
- `currency`: Supported three-letter currency code.
- `pay_frequency`: `MONTHLY` or `ANNUAL`.
- `effective_from`: Date on which the salary becomes applicable.
- `created_at`: Record creation timestamp.
- `updated_at`: Last update timestamp.
- Salary amounts must not be processed using binary floating-point arithmetic. Inputs with more than two decimal places must be rejected rather than silently rounded.
- Supported currencies in the initial version are `INR`, `USD`, `GBP`, `EUR`, `CAD`, and `AUD`.
- The database must enforce uniqueness on the combination of `employee_id` and `effective_from`.
- An employee can have multiple salary records with different effective dates, but only one record per employee may have a given effective date.
- Ordinary salary changes create new records. Correcting an existing salary record updates the existing record and creates an audit entry containing the before-and-after values.
- Future-dated salary records are allowed but must not become applicable before their effective dates.
- Salary records must reference an existing employee. Ordinary application operations must not delete salary records or destroy their history.

### 6.3 SalaryAuditLog

Records salary creation and update events for accountability and historical correction tracking.

Proposed fields:

- `id`: PostgreSQL-generated `BIGINT` primary key.
- `salary_record_id`: Foreign key referencing `SalaryRecord.id`.
- `action`: Action type, restricted to `CREATE` or `UPDATE`.
- `old_values`: Nullable JSONB snapshot of salary values before the change. Null for initial creation.
- `new_values`: Required JSONB snapshot of salary values after the change.
- `reason`: Optional for initial salary creation and required when updating an existing salary record.
- `changed_by`: `VARCHAR(100)` identifier of the configured HR Manager.
- `changed_at`: Timestamp of the audit event.
- The before-and-after snapshots must capture at least the salary amount, currency, pay frequency, and effective date.
- Every salary creation and update must generate an audit entry.
- Salary changes and their corresponding audit entries must be committed in the same database transaction. If the audit entry cannot be persisted, the salary operation must be rolled back.
- Audit entries must not be editable or deletable through ordinary application operations. Database relationships and deletion rules must not allow salary deletion to silently cascade into deletion of its audit history.

#### Audit Identity

The initial release supports one configured HR Manager identity.

- The backend automatically assigns the configured identity to every salary audit event.
- The frontend must not supply or determine the audit identity.
- A separate `users` table is not required in the initial version.
- The configured identity provides audit attribution. It is not loaded from an authenticated user row.
- Session authentication is implemented separately (see section 10). A valid session is required for protected employee and salary APIs.
- A user model and additional roles may be introduced in a future version if requirements expand.
- Salary records remain the source of truth for applicable compensation. Audit logs preserve accountability and evidence of changes.

### 6.4 UserSession

Represents an authenticated HR Manager session.

Fields (migration `0004_create_user_sessions`):

- `id`: PostgreSQL-generated `BIGINT` primary key.
- `token_hash`: SHA-256 hex digest of the opaque session token (`VARCHAR(64)`, unique). The raw token is not stored.
- `created_at`: Session creation timestamp (`TIMESTAMPTZ`).
- `expires_at`: Expiry timestamp (`TIMESTAMPTZ`).
- `revoked_at`: Nullable revocation timestamp.

A session authorizes requests only while it is unexpired and `revoked_at` is null.

### 6.5 Entity Relationships

The initial relationships are:

- One `Employee` can have many `SalaryRecord` entries.
- Each `SalaryRecord` belongs to one `Employee`.
- One `SalaryRecord` can have many `SalaryAuditLog` entries.
- Each `SalaryAuditLog` entry references the affected `SalaryRecord`.
- `UserSession` rows are independent of employees and salaries. They store only a SHA-256 token hash, timestamps, and optional revocation.
- The database must enforce referential integrity using primary and foreign key constraints.
- Employees should ordinarily be deactivated rather than deleted. Salary records and audit logs must not be deleted through ordinary application operations.
- Foreign-key and deletion policies must prevent cascading deletion from destroying salary or audit history.

## 7. Salary History and Business Rules

The following rules govern salary records and historical corrections:

1. Ordinary salary changes create new salary records rather than overwriting previous salary values.
2. Correcting an existing salary record updates that record and creates an audit entry.
3. Every salary creation and update must generate an audit entry containing the relevant salary values, action, timestamp, and configured HR Manager identity.
4. A reason is required when updating an existing salary record. A reason for initial salary creation is optional.
5. Salary changes and their corresponding audit entries must succeed or fail together within one database transaction.
6. The salary applicable on a given date is the record with the latest `effective_from` date that is on or before the requested date.
7. Future-dated salary changes must not become applicable before their effective dates.
8. Duplicate effective dates for the same employee are rejected.
9. Changing a salary record's effective date must be validated against the uniqueness constraint.
10. Salary records must reference an existing employee.
11. Salary amounts must be positive and use a supported currency and pay frequency.
12. Supported currencies are `INR`, `USD`, `GBP`, `EUR`, `CAD`, and `AUD`.
13. Salary amounts must use fixed-precision decimal handling, and inputs with more than two decimal places must be rejected.
14. Monthly salaries are normalized to annual equivalents by multiplying by 12. Annual salaries remain unchanged.
15. Salaries in different currencies must not be compared directly or combined into a single statistic without a defined currency conversion policy.
16. Corrected salary values must be used in subsequent applicable-salary calculations, while audit history retains evidence of the correction.
17. Audit history must not be modified or deleted through ordinary application operations.

The effective-date lookup must use the latest applicable record rather than simply selecting the most recently created record.

## 8. Compensation Analytics

Compensation analytics will be calculated using persisted employee and salary records. There is no analytics HTTP API yet; the rules below remain the intended behavior.

The backend will support questions such as:

- Employee headcount by country and department.
- Average, median, minimum, and maximum annual salary for a selected group.
- Departments with the highest average salary within a country.
- Salary changes over a selected period.
- Employee counts within annual salary ranges.

Analytics must be calculated from stored records using explicit business rules, not hardcoded results.

### 8.1 Currency Handling

The initial version supports the following currencies:

| Code | Currency |
|---|---|
| `INR` | Indian Rupee |
| `USD` | US Dollar |
| `GBP` | British Pound |
| `EUR` | Euro |
| `CAD` | Canadian Dollar |
| `AUD` | Australian Dollar |

Currency codes will be validated against this supported list.

Salary amounts will remain in their original currencies. Currency conversion is out of scope for the initial version.

Compensation analytics must calculate statistics separately for each currency. Results must identify the currency used, and values from different currencies must not be combined into a single average, median, minimum, maximum, or salary-range calculation.

### 8.2 Salary Standardization

Salary records will preserve their original amounts and pay frequencies. The initial version supports monthly and annual salaries.

For analytics:

- Monthly salaries will be normalized to annual equivalents by multiplying by 12.
- Annual salaries will remain unchanged.
- Normalized annual values will be used for averages, medians, minimums, maximums, and salary-range queries.
- Salary-range boundaries and calculations must use the same currency and annualized units.

Hourly salaries and conversions requiring working-hours assumptions are out of scope.

### 8.3 Reporting Rules

Analytics will use a reporting date to determine which salary record applies to each employee.

- The default reporting date is the current date.
- Users may select another reporting date for historical salary analysis.
- Current active headcount counts employees whose current employment status is `ACTIVE`.
- Analytics include active employees by default.
- The HR Manager may choose to include inactive employees in salary analytics.
- Active headcount must always be displayed separately, regardless of the selected employment-status filter.
- Salary calculations include only employees who satisfy the selected status filter and have an applicable salary record on the reporting date.
- Employees without an applicable salary record are excluded from salary calculations and counted separately.
- Missing salary records must not be treated as zero.
- Future-dated salary records must not affect calculations for reporting dates before their effective dates.
- Salary calculations must be performed separately for each currency.
- The initial version stores current employment status rather than employment-status history. Historical salary queries will use the salary applicable on the requested date but will not reconstruct an employee's historical employment status.
- The reporting date, selected employment-status filter, currency, and other applicable criteria must be explicit in analytics requests and results.

## 9. Database and Migrations

PostgreSQL will store persistent application data.

SQLAlchemy will manage database interactions, while Alembic will track schema changes through versioned migrations.

The design will use:

- PostgreSQL-generated primary keys.
- Foreign key constraints to enforce relationships.
- A unique constraint on employee identifiers.
- A unique constraint on the combination of employee and salary effective date.
- Check constraints for employment status, positive salary amounts, supported currencies, pay frequencies, and audit action values.
- Fixed-precision numeric storage for salary amounts.
- JSONB snapshots for salary audit values.
- A `VARCHAR(100)` field for the configured HR Manager identity, without a foreign key to a users table in the initial version.
- Appropriate indexes for frequently queried fields.
- Transactions for operations that must succeed or fail together.
- Database-level filtering and pagination for employee listings.
- Database constraints and application validation to protect data integrity.
- Employees should ordinarily be deactivated rather than deleted. Salary records must not be deleted through ordinary application operations, and audit history must be preserved. Foreign-key deletion policies must prevent cascading deletion from destroying salary or audit history.
- Indexes will be selected based on expected query patterns, including employee searches, salary effective-date lookups, and audit-history retrieval.
- A development seed script exists at `backend/scripts/seed_dev_data.py`. Default `--count` is **1,000** employees. It uses `DATABASE_URL`, targets database name `acme_salary` only, and refuses `acme_test`. A 10,000-employee seed remains a product requirement, not the current default. Repeatable execution skips existing employee codes.
- The detailed schema, constraints, index selection, deletion policies, and transaction boundaries are documented in `docs/database-design.md`.

## 10. Authentication and Authorization

The initial release supports one configured HR Manager. Multi-user management and additional roles remain out of scope.

The configured audit identity (`HR_MANAGER_IDENTITY`) is not proof of authentication. Login uses a separate username and Argon2 password hash (`HR_MANAGER_USERNAME`, `HR_MANAGER_PASSWORD_HASH`).

### 10.1 Implemented flow

1. `POST /api/v1/auth/login` requires a trusted origin. The backend prefers the `Origin` header. If `Origin` is absent, it derives an origin from `Referer`. A present but invalid `Origin` is not replaced by `Referer`. Configured origins (`CSRF_TRUSTED_ORIGINS`) must be exact HTTP or HTTPS origins with a valid hostname and canonical port. Wildcards and suffix matching are rejected at configuration time.
2. Credentials are checked against the configured username and password hash.
3. On success, the backend inserts a `user_sessions` row containing only the SHA-256 hash of an opaque token (`secrets.token_urlsafe(32)`). The raw token is returned only in the HttpOnly `acme_session` cookie (`Path=/`, `SameSite=Lax`, `Secure` from `SESSION_COOKIE_SECURE`, `Max-Age` from `SESSION_MAX_AGE_SECONDS`, default 28800 seconds). Cookies are set only after the session insert commits.
4. The backend also sets `acme_csrf` (not HttpOnly, same Path/SameSite/Secure/Max-Age). The cookie value is an HMAC token bound to that session id, signed with `CSRF_SIGNING_SECRET` (required `SecretStr`, at least 32 characters, not generated at startup).
5. `require_authenticated_session` reads `acme_session`, hashes it, and accepts the session only if it exists, is unexpired, and is not revoked.
6. `require_csrf_token` runs after authentication. It requires the `acme_csrf` cookie and the `X-CSRF-Token` header to match, and the token signature to bind to the authenticated session. Missing, mismatched, malformed, or cross-session tokens return 403 with a generic message. CSRF does not replace authentication.
7. `POST /api/v1/employees` requires both an authenticated session and a valid CSRF token. Employee GET routes require a session only. `GET /health` is public.
8. `POST /api/v1/auth/logout` requires a session and CSRF token. It sets `revoked_at` on the current session and clears both cookies only after revocation commits.
9. The salaries router (`/api/v1/employees/...`) requires `require_authenticated_session` on all routes. `POST .../salaries` and `PATCH .../salaries/{salary_id}` also use `require_csrf_token`. Salary GET routes (history, as-of, `salary-corrections`) require a session only.

### 10.2 Still pending

- Production trusted origins and `SESSION_COOKIE_SECURE=true` on HTTPS.
- Analytics HTTP protection once those routes exist.

## 11. Testing Strategy

### 11.1 Unit Tests

Test business logic independently, including:

- Employee and salary validation.
- Employment-status validation.
- Salary effective-date selection.
- Duplicate effective-date rejection.
- Salary-history rules.
- Historical correction behavior.
- Audit snapshot generation.
- Currency and pay-frequency validation.
- Decimal precision validation.
- Monthly-to-annual salary normalization.
- Compensation analytics calculations.
- Employment-status filters and active headcount.
- Missing salary records and reporting-date edge cases.

### 11.2 Integration Tests

Test interactions between application components, including:

- Database persistence and constraints.
- Employee API endpoints (create, get, paginated list) and salary API endpoints (create, history, as-of, correction, correction history).
- Pagination, filtering, and error handling.
- Salary changes and historical record retrieval.
- Future-dated salary changes.
- Historical corrections and audit-log persistence.
- Transaction rollback when an audit entry fails.
- Duplicate effective-date rejection at the database level.
- Analytics queries against persisted data (pending analytics implementation).
- Currency-specific analytics and employment-status filtering (pending).
- Preservation of salary and audit history.
- Login, logout, session expiry/revocation, and CSRF cookie/header validation.
- Trusted-origin rejection on login and protected-route 401s without a session.

### 11.3 Frontend Tests

There is no Vitest or React Testing Library suite. `frontend/package.json` defines `lint` and `build` only.

When frontend tests are added, cover important user interactions, including:

- Form validation.
- Employee pagination (and server-side search if added).
- Salary history display.
- Salary correction reason handling.
- Correction history display.
- Analytics filters and results (when analytics exists).
- Loading, empty, and error states.

Backend integration tests derive a connection to `acme_test` from application `DATABASE_URL` (same driver, credentials, host, and port). Test migrations refuse any other database name and do not fall back to `acme_salary`. Ordinary Alembic and FastAPI keep using `DATABASE_URL`.

## 12. Proposed Repository Structure

Current layout (no `repositories` layer):

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
│   ├── scripts/
│   │   └── seed_dev_data.py
│   └── tests/
├── docs/
├── frontend/
│   └── src/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## 13. Development Principles

- Implement features incrementally.
- Keep business rules explicit and independently testable.
- Write tests alongside each feature.
- Review AI-generated code and validate it through tests.
- Use small, meaningful Git commits.
- Document important architectural decisions.
- Avoid introducing dependencies or infrastructure without a clear need.
- Prefer simple solutions until additional complexity is justified by a requirement.

## 14. Architecture Success Criteria

The architecture is successful when:

- Employee and salary records are stored consistently.
- Salary history can be retrieved accurately for a specified date.
- Future-dated salary changes are applied only when effective.
- Historical corrections retain an auditable record of changes.
- Salary creation and update operations generate audit entries.
- Salary changes and audit entries are persisted atomically.
- The configured HR Manager identity is recorded automatically in audit entries.
- Monthly and annual salary records preserve their original values and pay frequencies, subject to authorized audited corrections.
- Annualized salary calculations follow explicit business rules (**analytics not implemented**).
- Salary comparisons respect currency restrictions (**analytics not implemented**).
- Analytics handle reporting dates, employment status, and missing salaries consistently (**pending**).
- API handling, business logic, data access, and frontend responsibilities are separated.
- Core business rules can be tested independently.
- The application can be extended without unnecessary complexity.

## 15. Open Decisions

Settled by the current implementation:

- Session authentication, CSRF double-submit, trusted-origin login checks, and configuration of secrets/origins.
- `get_db` commit/rollback; tests against derived `acme_test` with savepoints.
- Audit snapshots store `amount` (decimal string), `currency`, `pay_frequency`, and `effective_from` (ISO date).
- Employee list pagination uses `limit` (1–100, default 50) and `offset`.

Still open:

1. Analytics HTTP API contracts, server-side employee search/filter, and employee update API.
2. Deployment target and production configuration (`SESSION_COOKIE_SECURE`, real `CSRF_TRUSTED_ORIGINS`).
3. Audit retention and administrative access policy.
4. Whether future versions should support additional salary frequencies or currency conversion.
5. Whether a future version should support bulk salary changes through a shared batch operation with individual audit entries for each affected employee.
6. Growing the development seed from 1,000 to about 10,000 employees, and adding frontend automated tests.

Bulk salary-change workflows are not part of the initial implementation scope. If introduced later, they should support safe retries, progress tracking, and manageable transaction sizes.