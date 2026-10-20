# ACME Employee Salary Management System

## 1. Goal

Build a web-based application that enables ACME's HR Manager to manage employee information, maintain salary records, and analyze compensation across the organization.

The intended **capacity and demo scale** is approximately 10,000 employees across multiple countries. That is a target for pagination, seeding, and demonstration—not evidence that a 10,000-row database has already been loaded.

## 2. Primary User

**HR Manager**

- The initial release supports one HR Manager user who is responsible for maintaining employee records, managing salary changes, and analyzing compensation patterns.
- Multi-user management and additional roles are outside the initial scope.

## 3. Problem Statement

ACME currently manages employee salary information using Excel spreadsheets. As the organization grows across multiple countries, maintaining consistent records, tracking salary changes, retrieving employee information, and analyzing compensation becomes increasingly difficult.

The application will centralize employee and salary information, preserve historical records, and provide reliable compensation analytics.

## 4. Functional Requirements

### 4.1 Employee Management

- Store employee ID, name, country, department, job title, and employment status (`ACTIVE` or `INACTIVE`).
- Validate required fields and prevent duplicate employee IDs (`employee_code`).
- Support pagination when browsing large employee datasets (`limit` / `offset`).
- Authorized callers may **create** employees through the HTTP API. This submission does **not** include an employee-create UI or an employee-update API/UI.
- The directory UI may filter the **currently loaded page** by text and employment status. That is not dataset-wide search.

### 4.2 Salary Management

- Record salary amount, currency, pay frequency, and effective date for each employee.
- Support monthly and annual salary frequencies in the initial version.
- Allow authorized HR users to record salary changes.
- Preserve previous salary records instead of overwriting salary history.
- Allow authorized HR users to correct existing salary records when previously recorded information is incorrect.
- Ensure each employee has only one salary record for a given effective date.
- Validate salary information before saving it, including positive salary amounts, supported currencies, and valid pay frequencies.
- Validate effective-date changes to prevent duplicate salary records for the same employee and date.
- Identify the salary applicable to an employee on a given date using the latest effective date that is not later than the selected date.
- Preserve the originally recorded salary amount, currency, and pay frequency.
- Support future-dated salary changes without applying them before their effective dates.
- Creating a salary record with a new effective date creates a new record. Correcting an existing salary record updates that record and generates an audit entry.
- The database must enforce the unique constraint on the combination of employee ID and effective date.
- The salary **schema** allow-list is `INR`, `USD`, `GBP`, `EUR`, `CAD`, and `AUD`.
- An **additional application validation policy** (not stated in the original Incubyte brief) further restricts salary currency by the employee’s country. Country names and currency codes are matched after normalizing case and surrounding whitespace. The currently implemented mapping is:

  | Country | Permitted currency |
  |---|---|
  | India | INR |
  | United States | USD |
  | United Kingdom | GBP |
  | Canada | CAD |
  | Australia | AUD |
  | Germany | EUR |

  This is the configured policy, not a claim that every country or currency is supported. Countries outside this list have no salary currency policy: salary **create** is rejected. Salary **correction** validates the combination when the currency **changes**; a correction may **retain** a legacy currency already stored on that salary. The backend rejects unsupported combinations with HTTP 422. The frontend limits salary currency options to the employee’s country (and may still offer a recorded legacy code on correction). The same mapping is used when generating seed salaries. Employee **country** itself is not validated against this list.

### 4.3 Salary Audit History

- Record an audit entry for every salary creation and update.
- Include the action, salary values before and after the change, responsible user, timestamp, and applicable reason in each audit entry.
- Require a reason when updating an existing salary record. A reason for initial salary creation may be optional.
- Save salary changes and their corresponding audit entries in the same database transaction.
- Roll back a salary change if its corresponding audit entry cannot be saved.
- Prevent audit history from being edited or deleted through ordinary application operations.
- The backend automatically records the configured HR Manager identity for every salary audit event. The frontend must not supply or determine the audit identity.
- The correction-history HTTP/UI list returns **UPDATE** audits only. CREATE audits remain in the database and are not shown on that list.


### 4.4 Compensation Analytics

- Compensation analytics include **active** employees only. There is no include-inactive control in this submission.
- Active headcount is displayed separately from counts of active employees with and without an applicable salary.
- Salary calculations include only active employees who have an applicable salary record for the selected reporting date.
- Employees without an applicable salary record are excluded from salary calculations and counted separately. Missing salary records must not be treated as zero.
- Salary selection uses the latest effective date that is not later than the reporting date. Future-dated salary changes must not affect earlier reporting dates.
- Only current employment status is stored. Historical salary reports must not imply that historical employment status is known.
- Do **not** annualize monthly salaries by multiplying by 12. Keep monthly and annual amounts in separate groups.
- Salaries in different currencies must not be directly compared or combined. Currency conversion is out of scope.
- Analytics must use stored employee and salary records rather than hardcoded results.
- Each analytical query must define how employment status, missing salary records, and the reporting date affect its calculations.
- Reports must make currency, pay frequency, and the reporting date explicit.

### 4.5 Data Seeding

