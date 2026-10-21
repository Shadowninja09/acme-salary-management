# Delivery checklist

Items stay unchecked until the work is actually done. Do not fill in URLs, dates, or results here before they exist.

## Deployment

- [ ] Choose a deployment target and record the trade-off in `artifacts/trade-offs.md`.
- [ ] Document verified run, migrate, seed, and environment-variable steps in the README (only after they work).
- [x] Keep secrets out of git (`.env` is gitignored).
- [ ] Apply migrations on the deployed database.
- [x] Verified **local** 10,000-employee demo database (not a deployed environment). Read-only inspection of `localhost:5432/acme_salary` on 2026-10-21 found 10,000 employees (`EMP-000001`–`EMP-010000`), 18,000 salary records, 18,000 `CREATE` audit records, and 1,000 employees with no salary records (Alembic `0004_create_user_sessions`). The seed script skips existing employee codes and does not repair missing salaries or remove extra rows; rerunning `--count 10000` is not a full reset. This box does not claim a deployed host was seeded.
- [ ] Confirm the HR Manager can use the paginated directory, open employee details, record or correct salaries, and view analytics against stored data (there is no employee-create or employee-update UI).
- [ ] Record the public URL here when the app is running:

```text
Deployed URL: (not deployed yet)
```

## Video demonstration

- [ ] Record a short walkthrough of the deployed (or otherwise reviewer-accessible) application.
- [ ] Show employee list against a large dataset (pagination). If search or status filters are shown, they are **dataset-wide** (`q` and `status` on `GET /api/v1/employees`).
- [ ] Show creating or **correcting** a salary and that history / UPDATE audit is visible.
- [ ] Show analytics answering how the org pays people (reporting date, **active** employees, currency **and** pay frequency kept separate).
- [ ] Store or link the video in a way reviewers can open without extra credentials, and add the link here:

```text
Demo video: (not recorded yet)
```

## Repository submission

Git history on `main` includes incremental commits from documentation through persistence, auth, salary HTTP, a 1,000-employee development seed, frontend workflows, correction history, country–currency validation, HR UI and session handling, and Vitest coverage (see `git log`). Deployment and a demo video are still pending, so the “through deploy” item stays unchecked.

- [ ] Incremental commits show how the solution evolved (docs → foundation → features → tests → seed → UI → deploy).
- [ ] `artifacts/ai-usage.md` has real prompt/usage notes from development.
- [ ] `artifacts/trade-offs.md` records decisions made during implementation.
- [ ] `artifacts/performance.md` records measurements taken on seeded data (if any).
- [ ] README matches the real stack, layout, and working commands (keep in sync with the repository).
- [x] Tests covering core behavior are present in the repository (backend pytest under `backend/tests/`; frontend `npm test` / lint / build). This box does not claim deployment or that tests were re-run after the latest implementation commits.
- [ ] Share the Git repository link by replying to the Incubyte assessment email.

```text
Repository URL: (not submitted yet)
```
