# ACME HRMS — Product Roadmap

## 1. Purpose

This roadmap defines the incremental evolution of ACME HRMS from the existing assessment application into a modular HRMS product.

The existing `main` branch remains the assessment baseline. Product development proceeds on `develop/hrms-v2`, with each feature implemented in a separate feature branch and merged only after review and validation.

The roadmap defines intended delivery order, dependencies, and completion criteria. It does not imply that a module is implemented simply because it appears here.

## 2. Current Baseline

The assessment application provides the starting point, including:

- Employee directory and server-side search/filtering.
- Salary records and effective-date-based salary lookup.
- Salary correction and audit logging.
- Compensation analytics.
- Session-based authentication and CSRF protection.
- PostgreSQL persistence and Alembic migrations.
- React frontend and FastAPI backend.
- Automated tests and Docker Compose support.
- A repeatable development seed process.

Before changing these capabilities, inspect the current implementation and establish the migration and regression-testing strategy.

The assessment branch must not receive HRMS V2 feature merges.

## 3. Development Principles

1. Work on one feature at a time.
2. Create each feature branch from the latest `develop/hrms-v2`.
3. Inspect relevant code, tests, database models, and migrations before implementation.
4. Define requirements and acceptance criteria before coding.
5. Keep database migrations backward-aware where practical.
6. Add tests for new behavior and existing behavior affected by the change.
7. Review the complete diff before merging.
8. Update documentation with the feature.
9. Merge only after required checks pass.
10. Avoid unrelated refactoring and large, speculative rewrites.

## 4. Milestone 0 — Product and Architecture Foundation

### Objectives

Establish a shared product direction and architecture before extending the data model.

### Deliverables

- Product vision.
- Product roadmap.
- User personas and permission expectations.
- Module boundaries and domain terminology.
- Multi-tenancy architecture decision.
- Authorization architecture decision.
- Domain model and migration strategy.

### Acceptance criteria

- Product scope and non-goals are documented.
- Dependencies between major modules are understood.
- Security and data isolation requirements are identified.
- The initial multi-tenancy approach is selected based on documented trade-offs.
- The assessment implementation remains unchanged.

## 5. Milestone 1 — Multi-Tenancy

### Objectives

Support multiple customer organizations with enforced data isolation.

### Planned work

- Define the tenant domain model.
- Define tenant identifiers and tenant ownership for business records.
- Decide how users belong to tenants and how tenant context is established.
- Enforce tenant-scoped data access in the backend.
- Protect against cross-tenant access through APIs and direct object identifiers.
- Define migration and development-seed behavior for the existing assessment data.
- Add tests covering tenant isolation and unauthorized access.

### Acceptance criteria

- Tenant ownership is explicit for applicable business data.
- Tenant context is derived from a trusted, authenticated context rather than an arbitrary client-supplied identifier alone.
- Cross-tenant reads and writes are rejected.
- Tests demonstrate isolation across representative endpoints.
- Existing salary, audit, authentication, and analytics behavior remains covered by regression tests.
- Migrations and local startup instructions are documented.

## 6. Milestone 2 — Organization Structure

### Objectives

Model the organizational structure within each tenant.

### Planned entities

- Organization and legal entity.
- Business unit.
- Department.
- Location.
- Job family.
- Job level.
- Position, where required.

### Planned work

- Define relationships and ownership boundaries.
- Establish unique constraints and validation rules.
- Define how departments and locations are associated with legal entities.
- Introduce APIs and administrative UI incrementally.
- Define safe handling of organizational changes and historical references.

### Acceptance criteria

- Organizational entities are tenant-scoped.
- Invalid or cross-tenant relationships cannot be created.
- Relevant APIs and UI support the agreed operations.
- Authorization, validation, and regression tests pass.
- Domain and database documentation is updated.

## 7. Milestone 3 — Identity, RBAC, and Data Scope

### Objectives

Move from basic authentication to enforceable permissions and data access boundaries.

### Planned roles

- Organization administrator.
- HR administrator.
- HR manager.
- Department or reporting manager.
- Payroll or finance user.
- Employee.

These are initial personas, not necessarily fixed database roles. The final permission model must allow appropriate configuration without granting broad access by default.

### Planned work

