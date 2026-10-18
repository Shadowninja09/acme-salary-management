# ACME Employee Salary Management System — Architecture

## 1. Purpose

This document describes the proposed technical architecture for the ACME Employee Salary Management System.

The application will allow authorized HR users to manage employee information, maintain salary history, and analyze compensation across approximately 10,000 employees in multiple countries.

The architecture prioritizes maintainability, testability, data integrity, and clear separation of responsibilities.

## 2. Technology Stack

| Component                   | Technology                       | Responsibility                                |
| --------------------------- | -------------------------------- | --------------------------------------------- |
| Frontend                    | React.js                         | User interface and user interactions          |
| Frontend build tool         | Vite                             | Frontend development and production builds    |
| Backend API                 | FastAPI                          | HTTP endpoints and request handling           |
| Request/response validation | Pydantic                         | Validate API inputs and outputs               |
| ORM                         | SQLAlchemy                       | Database access and object-relational mapping |
| Database migrations         | Alembic                          | Version and apply database schema changes     |
| Database                    | PostgreSQL                       | Persistent employee and salary data           |
| Backend testing             | pytest                           | Unit and integration tests                    |
| API testing                 | FastAPI TestClient               | Test HTTP endpoints                           |
| Frontend testing            | Vitest and React Testing Library | Test frontend behavior                        |
| Version control             | Git and GitHub                   | Track and review changes                      |

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
|           PostgreSQL             |
|                                  |
| Employees                        |
| Salary History                   |
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
- Apply compensation rules to analytics.
- Coordinate database operations when a business operation involves multiple records.

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

- Employee management
- Salary management and history
- Compensation analytics

Frontend responsibilities include:

- Rendering forms, tables, filters, and analytics views.
- Validating user input where useful for immediate feedback.
- Calling backend APIs.
- Displaying loading, success, empty, and error states.
- Managing pagination and filter state.

The frontend will not independently calculate authoritative compensation analytics. Results and business-rule enforcement will come from the backend.

## 6. Initial Domain Model

The initial domain model will contain two primary entities.

### 6.1 Employee

Represents an employee within ACME.

Proposed fields:

- `id`: Internal primary key.
- `employee_code`: Unique business identifier.
- `full_name`: Employee name.
- `country`: Employee's associated country.
- `department`: Employee's department.
- `job_title`: Employee's job title.
- `employment_status`: Employment status.
- `created_at`: Record creation timestamp.
- `updated_at`: Last update timestamp.

### 6.2 SalaryRecord

Represents a salary record for an employee at a particular effective date.

Proposed fields:

- `id`: Internal primary key.
- `employee_id`: Foreign key referencing Employee.
- `amount`: Annual salary amount stored using an appropriate fixed-precision numeric type.
- `currency`: Currency code, such as INR or USD.
- `effective_from`: Date on which the salary becomes applicable.
- `created_at`: Record creation timestamp.

The initial version will standardize all salary amounts as **annual salaries**. Salary frequency such as monthly or hourly will not be stored in the initial version.

An employee can have multiple salary records over time.

The detailed database schema, constraints, indexes, and relationship definitions will be finalized before implementation.

## 7. Salary History and Business Rules

The proposed initial rules are:

1. Salary changes create new salary records rather than overwriting historical salary values.
2. The salary applicable on a given date is the record with the latest effective date that is not later than the requested date.
3. A future-dated salary change may be recorded and should not become the current salary before its effective date.
4. An employee must not have conflicting salary records with the same effective date.
5. Salary records must reference an existing employee.
6. Salary amounts must be positive and use a supported currency.

The initial version stores all salaries as annual amounts, so no pay-frequency conversion is required.

The exact rules for correcting an erroneous historical record and handling future-dated changes will be finalized during domain and database design.

## 8. Compensation Analytics

Compensation analytics will be calculated using persisted employee and salary records.

The backend will support questions such as:

- Employee counts by country and department.
- Average, median, minimum, and maximum annual salary for a selected group.
- Departments with the highest average salary within a country.
- Salary changes over a selected period.
- Employee counts within salary ranges.

### Currency handling

Salaries in different currencies must not be directly compared or combined as equivalent values.

The initial version will restrict salary comparisons to a consistent currency.

Currency conversion will remain out of scope unless a reliable exchange-rate source, applicable date, and conversion policy are introduced.

### Salary standardization

All salary records in the initial version will represent annual salary amounts.

Because the system uses a single salary frequency, compensation analytics do not require pay-frequency normalization.

If support for different salary frequencies is introduced in the future, the conversion rules will be explicitly defined before implementation.

Analytics must be calculated from database records rather than hardcoded values or estimates generated by an AI model.

## 9. Database and Migrations

PostgreSQL will store persistent application data.

SQLAlchemy will manage database interactions, while Alembic will track schema changes through versioned migrations.

The design will use:

- Primary and foreign key constraints.
- Uniqueness constraints for employee identifiers.
- Appropriate indexes for frequently queried fields.
- Transactions for operations that must succeed or fail together.
- Database-level pagination and filtering for employee listings.

The seed script will generate approximately 10,000 synthetic employees and associated salary records. It must support repeatable execution without unintentionally creating duplicate records.

## 10. Authentication and Authorization

The application will restrict access to employee and salary information.

The implementation will define an authentication mechanism, credential-handling approach, and authorization rules before exposing sensitive endpoints.

Secrets and credentials must be stored outside source control. Authorization must be enforced by the backend rather than relying only on frontend visibility.

The exact authentication implementation will be selected during detailed design.

## 11. Testing Strategy

### Unit Tests

Test business logic independently, including:

- Employee and salary validation.
- Salary effective-date selection.
- Salary-history rules.
- Currency validation.
- Compensation analytics calculations.

### Integration Tests

Test interactions between application components, including:

- Database persistence and constraints.
- Employee and salary API endpoints.
- Pagination, filtering, and error handling.
- Salary changes and historical record retrieval.

### Frontend Tests

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
- Compensation analytics follow explicit business rules.
- Annual salary amounts are represented consistently.
- API handling, business logic, data access, and frontend responsibilities are separated.
- Core rules can be tested independently.
- The application can be extended without unnecessary complexity.
