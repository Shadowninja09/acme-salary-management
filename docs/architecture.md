# ACME Employee Salary Management System — Architecture

## 1. Purpose

This document describes the technical architecture for the ACME Employee Salary Management System.

The application will allow authorized HR users to manage employee information, maintain salary history, and analyze compensation across approximately 10,000 employees in multiple countries.

The architecture prioritizes maintainability, testability, data integrity, and clear separation of responsibilities.

## 2. Technology Stack

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | React.js | User interface and user interactions |
| Frontend build tool | Vite | Frontend development and production builds |
| Backend API | FastAPI | HTTP endpoints and request handling |
| Request/response validation | Pydantic | Validate API inputs and outputs |
| ORM | SQLAlchemy | Database access and object-relational mapping |
| Database migrations | Alembic | Version and apply database schema changes |
| Database | PostgreSQL | Persistent employee and salary data |
| Backend testing | pytest | Unit and integration tests |
| API testing | FastAPI TestClient | Test HTTP endpoints |
| Frontend testing | Vitest and React Testing Library | Test frontend behavior |
| Version control | Git and GitHub | Track and review changes |

## 3. High-Level Architecture

The application will follow a client-server architecture.

```text
+----------------------------------+
|          React Frontend          |
|                                  |
| Employee Management              |
| Salary Management                |
| Compensation Analytics           |
+----------------+-----------------+
                 |
                 | HTTP / JSON
                 v
+----------------------------------+
|          FastAPI Backend         |
|                                  |
| API Routes                       |
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
| Salary History                   |
| Salary Audit Logs                |
+----------------------------------+
```

The frontend will communicate with the backend through REST APIs. The backend will validate requests, execute business rules, access the database, and return structured responses.

The frontend will not access PostgreSQL directly.

## 4. Backend Architecture

The backend will use a layered structure to keep HTTP handling, business logic, and database operations separate.

### 4.1 API Layer

Responsibilities:

- Define REST API endpoints.
- Accept and validate incoming requests.
- Invoke the appropriate business services.
- Return structured responses and appropriate HTTP status codes.
- Apply authentication and authorization requirements.

API routes should not contain complex salary calculations or database business rules.

### 4.2 Service Layer

Responsibilities:

- Implement employee and salary management use cases.
- Enforce salary-history rules.
- Determine the applicable salary for a given date.
- Normalize monthly and annual salaries for analytics.
- Apply compensation rules to analytics.
- Coordinate database operations when a business operation involves multiple records.
- Ensure salary corrections and their audit entries are persisted atomically.

Business rules should be testable independently of HTTP request handling.

### 4.3 Data Access Layer

Responsibilities:

- Perform database queries using SQLAlchemy.
- Create, retrieve, and update persisted records.
- Support filtering, pagination, and analytics queries.
- Keep database access details separate from business services where practical.

### 4.4 Schema Layer

Pydantic schemas will define API request and response structures.

They will be separate from SQLAlchemy database models so that API contracts do not depend directly on the database representation.

## 5. Frontend Architecture

The React application will be organized around the main user workflows:

- Employee management.
- Salary management and history.
- Compensation analytics.

Frontend responsibilities include:

- Rendering forms, tables, filters, and analytics views.
- Validating user input where useful for immediate feedback.
- Calling backend APIs.
- Displaying loading, success, empty, and error states.
- Managing pagination and filter state.

The frontend will not independently calculate authoritative compensation analytics. Results and business-rule enforcement will come from the backend.

## 6. Initial Domain Model

The initial domain model contains three entities: `Employee`, `SalaryRecord`, and `SalaryAuditLog`.

### 6.1 Employee

Represents an employee within ACME.

Proposed fields:

- `id`: Internal primary key.
- `employee_code`: Unique business identifier.
- `full_name`: Employee name.
- `country`: Employee's associated country.
- `department`: Employee's department.
- `job_title`: Employee's job title.
- `employment_status`: Current employment status.
- `created_at`: Record creation timestamp.
- `updated_at`: Last update timestamp.

### 6.2 SalaryRecord

Represents a salary record for an employee from a specified effective date.

Proposed fields:

