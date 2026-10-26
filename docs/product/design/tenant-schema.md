# Tenant database schema

Design only. This document proposes what belongs in one ACME HRMS V2 tenant database. It does not create tables, migrations, or application code.

The assessment application on `main` stays unchanged. V2 work belongs on `develop/hrms-v2` and feature branches. This proposal follows `docs/product/decisions/ADR-001-multi-tenancy.md` and `docs/product/design/control-plane-schema.md`. ADR-001 is the architectural source of truth. The control-plane document is a schema proposal, not an approved implementation. Reviewing this document does not approve it, and it does not mean any tenant table has been implemented.

Labels used below:

- **ADR decision** — a direction already recorded in ADR-001. This document does not change those decisions.
- **Verified** — behavior read from the current application.
- **Proposed** — a placement or constraint that follows the ADR but is not itself an ADR decision.
- **Unresolved** — still needs an explicit choice. Section 9 lists them. A sentence in this document does not select one.

## 1. Status, scope, and non-goals

### Status

Proposal. ADR-001 status remains “Proposed — approved architectural direction, implementation not started.” ADR-001 §15 step 3 calls for a tenant schema, including company users and refresh-session records. This document is that proposal. It does not define the refresh-session table’s open columns.

### Scope

- Business tables carried forward from the assessment database: employees, salary records, and salary audit logs.
- Tenant-local company identity: the company-assigned employee ID, the Argon2id password hash, and the fact that a company role check is required.
- Tenant-local employee access status, the server-recorded deactivation time, and that company’s choice of immediate revocation or a 12-hour document-only grace period.
- The requirement to store refresh-token hashes in this database, with rotation and reuse detection.
- Authorization and tenant-isolation rules that this database must be able to support.
- What happens to assessment sessions and the environment HR-manager login at cutover.

### Non-goals

- Implementing the schema, Alembic revisions, provisioning, or login.
- Approving the open choices in section 9.
- Changing ADR-001 or the control-plane schema proposal.
- Putting company users, employee IDs, password hashes, employee access status, the grace policy, or refresh-session records in the control plane (ADR decisions 5, 6, 7, and 13; control-plane schema §1 and §7).
- Choosing company `access_status`, its initial value, its nullability, who may change it, or whether that change is audited. Those stay on `tenants` in the control plane (ADR decision 15 and §5; control-plane schema §6 and §16).
- Adding `grace_until` as a required column (ADR decision 18).
- Inventing a role and permission matrix or a first-administrator onboarding flow (ADR §14; control-plane schema §16).
- Finalizing JWT claims, signing keys, logout’s effect on an already-issued JWT, the token-invalidation mechanism, CSRF after login, cookie attributes other than HttpOnly, refresh-token family structure, the reuse response, or concurrent refresh behavior (ADR §6 and §14; control-plane schema §16).
- Designing platform-operator authentication (ADR §6 and §14; control-plane schema §4 and §16).
- Payroll, attendance, recruitment, self-service, or AI features.
- Copying the current assessment database as part of writing this document (ADR §9).

## 2. Boundary between the control plane and tenant database

ADR decision 2 gives each company its own PostgreSQL database. ADR decision 7 and control-plane schema §4 keep a separate control-plane database for registry, routing, provisioning, company access status, and platform operations.

### Control plane

Established by ADR §4 and §5 and by control-plane schema §6:

- Tenant identity.
- Provisioning status, exactly these six values: `requested`, `provisioning`, `migrating`, `ready`, `failed`, and `suspended`.
- Company access status, `active` or `deactivated` in the control-plane proposal (`Active` or `Deactivated` in ADR-001). This is not a provisioning state.
- Routing metadata: which database serves the tenant, and references to database credentials. Those references are not company password hashes.
- Provisioning step, routing disposition, and the last schema revision successfully applied to this tenant database.
- Provisioning requests, provisioning attempts, and platform audit events.