- Provide a repeatable seed script of synthetic employees and associated salary data (no real personal data). Seeded salaries use the country–currency allow-list in section 4.2.
- Local default `--count` is **1,000** for safer development. The assessment/demo environment is intended to be seeded with **10,000** (`--count 10000`). Do not claim a 10,000-row database exists until that run is recorded.
- Repeated execution must not unintentionally duplicate employee codes.
- Document how to run the script.

### 4.6 Access Control

- The initial release supports one configured HR Manager.
- Employee and salary operations must be protected against unauthorized access.
- The backend must enforce access control rather than relying only on frontend visibility.
- Authentication is session-based. The HR Manager signs in with a configured username and password. The backend issues an opaque session token and persists only the SHA-256 hash of that token. The raw token is not stored.
- Sessions expire after a configured lifetime and can be revoked on logout. Expired or revoked sessions must not authorize further requests.
- The session cookie is HttpOnly. State-changing browser requests must also present a valid CSRF token bound to the authenticated session (cookie plus matching request header). CSRF protection does not replace authentication.
- Login has no session yet, so login requests must come from a configured trusted origin (`Origin`, or `Referer` only when `Origin` is absent). Arbitrary origins must not be trusted.
- Passwords are stored only as Argon2 encoded hashes. Session signing material, CSRF signing secrets, trusted origins, and other sensitive configuration must remain outside source control.
- The backend automatically assigns the configured HR Manager identity (`HR_MANAGER_IDENTITY`) to salary audit events. That identity is audit attribution. It is distinct from the login username and is not independently derived from an authenticated user row.
- Multi-user management and additional roles are out of scope for the initial release.

## 5. Non-Functional Requirements

### 5.1 Maintainability

- Code must be readable, modular, and easy to extend.
- Business logic, data access, API handling, and frontend responsibilities must be clearly separated.

### 5.2 Performance

- The application is designed so a **demo-scale** dataset of approximately 10,000 employees can be listed without loading the entire dataset into the frontend. That is a design target, not a recorded benchmark or a claim that 10,000 rows are already seeded.
- Employee listing must use pagination so the frontend does not load the entire dataset. Directory search in this submission is page-local, not a server-side dataset query.
- Analytics must use appropriate database queries and avoid unnecessary retrieval of entire datasets into application memory.

### 5.3 Reliability and Data Integrity

- Employee and salary records must follow defined validation rules.
- Salary history must be preserved when compensation changes.
- Salary effective dates must be handled consistently.
- Analytics must produce consistent results for the same dataset and query criteria.
- Operations involving related data changes must maintain database consistency.

### 5.4 Testing

- Include meaningful unit tests covering core business logic and validation.
- Tests must be fast, deterministic, and easy to understand.
- Tests should be independent where practical and must not rely on external services for ordinary unit-test execution.
- Include integration tests for important database and API behavior.

### 5.5 Security

- Employee and salary information must be accessible only to authorized users.
- Sensitive configuration and credentials must not be committed to source control.
- The backend must enforce session authentication for protected operations and CSRF validation for authenticated state-changing browser requests.

### 5.6 Documentation

- Provide instructions for setting up and running the application.
- Document how to execute tests and seed the database.
- Include deployment instructions once a target is chosen and the steps have been run.
- Document important business rules and unresolved design decisions.

## 6. Out of Scope

The initial version will not include:

- Payroll processing or salary disbursement.
- Tax calculations or statutory deductions.
- Attendance, leave, or holiday management.
- Recruitment or performance management.
- Employee self-service portals.
- External payroll integrations.
- Excel/CSV import and export.
- AI-powered natural-language analytics.
- Hourly salary records or conversions requiring working-hours assumptions.
- Currency conversion using external exchange rates.
- Employee-update API/UI, employee-create UI, dataset-wide search, include-inactive analytics, monthly ×12 annualization, and extra analytics (median, pay bands, trends). See section 10.

These features are excluded or deferred to keep this submission focused on employee information, salary history, and honest compensation grouping.

## 7. Acceptance Criteria

The application will be considered functionally complete for **this submission** when:

1. Authorized HR users can view employees and list them with pagination. Create is available on the HTTP API (no create/update UI required).
2. The directory can page through a large seeded dataset. Any search/status filter is page-local and labeled as such.
3. Duplicate employee IDs and invalid employee or salary data are rejected.
4. Salary changes preserve historical records and effective dates.
5. The system can identify the applicable salary for a specified date (HTTP as-of). The employee-detail current-pay panel may derive that from loaded history rather than calling as-of.
6. Monthly and annual salary records preserve their original amounts and pay frequencies.
7. Compensation analytics calculate results from stored data using the defined business rules.
8. Salary analytics keep currency and pay frequency separate (no ×12 annualization, no FX mix).
9. Analytics apply explicit rules for reporting dates, **active** employment status, and missing salary records.
10. The seed script can populate about 10,000 synthetic employees (`--count 10000`). Local default remains 1,000 until the demo database is seeded at 10,000.
11. Core functionality is covered by meaningful, fast, deterministic tests (backend pytest; frontend Vitest for a small high-value set).
12. The project includes setup, testing, and seeding documentation. Deployment documentation is complete once deploy steps have been run.
13. Every salary creation and update generates an audit entry (action, before/after values, responsible user, timestamp, reason where applicable). The correction-history UI lists **UPDATE** audits only.
14. Salary changes and their corresponding audit entries are committed in the same database transaction. If audit logging fails, the salary change is rolled back.
15. Authorized HR users can correct an existing salary record without creating duplicate records for the same employee and effective date.
16. Compensation analytics include active employees only and display active headcount separately from with-salary / without-salary counts.
17. Employees without an applicable salary record are counted separately and excluded from salary calculations.
18. Future-dated salary changes do not affect analytics for reporting dates before their effective dates.
19. Only an authenticated HR Manager session can access protected employee, salary, and analytics operations.
20. Login issues a session cookie and a session-bound CSRF cookie only after trusted-origin checks and successful credential verification. Logout requires a valid session and CSRF token, revokes the current session, and clears both cookies.
21. Credentials, the CSRF signing secret, and trusted origins are supplied through configuration rather than committed source.

