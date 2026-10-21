# Performance findings

**Measured results:** none. Do not treat the notes below as timings or capacity claims.

The assessment target is about **10,000** employees. The development seed (`backend/scripts/seed_dev_data.py`) defaults to **1,000** (`--count`). Directory search (`q`) and employment-status (`status`) filters are **implemented server-side** on `GET /api/v1/employees`. No query or UI **timings** against a 10,000-row dataset have been recorded. Design rules (pagination, Decimal amounts, indexes in `docs/database-design.md`) are expectations, not measurements.

## Suggested later checks (not yet run)

These are benchmarks of existing behavior, not a backlog of missing features.

- Employee list with `limit`/`offset` on ~10,000 rows
- Directory search and status filters (`q`, `status`) on ~10,000 rows
- Applicable-salary lookup (`GET .../salaries/as-of`) for a reporting date
- Correction-history list (`GET .../salary-corrections`) for an employee with many UPDATE audits
- Session lookup by `token_hash`
- One analytics query (active headcount and grouped min/avg/max by currency and pay frequency) over a 10,000-row seed

## Log

_No measurements recorded yet._
