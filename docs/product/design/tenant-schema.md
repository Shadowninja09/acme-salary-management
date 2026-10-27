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

Proposal. ADR-001 status remains “Proposed — approved architectural direction, implementation not started.” ADR-001 §15 step 3 calls for a tenant schema, including company users and refresh-session records. This document is that proposal. Decisions 12, 13, and 18 fix the session behavior. They do not name every physical column.

### Scope

- Business tables carried forward from the assessment database: employees, salary records, and salary audit logs.
- Tenant-local company identity: the company-assigned employee ID, a slow password hash such as Argon2id, and the fact that a company role check is required.
- Employee access through the existing `employment_status` column. There is no separate employee `access_status` and no document-grace period.
- Refresh-session records in this database, including the HMAC-SHA-256 digest, rotation, and the session metadata required by ADR decision 13.
- Authorization and tenant-isolation rules that this database must be able to support.
- What happens to assessment sessions and the environment HR-manager login at cutover.

### Non-goals

- Implementing the schema, Alembic revisions, provisioning, or login.
- Approving the open choices in section 9.
- Changing ADR-001 or the control-plane schema proposal.
- Putting company users, employee IDs, password hashes, or refresh-session records in the control plane (ADR decisions 5, 6, 7, and 13; control-plane schema §1 and §7).
- Choosing who may change company `access_status`, which transitions are allowed, or whether that change is audited. The column itself is decided and stays on `tenants` in the control plane (ADR decision 15 and §5; control-plane schema §6 and §16).
- Adding an employee `access_status` or a grace period for payslips, personal documents, or employment documents (ADR decisions 16 and 17).
- Inventing a role and permission matrix or a first-administrator onboarding flow (ADR §14; control-plane schema §16).
- Choosing cookie names or cookie `Path`. `HttpOnly`, `Secure`, and `SameSite=Lax` are already the initial defaults. Prefer host-only cookies rather than a shared parent-domain cookie (ADR decision 12).
- Designing platform-operator authentication (ADR §6 and §14; control-plane schema §4 and §16).
- Payroll, attendance, recruitment, self-service, or AI features.
- Copying the current assessment database as part of writing this document (ADR §9).
- Copying assessment cookie names, the assessment SHA-256 session hash, or the assessment CSRF HMAC into the V2 design as if they were approved.

## 2. Boundary between the control plane and tenant database

ADR decision 2 gives each company its own PostgreSQL database. ADR decision 7 and control-plane schema §4 keep a separate control-plane database for registry, routing, provisioning, company access status, and platform operations.

### Control plane

Established by ADR §4 and §5 and by control-plane schema §6:

- Tenant identity.
- Provisioning status, exactly these six values: `requested`, `provisioning`, `migrating`, `ready`, `failed`, and `suspended`.
- Company access status: `onboard`, `active`, or `deactivated`. The column is `NOT NULL` and defaults to `onboard`. A new company starts as `onboard`. This is not a provisioning state.
- Routing metadata: which database serves the tenant, and references to database credentials. Those references are not company password hashes.
- Provisioning step, routing disposition, and the last schema revision successfully applied to this tenant database.
- Provisioning requests, provisioning attempts, and platform audit events.

`ready` means migrations succeeded and the first company administrator exists, so the database may be routed (ADR decision 14 and §5). It does not set `access_status` to `active`. Normal HRMS business APIs also require company access status `active` and the other authorization checks in ADR decisions 15–19. Provisioning success, failure, suspension, recovery, and compensation do not activate or deactivate the company (ADR §5; control-plane schema §9 and §12). Company `deactivated` and provisioning status `suspended` both block normal HRMS access. They are different states.

This tenant database does not store `tenants.status`, `access_status`, `provisioning_state`, or `routing_disposition`.

### Tenant database

Established by ADR decisions 5, 6, 11, 12, 13, and 16:

- Employee, salary, and salary-audit rows.
- Company user accounts and the company-assigned employee ID. The employee ID is unique within this tenant. It does not have to be unique across companies.
- Password hashes. The hash is a slow hash such as Argon2id. It is not plaintext.
- `employment_status`, which governs employee access. There is no separate employee `access_status`.
- The current company role used for protected requests. Do not trust a role embedded in the JWT (ADR decision 12).
- Refresh-session records. Section 6 states the settled rules: high-entropy opaque tokens, an HMAC-SHA-256 digest only, rotation, family-or-session reuse revocation, no concurrency grace period, multiple independent sessions, basic session and device metadata, `last_used`, and no IP history by default.

The access JWT and the raw refresh token are not stored in either database (ADR decision 13).