`ready` means migrations succeeded and the first company administrator exists, so the database may be routed (ADR decision 14 and §5). It is not sufficient for normal HRMS business APIs. Those APIs also require company access status `Active` and the other authorization checks in ADR decisions 15–19. Provisioning success, failure, suspension, recovery, and compensation do not activate or deactivate the company (ADR §5; control-plane schema §9 and §12).

This tenant database does not store `tenants.status`, `access_status`, `provisioning_state`, or `routing_disposition`.

### Tenant database

Established by ADR decisions 5, 6, 11, and 16–18 and by control-plane schema §7:

- Employee, salary, and salary-audit rows.
- Company user accounts and the company-assigned employee ID. The employee ID is unique within this tenant. It does not have to be unique across companies.
- Password hashes. The hash is a slow hash such as Argon2id. It is not plaintext.
- Employee access status, `Active` or `Deactivated`, the server-recorded deactivation time, and this company’s immediate-revocation or 12-hour document-only grace policy.
- Refresh-session records. Only the refresh-token hash is persisted here.

The access JWT and the raw refresh token are not stored in either database (ADR decision 13).

Login does not look up a control-plane user or membership. The company-specific URL selects one control-plane registry row. The employee ID and password are then checked in this database (ADR §6; control-plane schema §8). A person who works for two companies has two tenant-local accounts, one in each company’s database, reached by each company’s login URL (control-plane schema §7).

The first company administrator is created in this database. There is no cross-database foreign key to that account (ADR decision 14). The control plane records success as a succeeded `bootstrap_admin` provisioning request. It does not point at the account (control-plane schema §6 and §9). How that person proves identity, how the password is set, and who may start that request are unresolved (ADR §14; control-plane schema §16).

Which physical tables hold the company user, the password hash, the access status, the grace policy, and the refresh-session hash is part of a later approved schema. This proposal fixes the database they belong to and the rules those facts must satisfy. It does not silently choose table or column names for the facts ADR-001 left undesigned.

## 3. Assessment tables carried forward

Verified from the current models. These are assessment shapes. V2 has not created a tenant copy of them.

### `employees`

`backend/app/models/employee.py` defines `employees` with:

- `id`, `bigint` identity, primary key.
- `employee_code`, `varchar(20)`, not null. Unique across the whole table today (`uq_employees_employee_code`).
- `full_name`, `country`, `department`, `job_title`.
- `employment_status`, constrained to `ACTIVE` or `INACTIVE` (`ck_employees_employment_status`).
- `created_at` and `updated_at`.

`employment_status` is the assessment HR employment flag. It is not the V2 employee access status in ADR decision 16. This proposal does not map `ACTIVE`/`INACTIVE` onto `Active`/`Deactivated`, and it does not decide that they share a column.

ADR decision 6 limits employee ID uniqueness to one tenant. Because each company has its own database, the same unique `employee_code` constraint inside that database satisfies that rule. The same code may exist in another company’s database. This proposal does not drop the per-database uniqueness of `employee_code`. The login identifier in ADR decision 11 is this company-assigned employee ID. Whether the column keeps the name `employee_code` is not a separate decision in the ADR.

### `salary_records`

`backend/app/models/salary.py` defines `salary_records` with:

- `id`, `bigint` identity, primary key.
- `employee_id`, not null, foreign key to `employees.id` with `ON DELETE RESTRICT` (`fk_salary_records_employee_id`).
- `amount`, positive, `numeric(12, 2)`.
- `currency`, one of `INR`, `USD`, `GBP`, `EUR`, `CAD`, `AUD`.
- `pay_frequency`, `MONTHLY` or `ANNUAL`.
- `effective_from`.
- Unique `(employee_id, effective_from)` (`uq_salary_records_employee_id_effective_from`).
- `created_at` and `updated_at`.

ADR §9 requires a rehearsed copy to preserve primary keys and foreign keys so salary history still matches. This proposal keeps that foreign key and that uniqueness inside the tenant database.

### `salary_audit_logs`

`backend/app/models/salary_audit_log.py` defines `salary_audit_logs` with:

