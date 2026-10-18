# ACME Employee Salary Management System

## 1. Goal

Build a web-based application that enables ACME's HR Manager to manage employee information, maintain salary records, and analyze compensation across the organization.

The system must support approximately 10,000 employees across multiple countries and provide reliable answers to common compensation-related business questions.

## 2. Primary User

**HR Manager**

The HR Manager is responsible for maintaining employee records, managing salary changes, and understanding compensation patterns across the organization.

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

### 4.2 Salary Management

- Record salary amount, currency, pay frequency, and effective date for each employee.
- Allow authorized HR users to record salary changes.
- Preserve previous salary records instead of overwriting salary history.
- Validate salary information before saving it.
- Identify the salary applicable to an employee on a given date.

### 4.3 Compensation Analytics

The application must answer common business questions, including:

- How many employees work in each country or department?
- What are the average, median, minimum, and maximum salaries for a selected group?
- Which departments have the highest average salary within a country?
- How has compensation changed over a selected period?
- How many employees fall within a selected salary range?

**Business rules:**

- Salary comparisons must use a consistent currency and pay frequency.
- Salaries in different currencies must not be directly compared without a defined currency conversion policy.
- Monthly and annual salaries must be normalized before comparison.
- Analytics must use stored employee and salary records rather than hardcoded results.

### 4.4 Data Seeding

- Provide a repeatable seed script that generates approximately 10,000 synthetic employee records and associated salary data.
- Generate realistic, internally consistent data suitable for testing employee management, salary history, and analytics.
- Avoid using real employee information or confidential salary data.
- Document how to run the seed script.

### 4.5 Access Control

- Restrict access to employee and salary information to authorized users.
- Keep credentials and sensitive configuration outside source control.

## 5. Non-Functional Requirements

### 5.1 Maintainability

- Code must be readable, modular, and easy to extend.
- Business logic, data access, API handling, and frontend responsibilities must be clearly separated.

### 5.2 Performance

- The application must support approximately 10,000 employee records without loading the entire dataset into the frontend.
- Employee listing and search operations must use pagination and appropriate query strategies.

### 5.3 Reliability and Data Integrity

- Employee and salary records must follow defined validation rules.
- Salary history must be preserved when compensation changes.
- Analytics must produce consistent results for the same dataset and query criteria.

### 5.4 Testing

- Include meaningful unit tests covering core business logic and validation.
- Tests must be fast, deterministic, and easy to understand.
- Tests should be independent where practical and must not rely on external services for ordinary unit-test execution.

### 5.5 Security

- Employee and salary information must be accessible only to authorized users.
- Sensitive configuration and credentials must not be committed to source control.

### 5.6 Documentation

- Provide instructions for setting up and running the application.
- Document how to execute tests and seed the database.
- Include deployment instructions.

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

These features are excluded to keep the initial implementation focused on employee information, salary history, and reliable compensation analytics.

## 7. Acceptance Criteria

The application will be considered functionally complete when:

1. Authorized HR users can create, view, and update employee records.
2. Employee records can be searched and filtered across the seeded dataset using pagination.
3. Duplicate employee IDs and invalid employee or salary data are rejected.
4. Salary changes preserve historical records and effective dates.
5. The system can identify the applicable salary for a specified date.
6. Compensation analytics calculate results from stored data using the defined business rules.
7. Salary comparisons respect currency and pay frequency.
8. The seed script can populate the application with approximately 10,000 synthetic employees and associated salary records.
9. Core functionality is covered by meaningful, fast, deterministic unit tests.
10. The project includes setup, testing, seeding, and deployment documentation.

## 8. Success Criteria

The HR Manager can securely manage employee and salary information in one application, review historical compensation changes, and answer common organizational compensation questions without relying on manually maintained spreadsheets.

The solution must remain understandable, testable, and maintainable as the dataset and business requirements grow.