Login does not look up a control-plane user or membership. The company-specific subdomain selects one control-plane registry row. The initial deployment uses a tenant-specific subdomain under a shared domain (ADR decision 8). The employee ID and password are then checked in this database (ADR §6; control-plane schema §8). A person who works for two companies has two tenant-local accounts, one in each company’s database, reached by each company’s login URL (control-plane schema §7).

The first company administrator is created in this database. There is no cross-database foreign key to that account (ADR decision 14). The control plane records success as a succeeded `bootstrap_admin` provisioning request. It does not point at the account (control-plane schema §6 and §9). How that person proves identity, how the password is set, and who may start that request are unresolved (ADR §14; control-plane schema §16).

Which physical tables hold the company user, the password hash, the role, and the refresh-session digest is part of a later approved schema, except where section 3 already carries `employment_status` on `employees`. This proposal fixes the database they belong to and the rules those facts must satisfy.

## 3. Assessment tables carried forward

Verified from the current models. These are assessment shapes. V2 has not created a tenant copy of them.

### `employees`

`backend/app/models/employee.py` defines `employees` with:

- `id`, `bigint` identity, primary key.
- `employee_code`, `varchar(20)`, not null. Unique across the whole table today (`uq_employees_employee_code`).
- `full_name`, `country`, `department`, `job_title`.
- `employment_status`, constrained to `ACTIVE` or `INACTIVE` (`ck_employees_employment_status`).
- `created_at` and `updated_at`.

ADR decision 16 says employee access is governed by `employment_status`. Do not add a separate employee `access_status`. This proposal carries the assessment values `ACTIVE` and `INACTIVE` forward on that column. It does not rename them and does not add a second status column. It does not define a new permission matrix for those two values.

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
- After authentication, a role and permission check still decides what the user may do inside the company. Load the current role from this database. Do not trust a role embedded in the JWT (decision 9 and decision 12; ADR §6). A separate database does not replace that check.

Unresolved, and not chosen here:

- The role and permission matrix, including any starter role names (ADR §14; control-plane schema §16). This document does not add a role column with a fixed list of names. It records only that the check is tenant-local and is not the platform-operator permission.
- Whether the password hash and the company role live on the employee row or on a separate company-user row. ADR-001 requires both the employee ID and a company user account in this database. It does not say they are the same row.
- The first-administrator onboarding flow (ADR §14; control-plane schema §16).

A company role is not an elevated operator permission. Operator authentication stays unresolved and is not a table in this database (ADR §7 item 8 and §14; control-plane schema §4 and §16).

## 5. Employee access

ADR decision 16 governs employee access with the existing `employment_status` column in this database. Section 3 carries the assessment values `ACTIVE` and `INACTIVE`. This section does not add a column and does not define which of those values permits a request.

Established:

- Do not add a separate employee `access_status`.
- An employee’s access must respect both `employment_status` and the company’s current `access_status` in the control plane (decision 16). Section 7 states the request checks.
- There is no grace period for payslips, personal documents, or employment documents after employee deactivation (decision 17). Do not add a grace policy, a company-specific deactivation policy, a deactivation-deadline column, or `grace_until`.

Changing `employment_status` does not rewrite control-plane audit rows and does not change `tenants.status` or `tenants.access_status` (control-plane schema §13).

## 6. Refresh sessions

ADR decisions 12, 13, and 18 are established. This section records the session behavior. It does not name every physical column.

Established:

- Refresh tokens are high-entropy opaque tokens with a 7-day lifetime (decision 12). Ordinary protected business requests are authenticated with the access token. A refresh token is used only at the refresh endpoint to issue a new access token. Rotation and reuse protections for that exchange are enforced in this database.
- Access tokens are JWTs lasting 15 minutes. The claims are `sub`, `tenant_id`, `jti`, `iat`, `exp`, `iss`, and `aud`. Sign with RS256, include a `kid`, and publish a trusted JWKS endpoint. APIs verify with public keys and refresh JWKS when an unknown `kid` is encountered (decision 12).
- Auth cookies use `HttpOnly`, `Secure`, and `SameSite=Lax` as the initial defaults. Prefer host-only cookies rather than a shared parent-domain cookie (decision 12). Cookie names and `Path` are unresolved. See section 9.
- Store only an HMAC-SHA-256 digest of the refresh token, using a server-side secret, in this tenant database (decision 13). Never store the raw refresh token or the access JWT here or in the control plane. This digest is not the assessment SHA-256 hash of the raw token described in section 8.
- Refresh-token rotation is required. Reuse of a rotated token revokes only its affected token family or session, not unrelated sessions. There is no concurrency grace period (decision 13).
- An employee may hold multiple independent active sessions (decision 13).
- Store basic session and device metadata and `last_used`. Do not retain IP history by default (decision 13).
- Logout revokes the current refresh session and clears auth cookies. The access JWT may remain valid until its 15-minute expiry. Other device sessions remain active (decision 18). This database does not gain an access-token denylist.
- State-changing requests require a CSRF token and trusted `Origin` validation. Safe HTTP methods must not mutate state (decision 18). This database does not store CSRF tokens. The assessment HMAC in section 8 is not the V2 construction.
- The assessment `user_sessions` table is not this store. Section 8 says those rows are invalidated and are not copied.