- `id`, `bigint` identity, primary key.
- `salary_record_id`, not null, foreign key to `salary_records.id` with `ON DELETE RESTRICT` (`fk_salary_audit_logs_salary_record_id`).
- `action`, `CREATE` or `UPDATE`. An `UPDATE` requires a non-empty `reason`.
- `old_values`, nullable JSON. `new_values`, JSON, not null.
- `changed_by`, `varchar(100)`, not null. It is not a foreign key.
- `changed_at`.

Verified today: `backend/app/services/salary.py` writes `changed_by` from the configured string `HR_MANAGER_IDENTITY`. ADR §1 records the same fact.

Proposed, matching control-plane schema §13: `changed_by` remains a non-key string stored in this database, copied when the salary audit row is written. It is not a foreign key to a control-plane table, and it is not a foreign key back from this audit row to a control-plane user. Deactivating or deleting a company user does not delete or rewrite these audit rows through the control plane. After the user is gone, the stored string remains. Salary history still matches its salary row through the tenant-local foreign keys above. Which string is copied, such as the employee ID or a display label, is the control-plane document’s example. This proposal does not choose between those examples.

These three tables are not control-plane tables. Platform audit events stay in the control plane and are not `salary_audit_logs` (control-plane schema §6 and §13).

## 4. Company identity

ADR decisions 5, 6, and 11 are established. The table layout is not.

Established:

- A company user account lives in this tenant database. There is no control-plane company membership and no company-selection login (decision 5).
- Login uses the company-assigned employee ID and password (decision 11). The password check runs in this database (control-plane schema §3 and §8).
- The password is stored as a hash, not plaintext. ADR §6 keeps a slow hash such as Argon2id. The current application already verifies Argon2 hashes for the environment HR manager (`backend/app/services/auth.py`). That code path is not the V2 user table.
- The employee ID is unique within this tenant (decision 6). Section 3 records how the current `employee_code` uniqueness behaves once each company has its own database.
- After authentication, a role and permission check still decides what the user may do inside the company. A separate database does not replace that check (decision 9; ADR §6).

Unresolved, and not chosen here:

- The role and permission matrix, including any starter role names (ADR §14; control-plane schema §16). This document does not add a role column with a fixed list of names. It records only that the check is tenant-local and is not the platform-operator permission.
- Whether the password hash and the company role live on the employee row or on a separate company-user row. ADR-001 requires both the employee ID and a company user account in this database. It does not say they are the same row.
- The first-administrator onboarding flow (ADR §14; control-plane schema §16).

A company role is not an elevated operator permission. Operator authentication stays unresolved and is not a table in this database (ADR §7 item 8 and §14; control-plane schema §4 and §16).

## 5. Employee access status and document grace

ADR decisions 16, 17, and 18 place these facts in the tenant database. Control-plane schema §1 and §7 say the same thing and forbid a required `grace_until` column. This section does not design the columns.

Established:

- Employee access status is `Active` or `Deactivated` (decision 16). An employee’s access must respect both this status and the company’s current access status in the control plane.
- This is not `employees.employment_status`. The assessment values `ACTIVE` and `INACTIVE` stay the HR employment flag described in section 3 until a later decision says otherwise. This proposal does not treat them as decision 16.
- Each company chooses its own employee deactivation policy. The choices are immediate access revocation, or a 12-hour document-only retrieval grace period. The grace period is not a platform-wide policy (decision 17). The choice is stored in this tenant database (control-plane schema §7).
- The backend records the employee’s deactivation time with server-side time and persists it. Grace eligibility and expiry use that timestamp plus the company’s selected policy. Browser clocks and JWT `exp` do not set the deadline. The persisted state must survive application restarts (decision 18). Decision 18 does not require a separate `grace_until` column. This proposal does not add one.
- During a valid grace period the employee may access only explicitly permitted personal documents, such as eligible payslips and employment documents. Grace does not allow normal HR operations, editing employee records, or viewing other employees’ information. When the grace period ends, document access is denied (decision 17).
- Grace is considered only when the control plane shows provisioning `ready` and company access `active` (ADR §6 and §7 item 7; control-plane schema §9 and §10). A ready company whose `access_status` is `deactivated` is denied normal HRMS business APIs and denied document grace, even when the JWT or refresh token has not expired (ADR decision 15 and §5). Company deactivation overrides an employee grace window.
- When the company’s policy is immediate revocation, a deactivated employee loses normal HRMS access and document access (ADR §6).
- The 15-minute access-token lifetime and the 7-day refresh-token lifetime do not extend the grace deadline and do not restore a deactivated company (decision 19). Refreshing a token does not move the deadline (ADR §6).