- `id`: Internal primary key.
- `employee_id`: Foreign key referencing Employee.
- `amount`: Original salary amount stored using a fixed-precision numeric type.
- `currency`: Supported three-letter currency code.
- `pay_frequency`: Supported value of `MONTHLY` or `ANNUAL`.
- `effective_from`: Date on which the salary becomes applicable.
- `created_at`: Record creation timestamp.
- `updated_at`: Last update timestamp, where applicable.

An employee can have multiple salary records with different effective dates. Only one salary record per employee may have a given effective date.

Ordinary salary changes create new records. Historical corrections follow a separate audited process.

Salary records preserve the originally recorded amount, currency, pay frequency, and effective date, except where an authorized historical correction changes the applicable salary data. Such corrections must retain an audit trail.

### 6.3 SalaryAuditLog

Records changes made when correcting existing salary information.

Proposed fields:

- `id`: Internal primary key.
- `salary_record_id`: Reference to the affected salary record.
- `old_values`: Previous salary values being corrected.
- `new_values`: Corrected salary values.
- `reason`: Explanation for the correction.
- `changed_at`: Timestamp of the correction.
- `changed_by`: Identifier of the user responsible for the correction.

The audit log must preserve the original and corrected values. Audit entries must not be silently overwritten or deleted through ordinary application operations.

Salary corrections and their audit entries must be persisted atomically. The salary records remain the source of truth for calculating applicable compensation; audit logs provide accountability and correction history.

The exact column types, constraints, and relationships will be finalized during database design.

## 7. Salary History and Business Rules

The following rules govern salary records and historical corrections:

1. Ordinary salary changes create new salary records rather than overwriting historical salary values.
2. The salary applicable on a given date is the record with the latest effective date that is on or before the requested date.
3. Future-dated salary changes may be recorded but must not become applicable before their effective dates.
4. Duplicate effective dates for the same employee are rejected. Records with different effective dates are permitted.
5. Salary records must reference an existing employee.
6. Salary amounts must be positive and use a supported currency and pay frequency.
7. Supported currencies are INR, USD, GBP, EUR, CAD, and AUD.
8. Salary records preserve their original amount, currency, pay frequency, and effective date, except where an authorized historical correction changes the recorded values.
9. Monthly salaries are normalized to annual equivalents by multiplying by 12. Annual salaries remain unchanged.
10. Salaries in different currencies must not be compared directly or combined as equivalent values without an explicitly defined currency conversion policy.
11. Historical corrections must record the original values, corrected values, reason, timestamp, and responsible user.
12. A historical correction and its audit entry must succeed or fail together.
13. Corrected salary data must be used for subsequent applicable-salary calculations, while the audit log retains evidence of the correction.

The effective-date lookup must use the latest applicable record rather than simply selecting the most recently created record.

## 8. Compensation Analytics

Compensation analytics will be calculated using persisted employee and salary records.

The backend will support questions such as:

- Employee counts by country and department.
- Average, median, minimum, and maximum annual salary for a selected group.
- Departments with the highest average salary within a country.
- Salary changes over a selected period.
- Employee counts within salary ranges.

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

Compensation analytics must group or filter salary values by currency. Results must identify the currency used, and values from different currencies must not be combined into a single average, median, minimum, maximum, or salary-range calculation.

### 8.2 Salary Standardization

Salary records will preserve their original amounts and pay frequencies. The initial version supports monthly and annual salaries.

For analytics:

- Monthly salaries will be normalized to annual equivalents by multiplying by 12.
- Annual salaries will remain unchanged.
- Normalized values will be used for salary averages, medians, minimums, maximums, and salary-range queries.

Hourly salaries and conversions requiring working-hours assumptions are out of scope.

### 8.3 Reporting Rules

Analytics will use a reporting date to determine which salary record applies to each employee.

- The default reporting date is the current date.
- Users may select another reporting date for historical salary analysis.
- Employee headcount counts employees whose current employment status is active.
- Salary analytics include active employees who have an applicable salary record on the selected reporting date.
- Employees without an applicable salary record are excluded from salary calculations and counted separately.
- Monthly salary values are annualized before salary statistics and salary-range calculations.
- Salary calculations must be performed separately for each currency.