The stored session must be revocable as one family or session without revoking the employee’s other sessions. This proposal does not assign column names to that grouping, to `last_used`, or to the basic device metadata. Section 9 does not reopen these rules. Cookie names and `Path` remain open there.

The current assessment store, for comparison only, is `backend/app/models/user_session.py`: a unique SHA-256 `token_hash`, `expires_at`, and nullable `revoked_at`, with no user id and no tenant id. `backend/app/services/sessions.py` issues `secrets.token_urlsafe(32)`, stores the SHA-256 hash, and rejects a missing, revoked, or expired row. That shape is verified current behavior. It is not the V2 refresh-session table.

## 7. Authorization and tenant-isolation invariants

These are ADR rules. This database has to be able to support them. This section does not add a control-plane column.

For a business request, ADR §7 and control-plane schema §10 require:

1. Resolve the tenant from the company-specific subdomain. An unknown URL fails closed and is not a directory of companies. The URL is not authorization.
2. At login, authenticate the company-assigned employee ID and password in this database. On a later protected business request, verify the access JWT with public keys from the trusted JWKS endpoint, using the claims in ADR decision 12. Refresh JWKS when an unknown `kid` is encountered. Load the current role from this database. Do not accept a refresh token as that request’s credential. The refresh endpoint is the only place a refresh token is exchanged for a new access token, and this database enforces rotation and reuse checks there.
3. Load provisioning status, company access status, and routing from the control plane on every protected request. Do not use a short-lived status cache (ADR decision 18). Do not load the company user, `employment_status`, or the refresh session from the control plane.
4. Open a connection only to this tenant database, and only when the authenticated identity, the token’s tenant binding, the resolved tenant, and this database agree. Fail closed on any disagreement (ADR decision 8).
5. Ignore any client-supplied tenant id or database name as authorization.
6. Never reuse a company token or a business database connection across tenants.

Fail closed when the tenant is missing, not `ready`, `failed`, or `suspended` (ADR §5 and §7 item 7). Also fail closed for normal HRMS business APIs when company access status is `onboard` or `deactivated`, even if the access JWT has not expired. An unexpired refresh token does not authorize those APIs. Do not change the provisioning status to `suspended` because the company is `onboard` or `deactivated`, and do not close or disrupt another tenant’s pool (control-plane schema §9 and §10).

There is no document-only grace path. Payslips, personal documents, and employment documents follow the same company `access_status`, provisioning status, and `employment_status` checks as other protected requests (ADR decision 17).

A cryptographically valid JWT is not enough (ADR decision 19). The protected request still enforces the current company access status, the current `employment_status`, the applicable permissions, and the current provisioning status. The permission matrix itself is unresolved (section 4).

Ordinary business connections must not use a PostgreSQL superuser. Runtime privileges for application queries stay separate from the privileges that create databases or apply migrations (ADR §7 items 9 and 10). Credential product, injection, and rotation remain unresolved. Company password hashes are not those database credentials.

## 8. Assessment authentication and session cutover

ADR-001 §9 decides the assessment-data cutover. The legacy login transition in control-plane schema §8 is a proposal. It is not an ADR decision.

Verified today:

- Login is `POST /api/v1/auth/login` in `backend/app/api/auth.py`. It checks `HR_MANAGER_USERNAME` and `HR_MANAGER_PASSWORD_HASH` through `backend/app/services/auth.py`. There is no user table.
- A successful login stores an opaque session hash in `user_sessions` and sets the `acme_session` cookie. That cookie is HttpOnly, SameSite=Lax, path `/`, with `Secure` taken from settings (`backend/app/api/auth.py`).
- The same login sets `acme_csrf`, which is not HttpOnly. `backend/app/services/csrf.py` builds an HMAC bound to the numeric session id. State-changing routes send it in `X-CSRF-Token`. Logout requires that CSRF check and then sets `revoked_at` (`backend/app/services/sessions.py`).
- Login also requires a trusted origin (`require_trusted_login_origin`).
- `changed_by` uses `HR_MANAGER_IDENTITY` only as an audit label. There is no user row to migrate.

