# ACME Employee Salary Management System

## 1. Goal

Build a web-based application that enables ACME's HR Manager to manage employee information, maintain salary records, and analyze compensation across the organization.

The system must support approximately 10,000 employees across multiple countries and provide reliable answers to common compensation-related business questions.

## 2. Primary User

**HR Manager**

- The initial release supports one HR Manager user who is responsible for maintaining employee records, managing salary changes, and analyzing compensation patterns.
- Multi-user management and additional roles are outside the initial scope.

## 3. Problem Statement

ACME currently manages employee salary information using Excel spreadsheets. As the organization grows across multiple countries, maintaining consistent records, tracking salary changes, retrieving employee information, and analyzing compensation becomes increasingly difficult.

The application will centralize employee and salary information, preserve historical records, and provide reliable compensation analytics.

## 4. Functional Requirements

### 4.1 Employee Management

- Create, view, and update employee records.
- Store employee ID, name, country, department, job title, and employment status.
- Validate required fields and prevent duplicate employee IDs.
- Search and filter employees by relevant attributes.
- Support pagination when browsing large employee datasets.
- Employment status must be limited to `ACTIVE` and `INACTIVE` in the initial version.

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
- The initial supported currencies are `INR`, `USD`, `GBP`, `EUR`, `CAD`, and `AUD`.

### 4.3 Salary Audit History

- Record an audit entry for every salary creation and update.
- Include the action, salary values before and after the change, responsible user, timestamp, and applicable reason in each audit entry.
- Require a reason when updating an existing salary record. A reason for initial salary creation may be optional.
- Save salary changes and their corresponding audit entries in the same database transaction.
- Roll back a salary change if its corresponding audit entry cannot be saved.
- Prevent audit history from being edited or deleted through ordinary application operations.
- The backend automatically records the configured HR Manager identity for every salary audit event. The frontend must not supply or determine the audit identity.


### 4.4 Compensation Analytics

- Compensation analytics must include active employees by default, with an option to include inactive employees.
- The active employee headcount must always be displayed separately, regardless of the selected employment status filter.
- Salary calculations must include only employees who have an applicable salary record for the selected reporting date and satisfy the selected employment status filter.
- Employees without an applicable salary record must be excluded from salary calculations and counted separately. Missing salary records must not be treated as zero.
- Salary selection must use the latest effective date that is not later than the reporting date. Future-dated salary changes must not affect earlier reporting dates.
- Only current employment status is stored in the initial version. Historical salary reports must not imply that historical employment status is known.
- Salary comparisons must use a consistent currency and normalized annual salary amounts.
- Monthly salaries must be converted to annual equivalents using a factor of 12. Annual salaries remain unchanged.
- Salaries in different currencies must not be directly compared or combined without a defined currency conversion policy.
- Currency conversion is out of scope for the initial version.
- Analytics must use stored employee and salary records rather than hardcoded results.
- Each analytical query must define how employment status, missing salary records, and the reporting date affect its calculations.
- Salary ranges must be evaluated using normalized annual salary amounts and a consistent currency.
- Reports must make the selected currency and applicable reporting criteria explicit.
- Active headcount represents employees whose current employment status is `ACTIVE`, regardless of whether the report includes inactive employees in its salary analysis.

### 4.5 Data Seeding

- Provide a repeatable seed script that generates approximately 10,000 synthetic employee records and associated salary data.
- Generate realistic, internally consistent data suitable for testing employee management, salary history, and analytics.
- Avoid using real employee information or confidential salary data.
- Document how to run the seed script.
- Ensure repeated execution does not unintentionally create duplicate records.

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

- The application must support approximately 10,000 employee records without loading the entire dataset into the frontend.
- Employee listing and search operations must use pagination and appropriate query strategies.
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
- Include deployment instructions.
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

These features are excluded to keep the initial implementation focused on employee information, salary history, and reliable compensation analytics.

## 7. Acceptance Criteria

The application will be considered functionally complete when:

