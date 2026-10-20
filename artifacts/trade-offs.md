# Engineering trade-offs

Add an entry when a decision is made during implementation. Do not restate the architecture document as if it were a new decision.

Established choices (already documented; do not reopen without a concrete conflict):

- FastAPI backend, React + Vite frontend, PostgreSQL, Alembic, SQLAlchemy
- Salary history by `effective_from`; corrections update a row and write an audit log
- No currency conversion; monthly pay annualized by multiplying by 12
- One configured HR Manager identity; no users table in the first release

## Log

| Date | Decision | Why | Trade-off |
|---|---|---|---|
| 2026-10-19 | Persist opaque session tokens as SHA-256 hashes; send the raw token in an HttpOnly `acme_session` cookie (`SameSite=Lax`, configured `Secure` and max-age). Protect browser state-changing requests with a session-bound CSRF cookie/header pair. Validate login with exact trusted origins because login has no session yet. | Server-side sessions can expire and revoke without storing reusable raw tokens. HttpOnly reduces token theft via JavaScript. CSRF is still needed with `SameSite=Lax`. Login CSRF cannot use a session-bound token, so origin allowlisting is explicit rather than silently skipped. Audit identity stays a separate configured string. | Cookie auth depends on correct `Secure` and trusted-origin configuration before a real frontend is deployed. CSRF cookies are readable by JavaScript by design. Origin/Referer checks fail closed if browsers omit both. This is not a multi-user authorization model. |
| 2026-10-19 | Salary correction `PATCH`es the existing `salary_records` row and writes an UPDATE audit; it does not insert a replacement salary. | Requirements treat ordinary changes as new effective dates and corrections as edits with an audit trail. Unique `(employee_id, effective_from)` stays one row per date. | History is the current rows, not a full version table. Previous values live in `salary_audit_logs`, not extra salary rows. |
| 2026-10-19 / 2026-10-20 | Uniqueness is the database constraint. A correction may keep its own `effective_from`. A change onto another of the same employee’s dates is 409. | PostgreSQL unique indexes do not treat a row as a duplicate of itself. Tests (`test_correct_salary_keeps_existing_effective_date`, duplicate-date 409 cases) lock that in. | Callers must not pre-reject “date already on this row.” There is no application-level date query that excludes `salary_id`; the database is authoritative. Not load-tested at 10k employees. |
| 2026-10-20 | `GET .../salary-corrections` returns UPDATE audits only (join to `salary_records` for that employee). CREATE audits are omitted. | The UI needs correction timestamp, old/new values, reason, and `changed_by`. CREATE has null reason/`old_values`. Reuses `ix_salary_audit_logs_salary_record_id`; no new table. | Creation events are not shown in that list. Empty list after create-only is expected. No audit HTTP mutation API. |
| 2026-10-19 | Directory search/status filter runs in the browser on the current `limit`/`offset` page. | Avoided inventing a backend search contract the employee list API does not provide (`limit`/`offset` only). | Matches can miss employees on other pages. Server-side search remains a requirement gap. |
| 2026-10-19 | Development seed default is 1,000 employees (`--count`), not 10,000. | Safer local runs, still exercises mixed salaries/statuses. Script refuses `acme_test`. | Does not meet the ~10,000 assessment seed by default. No 10k performance numbers recorded. |
| 2026-10-19 | Vite dev server proxies `/api` to `http://127.0.0.1:8000`. The frontend copies `acme_csrf` into `X-CSRF-Token` on POST/PATCH except login; GET does not send CSRF. | Same-origin cookies during local UI work without a CORS setup. Login stays origin-checked, not CSRF-header-checked. | Production still needs matching trusted origins and `Secure` cookies. Proxy is a development convenience, not a deployment architecture. Unverified in production. |

Record further trade-offs when new decisions are made.