Those cookie names, the SHA-256 session hash, and the CSRF HMAC are assessment behavior. They are not the V2 token or cookie design in sections 6 and 7.

Established by ADR-001 §9:

- Do not copy existing `user_sessions` rows into tenant refresh-session records. Invalidate them. They have no user and no tenant. Copying them would keep the single shared login. Control-plane schema §8 records the same instruction.
- Copy employees, salary records, and salary audit logs on a disposable rehearsal. Preserve primary keys and foreign keys. Leave `main` and the current assessment database unchanged until that rehearsal. Do not truncate the assessment database as part of writing this document.

Proposed transition from control-plane schema §8, not an ADR decision:

- V2 routes do not accept `HR_MANAGER_USERNAME` as a second login path.
- During a rehearsed cutover, create the first company administrator in the default tenant’s database. The password is a new Argon2id hash. The repository has never stored the plaintext password, so it cannot be copied. Do not create a control-plane user for that person. Creating that account in the tenant database, with no cross-database foreign key, is also ADR decision 14. The new Argon2id hash is the proposed transition.
- After that administrator exists, V2 company authentication reads only the tenant database named by the login URL. The environment variables remain for the assessment application on `main`.
- Do not keep a fallback that authenticates the configured HR manager when this database has no matching account. That fallback would skip tenant status and the URL-to-database agreement.

V2 cookie names are not required to be `acme_session` or `acme_csrf`. Cookie names and `Path` are unresolved (control-plane schema §16). `HttpOnly`, `Secure`, and `SameSite=Lax` are the initial defaults. Prefer host-only cookies rather than a shared parent-domain cookie (ADR decision 12).

## 9. Open decisions

Every item below needs an explicit approval before implementation treats it as decided. This section does not select one. Items that ADR-001 or the control-plane proposal already closed are not reopened.

| Topic | What stays open | What is already decided |
|---|---|---|
| Role and permission matrix | Names and permissions, including any starter roles (ADR §14; control-plane schema §16). | A company role check loads the current role from this database. It is not the operator permission and is not a JWT role claim (ADR decisions 9 and 12). |
| Company-user row shape | Whether the password hash and role live on the employee row or on a separate user row. The specific password-hash algorithm is not closed beyond the description below. | The account, employee ID, and a password hash live in this database (ADR decisions 5, 6, and 11). ADR-001 §6 describes a slow hash such as Argon2id. |
| First-administrator onboarding | How the person proves identity, how the password is set, and who may start `bootstrap_admin` (ADR §14). | The account is created here. No cross-database foreign key. Control-plane evidence is the succeeded provisioning request (ADR decision 14). |
| `changed_by` label | Which non-key string is copied at write time. | It stays a non-key string in this database, not a control-plane foreign key (control-plane schema §13). |
| Cookie names and `Path` | The cookie names and `Path` (ADR §14). | `HttpOnly`, `Secure`, and `SameSite=Lax` are the initial defaults. Prefer host-only cookies rather than a shared parent-domain cookie (decision 12). |
| Login URL key | Which control-plane `tenants` column the subdomain matches (control-plane schema §16). | The initial deployment uses a tenant-specific subdomain under a shared domain. That value selects a registry row and is not authorization (ADR decision 8). |
| Company access-status changes | Who may change `access_status`, which transitions among `onboard`, `active`, and `deactivated` are permitted, provisioning preconditions, and whether the change must be audited (ADR §7 item 8; control-plane schema §16). | The column is `NOT NULL`, defaults to `onboard`, and allows those three values. A new company starts as `onboard`. `ready` does not set `active`. `deactivated` blocks normal HRMS access and does not set provisioning status to `suspended`. |
| Platform-operator authentication | How operators authenticate (ADR §14). | The path is separate from company login and is not a table here. |
| Database hosting, credentials, pools, migration recovery, backup, and deletion | ADR §14 and control-plane schema §16. | They are control-plane and operational questions. This document does not decide them. |

Closed by ADR-001 and not left open here: multiple independent sessions, refresh-token HMAC-SHA-256 digests, rotation and family-or-session revocation, no concurrency grace period, JWT claims and RS256 with JWKS, logout of the current refresh session only, CSRF plus trusted `Origin` on state-changing requests, no short-lived company or tenant status cache, employee access through `employment_status`, and no document-access grace period.

This document proposes a tenant schema only. No application code, database schema, migration, or tenant provisioning has been changed.