- Define permission naming and resource boundaries.
- Define role-permission assignments.
- Define user and tenant membership.
- Define self, team, department, legal-entity, and tenant scopes.
- Protect sensitive compensation and personal information.
- Enforce authorization in backend service/API boundaries.
- Add negative authorization tests.

### Acceptance criteria

- Every protected operation has an explicit authorization rule.
- Access is denied by default where no permission is granted.
- Users cannot expand their access by changing request parameters or resource IDs.
- Sensitive fields are protected independently of general employee-directory access.
- Authorization behavior is tested and documented.

## 8. Milestone 4 — Core HR and Employment History

### Objectives

Expand the existing employee directory into a structured employee master.

### Planned work

- Extend employee profiles with approved employment attributes.
- Associate employees with organizational entities.
- Define reporting-manager relationships.
- Define employment types and employment statuses.
- Introduce effective-dated employment history for attributes requiring historical accuracy.
- Preserve existing salary history as a separate domain concept.
- Define data-retention and sensitive-field access requirements.
- Provide appropriate employee profile and history APIs and UI.

### Acceptance criteria

- Employee records reference valid organizational entities within their tenant.
- Historical employment changes are represented according to documented effective-date rules.
- Existing salary functionality remains consistent with the new employee model.
- Invalid transitions and conflicting records are rejected.
- Authorization and history behavior are tested.

## 9. Milestone 5 — Workflow and Approvals

### Objectives

Establish reusable approval capabilities for HR operations.

### Initial use cases

- Employee information changes.
- Leave requests.
- Compensation revisions.
- Attendance regularization.

### Planned work

- Define workflow instances and states.
- Define approvers and approval transitions.
- Track decisions, reasons, and timestamps.
- Handle rejection, cancellation, and resubmission.
- Enforce permissions and prevent unauthorized state transitions.
- Define notifications and failure-handling behavior.

### Acceptance criteria

- Invalid transitions are rejected.
- Approval actions are authorized and auditable.
- Concurrent updates do not silently overwrite decisions.
- Workflow history is queryable.
- Tests cover successful, rejected, cancelled, and invalid transitions.

## 10. Milestone 6 — Workforce Management

### Objectives

Deliver attendance, shifts, holidays, and leave.

### Planned modules

- Shift and work-schedule management.
- Attendance events and daily summaries.
- Holiday calendars.
- Leave types and policies.
- Leave requests and balances.
- Accrual, carry-forward, and encashment where required.
- Attendance regularization.
- Integration with approval workflows.

### Acceptance criteria

- Attendance and leave rules are explicit and configurable where needed.
- Time zones, date boundaries, holidays, and policy edge cases are covered.
- Leave balances and attendance calculations are reproducible and tested.
- Approved changes have appropriate audit history.
- Permissions are enforced for employees, managers, and HR administrators.

## 11. Milestone 7 — Payroll

### Objectives

Evolve compensation management into a controlled payroll-processing subsystem.

### Planned modules

- Compensation structures and salary components.
- Payroll periods and payroll runs.
- Earnings and deductions.
- Attendance and leave inputs.
- Payroll calculation results.
- Review and approval.
- Payslip generation.
- Payroll adjustment and reconciliation.
- Accounting and bank-file integrations where required.

### Acceptance criteria

- Payroll runs have defined lifecycle states.
- Calculations are deterministic and reproducible from recorded inputs and rule versions.
- Approved or finalized payroll cannot be silently altered.
- Corrections and reruns have controlled, auditable behavior.
- Currency, rounding, effective dates, and jurisdiction-specific rules are explicitly defined.
- Statutory calculations are validated against authoritative requirements before being used for real payroll.

## 12. Milestone 8 — Employee and Manager Self-Service

### Objectives

Provide role-appropriate portals for employees and managers.

### Planned capabilities

- View permitted employee information.
- Request profile changes.
- Apply for leave and view balances.
- View attendance and request corrections.
- View permitted compensation information and payslips.
- Access assigned documents.
- Review and process approvals.
- View authorized team information.

### Acceptance criteria

- Employees can access only their own permitted data.
- Managers can access only authorized team information.
- HR permissions remain separate from employee permissions.
- Sensitive responses are not exposed through APIs or frontend state to unauthorized users.
- End-to-end tests cover primary employee and manager journeys.

## 13. Milestone 9 — Recruitment and Onboarding

### Objectives

Support the transition from candidate to employee.

### Planned capabilities

