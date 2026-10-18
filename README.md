# ACME Employee Salary Management System

A web-based employee and salary management application designed to help ACME's HR team manage employee records, track salary history, and analyze compensation across the organization.

## Problem Statement

ACME manages approximately 10,000 employees across multiple countries using Excel spreadsheets. As the organization grows, maintaining accurate employee records, tracking salary changes, and understanding compensation patterns becomes increasingly difficult.

This project aims to centralize employee and salary information in a maintainable application and provide reliable compensation analytics to support HR decision-making.

## Project Objectives

- Manage employee information in a centralized system.
- Maintain salary records and preserve historical changes.
- Search and filter employee records efficiently.
- Analyze compensation across countries and departments.
- Support approximately 10,000 employees using synthetic seed data.
- Maintain high standards of code quality, testing, and maintainability.

## Planned Features

- Employee creation, viewing, and updating.
- Employee search, filtering, and pagination.
- Salary management with effective dates and historical records.
- Compensation analytics, including average, median, minimum, and maximum salaries.
- Repeatable database seed script for approximately 10,000 synthetic employees.
- Access control for sensitive employee and salary information.
- Unit tests for core business logic and validation.

## Out of Scope

The initial version will not include payroll processing, tax calculations, attendance or leave management, recruitment, employee self-service, external payroll integrations, Excel/CSV import and export, or AI-powered natural-language analytics.

## Repository Structure

```text
acme-salary-management/
├── backend/
├── frontend/
├── tests/
├── scripts/
├── docs/
│   └── requirements.md
├── .gitignore
├── README.md
└── requirements.txt
```

The directory structure and project files will evolve as the architecture and implementation are finalized.

## Development Approach

The project will be developed incrementally, with a focus on:

- Clear requirements and deliberate design decisions.
- Separation of business logic, data access, API handling, and frontend responsibilities.
- Meaningful unit tests covering core functionality.
- Fast, deterministic, and easy-to-understand tests.
- Small, focused Git commits that demonstrate the evolution of the solution.
- Documentation for setup, testing, data seeding, and deployment.

AI coding tools may assist with implementation, test creation, and code review. All generated changes will be reviewed and validated before being accepted.

## Requirements

The project's functional requirements, business rules, acceptance criteria, and non-functional requirements are documented in [`docs/requirements.md`](docs/requirements.md).

## Technology Stack

The technology stack will be finalized during the architecture and design phase before implementation begins.

## Project Status

**Phase:** Requirements and project setup.

The initial repository structure and requirements are being prepared. Application features will be implemented after the architecture and technology decisions are finalized.