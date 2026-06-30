# Agent Context — Kudos Hackathon Project

This file is the primary briefing document for any sub-agent or human picking up this project.
Read this before touching any code.

---

## What this project is

**Kudos** is a peer-recognition web app built for the OpenTeams "Bounty Hunters" hackathon.
Employees give each other points tied to core values. Points accumulate from kudos, GitHub activity,
and CRM events. Points are redeemable in a swag catalog with a configurable approval workflow.

**Demo deadline:** July 20, 2026 (code), July 21–22 (5–10 min shareout).
**GitHub repo:** https://github.com/spectre-ns/ot-hackathon

---

## Tech choices (non-negotiable)

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.13 + FastAPI | Use miniconda Python, not system Python |
| DB | TinyDB (`kudos_db.json`) | No external server; single-file JSON |
| Thread safety | `threading.RLock()` in `app/db.py` | ALL reads AND writes go through it |
| Frontend | Vanilla JS/HTML/CSS | No React, no build step |
| HTTP client | `httpx` | For GitHub API calls |
| Test browser | Playwright with `channel="chrome"` | System Chrome |

---

## Running the project

```bash
# First time setup
cd /home/dahubley/source/repos/hackathon
source .venv/bin/activate          # venv built with ~/miniconda3/bin/python

# Reseed the database (wipes existing data)
python -m app.seed

# Start the server
uvicorn app.main:app --reload --port 8000

# Open http://localhost:8000
# Demo login: pick any employee from the dropdown — no credentials needed
# Admin users: Ada Lovelace, Grace Hopper
```

---

## Key invariants — never break these

1. **All TinyDB operations must acquire `_lock`** (the `threading.RLock` in `app/db.py`).
   FastAPI runs handlers in a threadpool. Without the lock, concurrent `seek()` calls on the
   shared file handle cause `JSONDecodeError` under load. Even read-only functions must lock.

2. **`CachingMiddleware` is NOT used** — it only flushes on `close()`, so data seeded in one
   process won't be visible to another. Use plain `JSONStorage` (the current setup).

3. **`giving_balance` is computed live** from calendar-month kudos — never store it. Same for
   `earned_points` and `spendable_points`.

4. **`spendable_points` = earned − committed** (pending + approved orders). This prevents
   users from over-spending while orders are in-flight.

5. **GitHub accumulation toggle is instant** — weights are always stored; `earned_points(uid)`
   conditionally includes them based on `settings.github_accumulation_enabled`. No re-sync needed.

---

## Where things live

```
app/
  main.py       — ALL routes (do not split into sub-routers without updating imports)
  db.py         — ALL database access (single source of truth for data shape)
  auth.py       — Session deps: current_user(), require_admin()
  config.py     — Env vars + helpers
  values.py     — 6 core values (colors + emoji)
  crm_events.py — 6 CRM event types + event_points()
  workflow.py   — State machine helpers
  schemas.py    — Pydantic request bodies
  seed.py       — Wipe + reseed

static/
  index.html    — HTML shell (login screen + app shell + modals)
  styles.css    — All CSS (OpenTeams palette variables at top)
  app.js        — SPA: routing, views, modals, API calls

docs/
  architecture.md   — Full system architecture reference
  agent-context.md  — THIS FILE — start here
  api-reference.md  — All API endpoints
  frontend-guide.md — Frontend patterns + adding new views

REQUIREMENTS.md  — Human-editable requirements (keep updated per standing instruction)
```

---

## Standing instructions from the user

- **"In this project ALWAYS update REQUIREMENTS.md when you see new requirements."**
  Add any new requirement to REQUIREMENTS.md before (or immediately after) implementing it.

- **Use sub-agents. Write documentation as you go to fuel those agents.**
  When spawning a sub-agent, pass relevant sections of `docs/` as context. Keep docs current
  so the next agent doesn't need to re-derive what was already figured out.

---

## Current status (as of June 30, 2026)

### Done
- Backend: all routes, data layer, auth, GitHub sync, CRM webhook, swag catalog, workflow engine, notifications
- Seed data: 10 employees, 15 kudos, 12 GitHub contribs, 12 CRM events, 8 swag items, 1 pending order
- Frontend: complete `app.js` rewrite covering all features
- `index.html`: Rewards nav, notification bell, artifact fields in give modal
- `styles.css`: swag grid, workflow editor, notification bell/dropdown, toggle switch, artifact pills
- `REQUIREMENTS.md`: updated with all features

### Remaining before demo
- [ ] Start server + reseed + manual smoke-test all views
- [ ] Playwright screenshot verification of all features
- [ ] Write README.md (setup instructions, GitHub OAuth config, AI-usage notes, demo script)
- [ ] Ensure GitHub repo is public and pushed

---

## Common sub-agent tasks

### "Verify the app works end-to-end"
Read `docs/agent-context.md` + `docs/architecture.md`. Start server, run `python -m app.seed`,
then use Playwright (`channel="chrome"`) to screenshot: login, feed, leaderboard, people,
a profile (with CRM + GitHub tabs), rewards/catalog, rewards/orders, admin settings,
admin CRM simulator, admin approvals, admin workflow editor.

### "Add a new API endpoint"
Read `app/main.py` + `app/db.py` + `app/schemas.py`. Add the Pydantic schema to `schemas.py`,
add the db function to `db.py` (always inside `with _lock:`), add the route to `main.py`.
Update `REQUIREMENTS.md`.

### "Add a new frontend view"
Read `docs/frontend-guide.md`. Add a route to `ROUTES` in `app.js`, add a nav link to
`index.html`, add component styles to `styles.css`. Follow the `avatarHTML` + `kudosCard`
patterns for consistency.

### "Write README"
Read `docs/agent-context.md` + `docs/architecture.md` + `REQUIREMENTS.md`. The README should
cover: what it is, setup steps (venv, pip, seed, run), GitHub OAuth config (optional),
demo walkthrough, AI tool usage disclosure, architecture blurb.