Unresolved:

- The exact catalog of permitted personal documents beyond eligible payslips and employment documents (ADR §14). Decision 17 still applies to whatever set is explicitly permitted.
- The physical columns and the table that stores access status, the deactivation timestamp, and the company policy. Naming them here would design the schema ADR decision 18 left undesigned.

Employee deactivation does not rewrite control-plane audit rows and does not change `tenants.status` or `tenants.access_status` (control-plane schema §13).

## 6. Refresh sessions

ADR decisions 12 and 13 are established. The refresh-session table is explicitly part of the tenant schema design, and several of its columns are explicitly not decided.

Established:

- Refresh tokens are opaque random tokens with a 7-day lifetime (decision 12).
- Access tokens and refresh tokens use HttpOnly cookies (decision 12). Cookie names and the other cookie attributes are unresolved. See section 9.
- Persist only the refresh-token hash, and persist it in this tenant database (decision 13). Do not persist the access JWT or the raw refresh token here or in the control plane.
- Rotation and reuse detection are required (decision 13; control-plane schema §7).
- The assessment `user_sessions` table is not this store. Section 8 says those rows are invalidated and are not copied.

The current assessment store, for comparison only, is `backend/app/models/user_session.py`: a unique SHA-256 `token_hash`, `expires_at`, and nullable `revoked_at`, with no user id and no tenant id. `backend/app/services/sessions.py` issues `secrets.token_urlsafe(32)`, stores the SHA-256 hash, and rejects a missing, revoked, or expired row. That shape is verified current behavior. It is not the V2 refresh-session table. V2 hashes must not be assumed to be SHA-256 solely because the assessment code uses SHA-256. The ADR requires a hash of the refresh token and does not name the hash algorithm for that token.

Unresolved, so this proposal does not add the columns:

- Whether one company user may hold more than one refresh session at a time (ADR §14; control-plane schema §16). Control-plane schema §16 says the tenant schema has to wait for that choice.
- The reuse response, whether reuse revokes a token family, and how concurrent refresh requests are handled (ADR §6 and §14; control-plane schema §16). Family, replacement, and reuse columns are not designed here (control-plane schema §7).
- Logout’s effect on an already-issued access JWT, and the mechanism that invalidates that JWT, such as a denylist or a token version (ADR §6 and §14). Those mechanics do not weaken decisions 15–19. This database does not gain an access-token store as part of this proposal.

Rotation and reuse detection remain required even though the response and the family structure are open. A later revision of this proposal can name those columns only after those choices are recorded.

## 7. Authorization and tenant-isolation invariants

These are ADR rules. This database has to be able to support them. This section does not add a control-plane column and does not close the open token questions.

For a business request, ADR §7 and control-plane schema §10 require:

1. Resolve the tenant from the company-specific login URL. An unknown URL fails closed and is not a directory of companies. The URL is not authorization.
2. At login, authenticate the company-assigned employee ID and password in this database. On a later request, authenticate the presented access or refresh token. Claims, signing keys, and the detailed checks are unresolved (ADR §6 and §14).
3. Load provisioning status, company access status, and routing from the control plane. Do not load the company user, the employee access status, or the refresh session from the control plane.
4. Open a connection only to this tenant database, and only when the authenticated identity, the token’s tenant binding, the resolved tenant, and this database agree. Fail closed on any disagreement (ADR decision 8).
5. Ignore any client-supplied tenant id or database name as authorization.
6. Never reuse a company token or a business database connection across tenants.

