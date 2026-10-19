# Database Design — ACME Salary Management System

## 1. Overview

The ACME Salary Management System uses PostgreSQL as its relational database. The database is designed to manage employee information, maintain salary history, record salary changes, and support compensation analytics.

The initial release supports approximately 10,000 employees and one configured HR Manager identity.

The database design prioritizes data integrity, historical accuracy, auditability, and maintainability.

### Core Tables

The database currently contains four tables (Alembic revisions `0001`–`0004`):

1. `employees` — stores employee information and current employment status.
2. `salary_records` — stores salary amounts, currencies, pay frequencies, and effective dates.
3. `salary_audit_logs` — records salary creation and update events.
4. `user_sessions` — stores hashed opaque session tokens for the configured HR Manager.

## 2. Entity Relationships

- One employee can have multiple salary records.
- Each salary record belongs to one employee.
- One salary record can have multiple audit log entries.
- Each audit entry belongs to one salary record.

Relationships:

- `salary_records.employee_id` references `employees.id`.
- `salary_audit_logs.salary_record_id` references `salary_records.id`.
- `user_sessions` has no foreign key to a users table. The application authenticates a single configured HR Manager; session rows are not linked to a user record.

## 3. Employees Table

**Table name:** `employees`

Stores employee profile information and their current employment status.

| Column | PostgreSQL Type | Constraints |
|---|---|---|
| `id` | `BIGINT` | Primary key, generated automatically |
| `employee_code` | `VARCHAR(20)` | Unique, not null |
| `full_name` | `VARCHAR(150)` | Not null |
| `country` | `VARCHAR(100)` | Not null |
| `department` | `VARCHAR(100)` | Not null |
| `job_title` | `VARCHAR(150)` | Not null |
| `employment_status` | `VARCHAR(10)` | Not null, restricted to `ACTIVE` or `INACTIVE` |
| `created_at` | `TIMESTAMPTZ` | Not null |
| `updated_at` | `TIMESTAMPTZ` | Not null |

### Rules

- `id` is the internal database identifier.
- `employee_code` is the business identifier, such as `EMP-000001`.
- Employee codes must be unique.
- Required employee fields cannot be null.
- Employment status must be either `ACTIVE` or `INACTIVE`.
- Employees who leave the organization are marked inactive instead of being deleted.
- Country, department, and job title are stored as text in the initial version. Separate lookup tables may be introduced if future requirements justify them.

## 4. Salary Records Table

**Table name:** `salary_records`

Stores employee salary information, including historical records and future-dated salary changes.

| Column | PostgreSQL Type | Constraints |
|---|---|---|
| `id` | `BIGINT` | Primary key, generated automatically |
| `employee_id` | `BIGINT` | Foreign key to `employees.id`, not null |
| `amount` | `NUMERIC(12,2)` | Not null, greater than zero |
| `currency` | `VARCHAR(3)` | Not null, restricted to supported currencies |
| `pay_frequency` | `VARCHAR(10)` | Not null, restricted to `MONTHLY` or `ANNUAL` |
| `effective_from` | `DATE` | Not null |
| `created_at` | `TIMESTAMPTZ` | Not null |
| `updated_at` | `TIMESTAMPTZ` | Not null |

### Constraints

- Every salary record must reference an existing employee.
- The combination of `employee_id` and `effective_from` must be unique.
- Salary amounts must be greater than zero.
- Supported currencies are `INR`, `USD`, `GBP`, `EUR`, `CAD`, and `AUD`.
- Pay frequency must be `MONTHLY` or `ANNUAL`.
- Database constraints must enforce the applicable currency, frequency, and amount restrictions.

### Salary History Rules

- Creating a salary record establishes salary information for its effective date.
- A new salary change with a different effective date creates a new salary record.
- Correcting an existing salary record updates that record and creates an audit entry.
- A future-dated salary record is allowed but must not apply before its effective date.
- An employee cannot have multiple salary records with the same effective date.

### Determining the Applicable Salary

To determine an employee's salary on a reporting date, select the salary record with the latest `effective_from` date that is less than or equal to the reporting date.

If no such record exists, the employee has no applicable salary for that date.

The database must not rely on an `is_current` flag because salary applicability depends on the reporting date.

### Decimal Precision