1. Authorized HR users can create, view, and update employee records.
2. Employee records can be searched and filtered across the seeded dataset using pagination.
3. Duplicate employee IDs and invalid employee or salary data are rejected.
4. Salary changes preserve historical records and effective dates.
5. The system can identify the applicable salary for a specified date.
6. Monthly and annual salary records preserve their original amounts and pay frequencies.
7. Compensation analytics calculate results from stored data using the defined business rules.
8. Salary comparisons normalize monthly amounts to annual equivalents and respect currency restrictions.
9. Analytics apply explicit rules for reporting dates, employment status, and missing salary records.
10. The seed script can populate the application with approximately 10,000 synthetic employees and associated salary records.
11. Core functionality is covered by meaningful, fast, deterministic unit tests.
12. The project includes setup, testing, seeding, and deployment documentation.
13. Every salary creation and update generates an audit entry containing the action, relevant salary values before and after the change, responsible user, timestamp, and applicable reason.
14. Salary changes and their corresponding audit entries are committed in the same database transaction. If audit logging fails, the salary change is rolled back.
15. Authorized HR users can correct an existing salary record without creating duplicate records for the same employee and effective date.
16. Compensation analytics include active employees by default, allow inactive employees to be included, and display active headcount separately.
17. Employees without an applicable salary record are counted separately and excluded from salary calculations.
18. Future-dated salary changes do not affect analytics for reporting dates before their effective dates.
19. Only an authenticated HR Manager session can access protected employee and salary operations.
20. Login issues a session cookie and a session-bound CSRF cookie only after trusted-origin checks and successful credential verification. Logout requires a valid session and CSRF token, revokes the current session, and clears both cookies.
21. Credentials, the CSRF signing secret, and trusted origins are supplied through configuration rather than committed source.

These criteria describe the intended complete deliverable. Progress against them is recorded in section 9; several criteria remain pending.

## 8. Success Criteria

The HR Manager can securely manage employee and salary information in one application, review historical compensation changes, and answer common organizational compensation questions without relying on manually maintained spreadsheets.

The solution must remain understandable, testable, and maintainable as the dataset and business requirements grow.

## 9. Current implementation status

This section records progress against the requirements above. It does not replace those requirements.

**Implemented**

- Employee persistence and HTTP APIs to create, fetch by id, and list employees with pagination (`limit`/`offset`). Protected by session authentication. Create also requires CSRF validation. There is no employee update (PATCH/PUT) API.
- Salary HTTP APIs (session required). Create and correction also require CSRF (`acme_csrf` cookie plus `X-CSRF-Token`):
  - `POST /api/v1/employees/{employee_id}/salaries` — create a salary for a new effective date.
  - `GET /api/v1/employees/{employee_id}/salaries` — salary history, newest `effective_from` first.
  - `GET /api/v1/employees/{employee_id}/salaries/as-of?date=YYYY-MM-DD` — applicable salary on or before that date, or `null`.
  - `PATCH /api/v1/employees/{employee_id}/salaries/{salary_id}` — correct an existing row (non-blank reason). Updates the same record and writes an UPDATE audit entry. A correction that keeps that row’s existing `effective_from` succeeds. Moving the date onto another of the same employee’s dates returns 409. Automated tests cover both cases (`test_correct_salary_keeps_existing_effective_date`, `test_correct_salary_duplicate_effective_date_returns_409`).
  - `GET /api/v1/employees/{employee_id}/salary-corrections` — UPDATE audit rows only (newest `changed_at` first). CREATE audits are not returned. No extra CSRF header.
- Salary persistence, create/correct services, applicable-salary lookup, and audit logging in the same database transaction as the salary change.
- React + TypeScript + Vite frontend: HR Manager login and logout; employee directory with pagination; client-side search/status filter on the **currently loaded page** (not a backend search API); employee details; add salary; correct salary; salary history; correction-history table. After a successful correction, the UI refreshes both lists and closes the correction form. The Vite dev server proxies `/api` to the FastAPI process so session cookies work locally.
- One configured HR Manager: login and logout, opaque `acme_session` cookie (HttpOnly, SameSite=Lax, configured Secure and max-age), SHA-256 hashed sessions in `user_sessions`, expiry and revocation.
- Session-bound CSRF cookie `acme_csrf` (readable by JavaScript) plus `X-CSRF-Token` on state-changing authenticated requests. The frontend copies that cookie into the header for POST and PATCH except login. Trusted-origin validation on login.
- Repeatable development seed (`backend/scripts/seed_dev_data.py`): default **1,000** synthetic employees on `acme_salary` only; refuses `acme_test`. Not a 10,000-employee seed.
- Health check `GET /health` remains public.
- Backend tests against a dedicated `TEST_DATABASE_URL` database, isolated with savepoints. Frontend `npm run lint` and `npm run build` exist; there is no Vitest/React Testing Library suite.

**Not yet implemented**

- Employee update API.
- Server-side employee search and filter APIs (directory filtering is page-local).
- Compensation analytics APIs and UI.
- Repeatable ~10,000-employee seed (requirement remains; current default is 1,000).
- Frontend automated tests.
- Deployment, production `SESSION_COOKIE_SECURE` / trusted origins, and a recorded demo.