Fail closed, including for document-only grace, when the tenant is missing, not `ready`, `failed`, or `suspended` (ADR §5 and §7 item 7). Also fail closed for normal HRMS business APIs and for document grace when the company is `Deactivated`, even if the JWT or refresh token has not expired. Do not change the provisioning status to `suspended` because the company is deactivated, and do not close or disrupt another tenant’s pool (control-plane schema §9 and §10).

A document-only request is allowed only when all of the following hold (ADR §7 item 7):

- The tenant is `Ready`.
- The company access status is `Active`.
- The employee access status is `Deactivated`.
- This company selected the 12-hour policy.
- Server time is still inside 12 hours of the persisted deactivation timestamp.
- The request is limited to that employee’s explicitly permitted personal documents.

A cryptographically valid JWT is not enough (ADR decision 19). The protected request still enforces the current company access status, the current employee access status, the applicable permissions, and any still-valid document-only grace period. The permission matrix itself is unresolved (section 4).

Ordinary business connections must not use a PostgreSQL superuser. Runtime privileges for application queries stay separate from the privileges that create databases or apply migrations (ADR §7 items 9 and 10). Credential product, injection, and rotation remain unresolved. Company password hashes are not those database credentials.

## 8. Assessment authentication and session cutover

ADR-001 §9 decides the assessment-data cutover. The legacy login transition in control-plane schema §8 is a proposal. It is not an ADR decision.

Verified today:

- Login is `POST /api/v1/auth/login` in `backend/app/api/auth.py`. It checks `HR_MANAGER_USERNAME` and `HR_MANAGER_PASSWORD_HASH` through `backend/app/services/auth.py`. There is no user table.
- A successful login stores an opaque session hash in `user_sessions` and sets the `acme_session` cookie. That cookie is HttpOnly, SameSite=Lax, path `/`, with `Secure` taken from settings (`backend/app/api/auth.py`).
- The same login sets `acme_csrf`, which is not HttpOnly. `backend/app/services/csrf.py` builds an HMAC bound to the numeric session id. State-changing routes send it in `X-CSRF-Token`. Logout requires that CSRF check and then sets `revoked_at` (`backend/app/services/sessions.py`).
- Login also requires a trusted origin (`require_trusted_login_origin`). ADR §6 keeps an origin check on login because login has no token yet. CSRF for later cookie-authenticated V2 requests is a separate unresolved question.
- `changed_by` uses `HR_MANAGER_IDENTITY` only as an audit label. There is no user row to migrate.

Established by ADR-001 §9:

- Do not copy existing `user_sessions` rows into tenant refresh-session records. Invalidate them. They have no user and no tenant. Copying them would keep the single shared login. Control-plane schema §8 records the same instruction.
- Copy employees, salary records, and salary audit logs on a disposable rehearsal. Preserve primary keys and foreign keys. Leave `main` and the current assessment database unchanged until that rehearsal. Do not truncate the assessment database as part of writing this document.

Proposed transition from control-plane schema §8, not an ADR decision:

- V2 routes do not accept `HR_MANAGER_USERNAME` as a second login path.
- During a rehearsed cutover, create the first company administrator in the default tenant’s database. The password is a new Argon2id hash. The repository has never stored the plaintext password, so it cannot be copied. Do not create a control-plane user for that person. Creating that account in the tenant database, with no cross-database foreign key, is also ADR decision 14. The new Argon2id hash is the proposed transition.
- After that administrator exists, V2 company authentication reads only the tenant database named by the login URL. The environment variables remain for the assessment application on `main`.
- Do not keep a fallback that authenticates the configured HR manager when this database has no matching account. That fallback would skip tenant status and the URL-to-database agreement.

V2 cookie names are not required to be `acme_session` or `acme_csrf`. Cookie names are unresolved (control-plane schema §2 and §16). HttpOnly for the access and refresh cookies is already required (ADR decision 12).

## 9. Open decisions