Progress against these criteria, including unfinished **release** work (deploy, 10,000-employee demo seed, demo video), is recorded in section 9.

## 8. Success Criteria

The HR Manager can securely manage employee and salary information in one application, review historical compensation changes, and answer common organizational compensation questions without relying on manually maintained spreadsheets.

The solution must remain understandable, testable, and maintainable as the dataset and business requirements grow.

## 9. Current implementation status

This section records the repository against the submission scope above.

**Implemented (product)**

- Employee persistence and HTTP APIs to **create**, fetch by id, and **list** employees with pagination (`limit`/`offset`). Session required; create also requires CSRF. There is **no** employee update (PATCH/PUT) API and **no** employee-create UI.
- Salary HTTP APIs (session required). Create and correction also require CSRF (`acme_csrf` cookie plus `X-CSRF-Token`):
  - `POST /api/v1/employees/{employee_id}/salaries` — create a salary for a new effective date. Country–currency allow-list validation always runs; unsupported combinations return HTTP 422.
  - `GET /api/v1/employees/{employee_id}/salaries` — salary history, newest `effective_from` first.
  - `GET /api/v1/employees/{employee_id}/salaries/as-of?date=YYYY-MM-DD` — applicable salary on or before that date, or `null`.
  - `PATCH /api/v1/employees/{employee_id}/salaries/{salary_id}` — correct an existing row (non-blank reason). Updates the same record and writes an UPDATE audit. Keeping that row’s `effective_from` succeeds; moving onto another of the same employee’s dates returns 409. Country–currency validation runs when the currency **changes**; a correction may retain a legacy currency. Tests that encode date cases include `test_correct_salary_keeps_existing_effective_date` and `test_correct_salary_duplicate_effective_date_returns_409`. This status section does not record a test run.
  - `GET /api/v1/employees/{employee_id}/salary-corrections` — **UPDATE** audit rows only (newest `changed_at` first). CREATE audits are not returned.
  - `GET /api/v1/analytics/compensation?date=YYYY-MM-DD` — **active-employee** analytics (session required; GET has no CSRF header). Groups by currency and pay frequency. Does not convert currency or mix monthly with annual amounts.
- React + TypeScript + Vite UI: login and logout; paginated directory with **page-local** search/status filter (labeled “Search this page”); employee details; add/correct salary; salary history; UPDATE-only correction history; compensation analytics (reporting date, active headcount, salary groups). Employee-detail “current compensation” is computed from loaded history, not from the as-of endpoint. Vite proxies `/api` to FastAPI in development. After a successful salary POST or PATCH, a later history-refresh failure is shown as stale lists, not as a failed write. A **401** from a protected API request returns the UI to login. A login **401** remains invalid credentials. HTTP **403** and network failures do not automatically clear the session.
- One configured HR Manager: HttpOnly `acme_session`, session-bound `acme_csrf`, trusted-origin login, logout revocation.
- Repeatable seed (`backend/scripts/seed_dev_data.py`): default **1,000** on `acme_salary` only; refuses `acme_test`; `--count 10000` is supported. A 10,000-row **database** is not claimed until that seed is run and recorded.
- `GET /health` is public.
- Backend tests against derived `acme_test` (savepoint isolation). Frontend Vitest is **committed** (`npm test` / `vitest run` in `frontend/package.json`, plus `npm run lint` and `npm run build`). This section does not claim those commands were re-run after the implementation commits.

**Remaining release tasks (not product-scope changes)**

- Seed the assessment/demo database with 10,000 employees.
- Deployment, production `SESSION_COOKIE_SECURE` / trusted origins, and a recorded demo.
- Document verified migrate/run commands in the README after those commands have been executed successfully.

## 10. Future enhancements

Not in this submission (unless already implemented above):

- Employee-update API/UI and employee-create UI.
- Dataset-wide (server-side) employee search and filter.
- Include-inactive analytics.
- Calling the as-of endpoint from the current-compensation UI.
- Medians, pay bands, trend reports, and monthly ×12 annualization.
- CSV export, currency conversion, payroll, tax, attendance, and natural-language analytics.