- Salary amounts use PostgreSQL `NUMERIC(12,2)`.
- The Python application uses `Decimal`, not floating-point values, for salary calculations.
- Inputs with more than two decimal places are rejected rather than silently rounded.
- Salary validation must be applied at the API and service layers, with database constraints enforcing essential integrity rules.

## 5. Salary Audit Logs Table

**Table name:** `salary_audit_logs`

Stores the history of salary creation and update operations.

| Column | PostgreSQL Type | Constraints |
|---|---|---|
| `id` | `BIGINT` | Primary key, generated automatically |
| `salary_record_id` | `BIGINT` | Foreign key to `salary_records.id`, not null |
| `action` | `VARCHAR(10)` | Not null, restricted to `CREATE` or `UPDATE` |
| `old_values` | `JSONB` | Nullable for creation events |
| `new_values` | `JSONB` | Not null |
| `reason` | `TEXT` | Optional for creation; required for updates |
| `changed_by` | `VARCHAR(100)` | Not null |
| `changed_at` | `TIMESTAMPTZ` | Not null |

### Audit Identity

The initial release supports one configured HR Manager identity (`HR_MANAGER_IDENTITY`).

- The backend automatically assigns that configured identity to each audit event (`changed_by`).
- The frontend must not supply the audit identity.
- A separate `users` table is not included in the initial database schema.
- Authentication exists as database-backed sessions for the configured login username. `changed_by` is still the configured audit identity, not a value loaded from an authenticated user row.
- Session authentication proves that a valid HR Manager session performed the request. It does not replace the configured audit identity field.

### Audit Snapshot

The `old_values` and `new_values` fields capture the salary values relevant to the operation:

- `amount`
- `currency`
- `pay_frequency`
- `effective_from`

Salary amounts in JSON snapshots should be represented as decimal strings to avoid ambiguity about numeric precision.

For a `CREATE` event, `old_values` is null.

For an `UPDATE` event, `old_values` contains the values before the change, and `new_values` contains the updated values.

### Audit Rules

- Every salary creation and update must produce an audit entry.
- An update must include a non-empty reason.
- Creation reasons are optional.
- Salary changes and their corresponding audit entries must be committed in the same database transaction.
- If audit creation fails, the salary change must be rolled back.
- Ordinary application operations must not allow audit entries to be edited or deleted.
- Foreign-key and deletion behavior must preserve audit history.
- There is no database privilege or trigger that makes `salary_audit_logs` immutable. Preservation is an application rule plus `ON DELETE RESTRICT` on the salary-record foreign key.

## 6. User Sessions Table

**Table name:** `user_sessions`

Stores hashed session tokens for the configured HR Manager. Implemented in migration `0004_create_user_sessions`.

| Column | PostgreSQL Type | Constraints |
|---|---|---|
| `id` | `BIGINT` | Primary key, generated automatically (`IDENTITY`) |
| `token_hash` | `VARCHAR(64)` | Unique, not null (SHA-256 hex digest of the raw token) |
| `created_at` | `TIMESTAMPTZ` | Not null, server default `now()` |
| `expires_at` | `TIMESTAMPTZ` | Not null |
| `revoked_at` | `TIMESTAMPTZ` | Nullable; set when the session is revoked |

### Session rules

- The raw session token is issued to the browser as the HttpOnly `acme_session` cookie. Only `token_hash` is persisted.
- A session is usable only when `revoked_at` is null and `expires_at` is still in the future.
- Logout sets `revoked_at`. It does not delete the row.
- CSRF tokens are not stored in this table. They are signed cookies bound to `user_sessions.id`.

## 7. Relationships and Deletion Policy

| Relationship | Rule |
|---|---|
| Employee to salary records | One-to-many |
| Salary record to audit logs | One-to-many |
| Employee deletion | Prevent deletion when salary history exists; use inactive status instead |
| Salary record deletion | Not allowed through ordinary application operations |
| Audit log modification | Not allowed through ordinary application operations |
| Audit log deletion | Not allowed through ordinary application operations |

Foreign keys use `ON DELETE RESTRICT` (`fk_salary_records_employee_id`, `fk_salary_audit_logs_salary_record_id`). They must not use cascading deletion in a way that removes salary or audit history.

## 8. Compensation Analytics Rules

The following reporting rules are intended for compensation analytics. There is no analytics query API yet. Salary applicability is implemented in the salary service (`get_applicable_salary`).

