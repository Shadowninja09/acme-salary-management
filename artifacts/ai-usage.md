# AI usage log

Record entries when AI tools are used for design, implementation, tests, or review.

| Date | Task | Tool | Prompt / instruction (summary) | Outcome |
|---|---|---|---|---|
| 2026-10-19 | Employee persistence (model, Alembic migration, tests) and follow-up test-fixture review | Cursor | Implement SQLAlchemy `Employee` and handwritten Alembic migration; add persistence tests gated on `TEST_DATABASE_URL`. Review model/migration consistency, constraints, timestamps, and test isolation. Tighten `db_session` cleanup and the timestamp assertions. | **Implemented:** employee model, first migration, persistence tests. **Reviewed file by file** (not from the agent summary alone): model vs migration, CHECK/UNIQUE constraints, timestamp defaults, and that tests do not use blanket table deletes. **Changed after review:** `db_session` rolls back then closes (no `DELETE FROM employees`); timestamp test asserts timezone-aware values and `created_at == updated_at`. **Verified:** integration tests against dedicated `acme_test` (not the app database); **6 passed**. Committed as `d3962bc` (`feat: add employee persistence and database migrations`). |
