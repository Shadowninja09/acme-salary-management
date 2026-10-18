# Engineering trade-offs

Add an entry when a decision is made during implementation. Do not restate the architecture document as if it were a new decision.

Established choices (already documented; do not reopen without a concrete conflict):

- FastAPI backend, React + Vite frontend, PostgreSQL, Alembic, SQLAlchemy
- Salary history by `effective_from`; corrections update a row and write an audit log
- No currency conversion; monthly pay annualized by multiplying by 12
- One configured HR Manager identity; no users table in the first release

## Log

_No implementation-time trade-offs recorded yet._