The initial version stores current employment status rather than employment-status history. Therefore, historical salary queries will use the salary applicable on the requested date but will not reconstruct an employee's historical employment status.

Analytics must use persisted employee and salary records rather than hardcoded results or estimates generated by an AI model.

## 9. Database and Migrations

PostgreSQL will store persistent application data.

SQLAlchemy will manage database interactions, while Alembic will track schema changes through versioned migrations.

The design will use:

- Primary and foreign key constraints.
- Uniqueness constraints for employee identifiers.
- A uniqueness constraint on the combination of employee and salary effective date.
- Appropriate indexes for frequently queried fields.
- Transactions for operations that must succeed or fail together.
- Database-level pagination and filtering for employee listings.
- Database constraints and application validation for data integrity.

The seed script will generate approximately 10,000 synthetic employees and associated salary records. It must support repeatable execution without unintentionally creating duplicate records.

Detailed column definitions, numeric precision, nullability, additional uniqueness rules, indexes, and transaction boundaries will be established during database design.

## 10. Authentication and Authorization

The application will restrict access to employee and salary information.

The implementation will define an authentication mechanism, credential-handling approach, and authorization rules before exposing sensitive endpoints.

Secrets and credentials must be stored outside source control. Authorization must be enforced by the backend rather than relying only on frontend visibility.

Salary corrections must be attributable to an authenticated user so that the audit log identifies who performed the correction.

The exact authentication implementation will be selected during detailed design.

## 11. Testing Strategy

### 11.1 Unit Tests

Test business logic independently, including:

- Employee and salary validation.
- Salary effective-date selection.
- Duplicate effective-date rejection.
- Salary-history rules.
- Historical correction and audit-log behavior.
- Currency and pay-frequency validation.
- Monthly-to-annual salary normalization.
- Compensation analytics calculations.
- Edge cases involving missing salary records and reporting dates.

### 11.2 Integration Tests

Test interactions between application components, including:

- Database persistence and constraints.
- Employee and salary API endpoints.
- Pagination, filtering, and error handling.
- Salary changes and historical record retrieval.
- Future-dated salary changes.
- Historical corrections and audit-log persistence.
- Transaction rollback when a correction or its audit entry fails.
- Analytics queries against persisted data.

### 11.3 Frontend Tests

Test important user interactions, including:

- Form validation.
- Employee search and pagination.
- Salary history display.
- Analytics results and error states.

Tests should be deterministic, fast where practical, and independent of external services. Integration tests will use a dedicated test database or isolated test environment.

## 12. Proposed Repository Structure

```text
acme-salary-management/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── db/
│   │   └── main.py
│   ├── migrations/
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── features/
│   │   ├── pages/
│   │   ├── services/
│   │   └── tests/
│   └── package.json
├── scripts/
├── docs/
│   ├── requirements.md
│   └── architecture.md
├── .gitignore
├── README.md
└── requirements.txt
```

This is a proposed structure. Directories will be created when they are needed rather than adding empty folders without a purpose.

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

The architecture is successful when it supports a maintainable application in which:

- Employee and salary records are stored consistently.
- Salary history can be retrieved accurately for a specified date.
- Future-dated salary changes are applied only when effective.
- Historical corrections retain an auditable record of changes.
- Monthly and annual salary records preserve their original values and pay frequencies, subject to audited corrections.
- Annualized salary calculations follow explicit business rules.
- Salary comparisons respect currency restrictions.
- API handling, business logic, data access, and frontend responsibilities are separated.
- Core rules can be tested independently.
- The application can be extended without unnecessary complexity.

## 15. Open Decisions

The following implementation decisions remain open:

1. Exact database column definitions, numeric precision, nullability, constraints, and indexes.
2. Authentication mechanism and authorization policy.
3. Database transaction boundaries and test-database strategy.
4. API contracts, error responses, and pagination conventions.
5. Deployment target and configuration strategy.
6. The audit log's storage format and actor identification mechanism.
7. Whether future versions should support additional salary frequencies or currency conversion.