- Job requisitions.
- Candidate profiles and applications.
- Interview stages and feedback.
- Offers and offer status.
- Onboarding tasks and documents.
- Controlled candidate-to-employee conversion.

### Acceptance criteria

- Candidate and employee data have clear ownership and lifecycle rules.
- Duplicate or incomplete conversions are handled safely.
- Access to candidate personal data is restricted.
- Recruitment and onboarding workflows are auditable.

## 14. Milestone 10 — Performance and Talent

### Objectives

Support structured performance and career-development processes.

### Planned capabilities

- Goals and objectives.
- Review cycles.
- Self and manager reviews.
- Feedback and calibration where required.
- Development plans.
- Promotion and compensation-change workflows.

### Acceptance criteria

- Review-cycle states and deadlines are defined.
- Employees and managers can access only authorized review information.
- Ratings and decisions are traceable.
- Compensation changes use the established approval and salary-history mechanisms.

## 15. Milestone 11 — Analytics, Integrations, and AI

### Objectives

Provide reliable workforce insights and controlled external integrations.

### Planned capabilities

- Workforce and headcount reporting.
- Hiring, attrition, leave, and attendance metrics.
- Compensation and payroll analytics.
- Exportable reports with access controls.
- Document and notification integrations.
- Natural-language HR analytics as a later capability.

### AI safety requirements

- AI access must respect the requesting user's authorization and data scope.
- The model must not receive unrestricted database access.
- Any generated query or action must be validated before execution.
- Sensitive fields must be excluded unless explicitly authorized.
- Write operations must require appropriate validation and approval.
- Results should be traceable to the data and calculations that produced them.

### Acceptance criteria

- Metrics have documented definitions.
- Aggregations respect tenant, role, and data-scope boundaries.
- Integrations handle retries, failures, and duplicate events appropriately.
- AI capabilities are introduced only after reliable, permission-aware data APIs exist.

## 16. Milestone 12 — Enterprise Readiness

### Objectives

Improve operational readiness as product requirements justify it.

### Planned capabilities

- Automated CI/CD.
- Centralized logging, metrics, and tracing.
- Background job processing.
- Secure document/object storage.
- Backup and restore procedures.
- Rate limiting and abuse protection.
- Dependency and container security checks.
- Performance and load testing.
- Disaster recovery and operational runbooks.
- Accessibility and usability improvements.
- Production deployment and environment management.

### Acceptance criteria

- Critical operational procedures are documented and tested.
- Recovery objectives and data-retention requirements are defined.
- Security-sensitive configuration is managed outside source control.
- Performance targets are measured rather than assumed.
- Deployment and rollback procedures are verified.

## 17. Feature Branch and Merge Workflow

The assessment `main` branch remains separate from product development.

The product integration branch is `develop/hrms-v2`.

For each feature:

1. Update the local integration branch.
2. Create a dedicated feature branch.
3. Inspect affected code and define acceptance criteria.
4. Implement the smallest coherent change.
5. Add or update tests and migrations.
6. Run relevant tests, linting, and type checks.
7. Review the diff and update documentation.
8. Commit changes with descriptive messages.
9. Merge into `develop/hrms-v2` only after checks pass.
10. Verify the integration branch before starting dependent work.

Example branch names:

- `feature/multi-tenancy`
- `feature/organization-structure`
- `feature/rbac`
- `feature/employment-history`
- `feature/workflow-engine`

The integration branch must not be merged into the assessment `main` as part of routine development.

## 18. Prioritization Rules

- Establish tenant isolation before introducing cross-organization business data.
- Define authorization boundaries before exposing sensitive new APIs.
- Establish organization structure before building advanced team-based workflows.
- Implement effective-dated employment data before relying on historical workforce reporting.
- Build and validate payroll inputs before introducing complex statutory calculations.
- Introduce AI only after the underlying data and authorization contracts are reliable.
- Prefer vertical slices that include data model, API, tests, and UI where applicable.
- Reassess priorities as product requirements and operational evidence evolve.

## 19. Roadmap Governance

This roadmap is a living product document.

Changes to milestone order, scope, or acceptance criteria should be documented when new requirements or technical discoveries justify them.

Each milestone should be broken into independently reviewable features. A milestone is complete only when its acceptance criteria are satisfied; a planned feature is not evidence of implemented functionality.
