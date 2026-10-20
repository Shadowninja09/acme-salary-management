# ACME Salary Management — Requirements Brief

This is the assessment-facing one-page brief. Detailed rules live in [`requirements.md`](requirements.md).

## Goal

Build a web application so ACME’s HR Manager can manage employee and salary data for about 10,000 people across multiple countries, and answer how the organization pays people, without maintaining Excel spreadsheets.

## Scope

This submission is a backend and UI for **one HR Manager**: employee records (view and paginated list), salary history and corrections, compensation analytics from stored data, a repeatable synthetic seed (local default 1,000; the assessment/demo environment is **intended** to use 10,000), and automated tests for core behavior. **Deployment and a demo video are outstanding release tasks**; they are not done.

Access is backend-enforced session authentication for that single HR Manager, with CSRF protection on state-changing browser requests. The configured audit identity recorded on salary changes is not the same thing as the login username. Multi-user administration and extra roles are out of scope.

## Key features

- View employees (identifier, name, country, department, job title, active/inactive status) with pagination. Create is available on the HTTP API; there is no employee-create or employee-update UI in this submission.
- Directory search and status filters apply to the **currently loaded page only**, which the UI states. They are not dataset-wide.
- Record salaries (amount, currency, monthly or annual frequency, effective date). Ordinary changes add a new effective date; corrections update an existing date, require a reason, and keep an audit trail.
- Resolve the salary that applies on a chosen date (latest `effective_from` on or before that date). Future-dated changes do not apply early. The as-of HTTP API exists; the employee-detail “current compensation” panel uses salary history already loaded in the browser.
- Analyze compensation from persisted records for **active** employees: keep currencies and pay frequencies separate (do not annualize monthly pay by ×12, and do not mix incomparable amounts). Missing salaries are counted separately (not treated as zero).
- Seed synthetic employees and related salaries without using real personal data. Local default is 1,000. The submitted/demo database is intended to use `--count 10000`.

Progress versus remaining release work is recorded in [`requirements.md`](requirements.md) section 9.

## Deliberate exclusions

| Left out | Why |
|---|---|
| Employee update API/UI; employee-create UI | Seed plus view/list is enough to manage salaries on a large dataset; extra HRIS CRUD can wait. |
| Dataset-wide employee search | Pagination already supports browsing 10,000 rows; a search API was not invented without a list-filter contract. |
| Include-inactive analytics; monthly ×12 annualization; medians, pay bands, trends | Mixing inactive staff, monthly with annual, or currencies would misstate pay. Groups stay explicit. |
| Payroll, disbursement, tax, and statutory deductions | Those are payment operations, not salary *records* and analysis. |
| Attendance, leave, recruitment, performance, employee self-service | Different products; they would delay a focused HR Manager tool. |
| External payroll integrations and Excel/CSV import/export | The assessment is a working web system plus seed data, not an Excel replacement pipeline. |
| Natural-language / AI analytics in the product | Analytics must be explicit, testable queries on stored data. |
| Hourly pay and working-hours assumptions | The original assessment does not require them; they add ambiguous conversion rules. |
| Currency conversion / live exchange rates | Cross-currency totals would be misleading without a defined FX policy. |

These cuts keep the submission understandable, testable, and deployable while still supporting the HR Manager’s job: maintain salaries and explain how the org pays people.

## Supporting documents

- [`requirements.md`](requirements.md) — full specification, status, and future enhancements
- [`architecture.md`](architecture.md) — stack and structure
- [`database-design.md`](database-design.md) — schema and integrity rules
- [`delivery-checklist.md`](delivery-checklist.md) — deploy, demo, and submission
