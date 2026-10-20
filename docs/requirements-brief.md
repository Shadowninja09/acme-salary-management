# ACME Salary Management — Requirements Brief

This is the assessment-facing one-page brief. Detailed rules live in [`requirements.md`](requirements.md).

## Goal

Build a web application so ACME’s HR Manager can manage employee and salary data for about 10,000 people across multiple countries, and answer how the organization pays people, without maintaining Excel spreadsheets.

## Scope

The first release is a fully functional backend and UI for **one HR Manager**. It covers employee records, salary history, compensation analytics from stored data, a repeatable synthetic seed of about 10,000 employees, automated tests for core behavior, and a deployed demonstration.

Access is backend-enforced session authentication for that single HR Manager, with CSRF protection on state-changing browser requests. The configured audit identity recorded on salary changes is not the same thing as the login username. Multi-user administration and extra roles are out of scope.

## Key features

- Create, view, and update employees (identifier, name, country, department, job title, active/inactive status), with validation, search, filters, and pagination.
- Record salaries (amount, currency, monthly or annual frequency, effective date). Ordinary changes add a new effective date; corrections update an existing date and keep an audit trail.
- Resolve the salary that applies on a chosen date. Future-dated changes do not apply early.
- Analyze compensation from persisted records: consistent currency, monthly amounts annualized by ×12, active employees by default, missing salaries counted separately (not treated as zero).
- Seed about 10,000 synthetic employees and related salaries without using real personal data.

This brief describes the intended first release, including analytics and a seed of about 10,000 employees. Those remain **requirements**, not a claim that they are finished. Current repository progress (implemented versus pending) is recorded in [`requirements.md`](requirements.md) section 9.

## Deliberate exclusions

| Left out | Why |
|---|---|
| Payroll, disbursement, tax, and statutory deductions | Those are payment operations, not salary *records* and analysis. |
| Attendance, leave, recruitment, performance, employee self-service | Different products; they would delay a focused HR Manager tool. |
| External payroll integrations and Excel/CSV import/export | The assessment is a working web system plus seed data, not an Excel replacement pipeline. |
| Natural-language / AI analytics in the product | Analytics must be explicit, testable queries on stored data. |
| Hourly pay and working-hours assumptions | The brief does not require them; they add ambiguous conversion rules. |
| Currency conversion / live exchange rates | Cross-currency totals would be misleading without a defined FX policy. Compare within a currency only. |

These cuts keep the first version understandable, testable, and deployable while still supporting the HR Manager’s job: maintain salaries and explain how the org pays people.

## Supporting documents

- [`requirements.md`](requirements.md) — full specification and acceptance criteria
- [`architecture.md`](architecture.md) — stack and structure
- [`database-design.md`](database-design.md) — schema and integrity rules
- [`delivery-checklist.md`](delivery-checklist.md) — deploy, demo, and submission