The database supports the following reporting rules:

- Active employees are included by default.
- Reports may include inactive employees when requested.
- Active headcount is reported separately from the number of employees with applicable salary data.
- Employees without an applicable salary are counted separately and excluded from salary statistics.
- Monthly salaries are annualized by multiplying by 12.
- Annual salaries are used without frequency conversion.
- Salaries in different currencies are analyzed separately.
- Currency conversion is outside the initial scope.
- Reports use the salary record applicable on the requested reporting date.
- Future-dated salary changes must not affect earlier reports.
- Historical employment status cannot be reconstructed because only the current employment status is stored.

## 9. Indexes and Query Performance

The following indexes exist in the current migrations (unique constraints create unique indexes in PostgreSQL):

- Unique constraint `uq_employees_employee_code` on `employees.employee_code`.
- Unique constraint `uq_salary_records_employee_id_effective_from` on `salary_records(employee_id, effective_from)`.
- Unique constraint `uq_user_sessions_token_hash` on `user_sessions.token_hash`.
- Index `ix_salary_audit_logs_salary_record_id` on `salary_audit_logs.salary_record_id`.

No additional search or analytics indexes have been added. Further indexes should follow actual query patterns and query-plan analysis.

The initial database is designed for approximately 10,000 employees. Performance has not been measured against a seeded dataset.

## 10. Data Seeding

A repeatable seed script is still planned. It is not in the repository yet. When added, it will generate approximately 10,000 synthetic employee records and associated salary records.

Requirements:

- Use synthetic data only.
- Avoid real employee information.
- Make repeated execution safe and prevent duplicate seed records.
- Generate valid employee, salary, currency, frequency, and effective-date values.
- Ensure seeded data supports testing of active and inactive employees, salary history, future-dated changes, and missing salary information.

## 11. Database Migrations

Alembic manages database schema changes. Current revisions:

| Revision | Table |
|---|---|
| `0001_create_employees` | `employees` |
| `0002_create_salary_records` | `salary_records` |
| `0003_create_salary_audit_logs` | `salary_audit_logs` |
| `0004_create_user_sessions` | `user_sessions` |

- Schema changes must remain version-controlled through migrations.
- Migrations must be reviewable and reproducible.
- The application must not depend on manually created production schema changes.
- Database initialization and migration instructions must be documented.

## 12. Database Testing

Database-related tests must cover:

- Employee-code uniqueness.
- Required employee fields and valid employment status.
- Salary amount, currency, and frequency validation.
- Duplicate employee/effective-date rejection.
- Salary selection by reporting date.
- Future-dated salary behavior.
- Salary audit creation for create and update operations.
- Required update reasons.
- Transaction rollback when audit creation fails.
- Preservation of salary and audit history.
- Safe, repeatable seed-script execution (pending; the script does not exist yet).
- Compensation analytics for missing salaries, employment status, frequency, and currencies (pending HTTP/analytics implementation).
- Session token hashing (raw token not persisted), expiry, and revocation.
- CSRF binding to the authenticated session.

Tests must be deterministic. Persistence tests use `TEST_DATABASE_URL` (dedicated `acme_test` database) and wrap each test in a connection-level transaction with savepoints so commits do not leak into other tests. Application `get_db` commits after a successful request. Login and logout use function-scoped sessions so the session row is committed before cookies are set or cleared.

## 13. Initial Scope and Future Extensions

The initial schema intentionally avoids unnecessary complexity:

- No separate users table (sessions are not tied to a user row).
- No role-management system.
- No country, department, or job-title lookup tables.
- No currency conversion tables.
- No historical employment-status table.
- No bulk salary-change tracking.

These can be introduced through future migrations if business requirements change.

## 14. Open Decisions

Settled by the current implementation:

- Single HR Manager authentication via opaque hashed sessions, cookies, CSRF, and trusted-origin login checks.
- Persistence tests against `TEST_DATABASE_URL`; request-scoped commit in `get_db`.

Still open:

1. Salary and analytics HTTP API contracts, employee search/filter conventions, and remaining pagination details beyond the current employee `limit`/`offset` list.
2. Deployment target and production configuration (HTTPS, `SESSION_COOKIE_SECURE`, real trusted origins).
3. Audit retention and administrative access policy.
4. Whether future releases need additional pay frequencies, currency conversion, or bulk salary operations.
