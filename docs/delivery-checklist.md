# Delivery checklist

Items stay unchecked until the work is actually done. Do not fill in URLs, dates, or results here before they exist.

## Deployment

- [ ] Choose a deployment target and record the trade-off in `artifacts/trade-offs.md`.
- [ ] Document verified run, migrate, seed, and environment-variable steps in the README (only after they work).
- [x] Keep secrets out of git (`.env` is gitignored).
- [ ] Apply migrations on the deployed database.
- [x] Seed about 10,000 synthetic employees on the deployed environment, or document why a smaller demo dataset is used. Local assessment database `localhost:5432/acme_salary` was seeded with `--count 10000` (exit 0): 10,000 employees (`EMP-000001`–`EMP-010000`); this run created 9,000 and skipped 1,000 existing codes. This box does not claim a deployed host was seeded.
- [ ] Confirm the HR Manager can use the paginated directory, open employee details, record or correct salaries, and view analytics against stored data (there is no employee-create or employee-update UI).
- [ ] Record the public URL here when the app is running:

```text
Deployed URL: (not deployed yet)
```

## Video demonstration

- [ ] Record a short walkthrough of the deployed (or otherwise reviewer-accessible) application.
- [ ] Show employee list against a large dataset (pagination). If search is shown, it is **page-local**, not dataset-wide.
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