Every item below needs an explicit approval before implementation treats it as decided. This section does not select one. Items that ADR-001 or the control-plane proposal already closed are not reopened.

| Topic | What stays open | What is already decided |
|---|---|---|
| Role and permission matrix | Names and permissions, including any starter roles (ADR §14; control-plane schema §16). | A company role check is required inside this database. It is not the operator permission (ADR decision 9). |
| Company-user row shape | Whether the password hash and role live on the employee row or on a separate user row. The specific hash algorithm is not closed beyond the description below. | The account, employee ID, and a password hash live in this database (ADR decisions 5, 6, and 11). ADR-001 §6 describes a slow hash such as Argon2id. |
| First-administrator onboarding | How the person proves identity, how the password is set, and who may start `bootstrap_admin` (ADR §14). | The account is created here. No cross-database foreign key. Control-plane evidence is the succeeded provisioning request (ADR decision 14). |
| Employee access columns | Table and column names for access status, the deactivation timestamp, and the company policy. | Values are `Active` and `Deactivated`. The timestamp is server time. The policy is immediate revocation or 12 hours, per company. `grace_until` is not required (ADR decisions 16–18). |
| `employment_status` versus access status | Whether or how assessment `employment_status` (`ACTIVE`/`INACTIVE`) should be related to employee access status (`Active`/`Deactivated`). | Not decided by ADR-001. This proposal treats the two as separate concepts and does not define a mapping. |
| Permitted personal documents | The catalog beyond eligible payslips and employment documents (ADR §14). | Grace allows only explicitly permitted personal documents and denies HR writes and other employees’ data (decision 17). |
| Multiple refresh sessions | Whether one user may hold more than one refresh session (ADR §14). | The hash is stored only in this database (decision 13). |
| Refresh reuse handling | The response, token-family revocation, and concurrent refresh. Family, replacement, and reuse columns wait for this choice (control-plane schema §7 and §16). | Rotation and reuse detection are required (decision 13). |
| Refresh-token hash algorithm | Which hash function stores the refresh token. | The raw token and the access JWT are not stored (decision 13). |
| `changed_by` label | Which non-key string is copied at write time. | It stays a non-key string in this database, not a control-plane foreign key (control-plane schema §13). |
| JWT details | Claims, signing-key management, and validation beyond the agreement rule in ADR decision 8. | Lifetime is 15 minutes. A valid JWT alone does not authorize the company or the employee (decisions 12 and 19). |
| Logout and token invalidation | Immediate revocation or the remaining 15-minute lifetime, and the mechanism, such as a denylist or a token version (ADR §14). | Deactivation authorization is decided in ADR §6. This proposal adds no access-token store. |
| CSRF after login | The V2 design for cookie-authenticated requests (ADR §6 and §14). | The assessment HMAC is verified current behavior, not the V2 design. Login still needs an origin check. |
| Cookie attributes | Names, `Secure`, `SameSite`, `Path`, and `Domain` (ADR §14). | HttpOnly is required for the access and refresh cookies (decision 12). |
| Login URL key | Which control-plane `tenants` value the company URL carries (control-plane schema §16). | The value selects a registry row and is not authorization (ADR decision 8). |
| Initial company access status | The value and nullability for a newly ready company, and any automatic transition from `ready` (ADR §5; control-plane schema §16). | Allowed values are `Active` and `Deactivated`. Becoming `ready` does not set them. |
| Company access-status changes | Who may change `access_status`, whether both directions are allowed, provisioning preconditions, and whether the change must be audited (ADR §7 item 8; control-plane schema §16). | A `deactivated` company is denied normal APIs and document grace. The change does not set provisioning status to `suspended`. |
| Platform-operator authentication | How operators authenticate (ADR §14). | The path is separate from company login and is not a table here. |
| Database hosting, credentials, pools, migration recovery, backup, and deletion | ADR §14 and control-plane schema §16. | They are control-plane and operational questions. This document does not decide them. |

This document proposes a tenant schema only. No application code, database schema, migration, or tenant provisioning has been changed.
