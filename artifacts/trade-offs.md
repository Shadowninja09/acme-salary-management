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

Record further trade-offs when new decisions are made.
