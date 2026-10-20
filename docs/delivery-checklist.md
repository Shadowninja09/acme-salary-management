# Delivery checklist

Items stay unchecked until the work is actually done. Do not fill in URLs, dates, or results here before they exist.

## Deployment

- [ ] Choose a deployment target and record the trade-off in `artifacts/trade-offs.md`.
- [ ] Document verified run, migrate, seed, and environment-variable steps in the README (only after they work).
- [x] Keep secrets out of git (`.env` is gitignored).
- [ ] Apply migrations on the deployed database.
- [ ] Seed about 10,000 synthetic employees on the deployed environment, or document why a smaller demo dataset is used.
- [ ] Confirm the HR Manager can manage employees, record/correct salaries, and view analytics against stored data.
- [ ] Record the public URL here when the app is running:

```text
Deployed URL: (not deployed yet)
```

## Video demonstration

- [ ] Record a short walkthrough of the deployed (or otherwise reviewer-accessible) application.
- [ ] Show employee search/list against a large dataset (pagination).
- [ ] Show creating or updating a salary and that history/audit is visible.
- [ ] Show analytics answering how the org pays people (reporting date, employment status, currency).
- [ ] Store or link the video in a way reviewers can open without extra credentials, and add the link here:

```text
Demo video: (not recorded yet)
```

## Repository submission

Git history on `main` includes incremental commits from documentation through persistence, auth, salary HTTP, a 1,000-employee development seed, frontend workflows, and correction history (see `git log`). Deployment and a demo video are still pending, so this item stays unchecked until the full evolution through deploy is present.

- [ ] Incremental commits show how the solution evolved (docs → foundation → features → tests → seed → UI → deploy).
- [ ] `artifacts/ai-usage.md` has real prompt/usage notes from development.
- [ ] `artifacts/trade-offs.md` records decisions made during implementation.
- [ ] `artifacts/performance.md` records measurements taken on seeded data (if any).
- [ ] README matches the real stack, layout, and working commands (keep in sync with the repository; last aligned with salary HTTP, frontend, and 1,000-employee seed).
- [ ] Tests covering core behavior are present and documented (backend pytest under `backend/tests/`; frontend lint/build only).
- [ ] Share the Git repository link by replying to the Incubyte assessment email.

```text
Repository URL: (not submitted yet)
```
