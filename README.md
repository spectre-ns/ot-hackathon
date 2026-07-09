# OpenTeams Kudos

A peer recognition and rewards platform built for the **OpenTeams "Bounty Hunters" hackathon**. Kudos lets employees celebrate each other for going above and beyond — a great assist, calming a difficult client, stepping up during a crisis — and backs that recognition with a real points economy: give points to colleagues, earn points from peer kudos plus (optionally) GitHub activity and CRM events, and redeem points for swag through a configurable approval workflow.

Design is intentionally minimal (Airbnb-style whitespace and cards) using the OpenTeams brand palette, and the whole thing runs out-of-the-box with no external database or services to stand up.

![Python](https://img.shields.io/badge/python-3.14-blue) ![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688) ![TinyDB](https://img.shields.io/badge/database-TinyDB-lightgrey)

---

## Features

- **Peer-to-peer kudos** — recognize a colleague with points, a core value (Great Teammate, Client Hero, Crisis Crusher, Above & Beyond, Innovator, Mentor), a message, and an optional artifact link (PR, ticket, deal). Confetti included.
- **Three balances per person** — a monthly *giving allowance* (what you can hand out), *earned points* (what you've accumulated), and *spendable points* (earned minus points tied up in swag orders).
- **GitHub integration** — OAuth login, automatic points for merged PRs and closed issues via the GitHub Search API, admin-configurable weights, and an accumulation toggle so contributions can be tracked informationally without awarding points.
- **CRM integration** — a webhook endpoint (`POST /api/crm/event`, secured by an `X-CRM-Key` header) that any CRM can call, six built-in event types (deal closed, contract renewed, escalation resolved, positive NPS, ticket resolved, customer call) with admin-configurable weights, idempotent on `reference_id`, plus an in-app simulator for demos. A Salesforce Flow/Apex adapter path is documented in code.
- **Recognition feed and people directory** — reverse-chronological feed with emoji reactions and individual profiles with kudos/GitHub/CRM history tabs.
- **Admin statistics dashboard** — org-wide totals, points-by-source breakdown, top earners, and recognition/role/order breakdowns, visible to Admins and SuperAdmins only (no public leaderboard, to avoid gaming the recognition system).
- **Activity feed** — a combined, filterable stream of everyone's GitHub and CRM contributions, with an "Award kudos" button that pre-fills the give-kudos modal.
- **Swag catalog & redemption** — admin-managed catalog with point costs, optional stock limits, image thumbnails, and inline editing.
- **Configurable, JIRA-inspired workflow engine** — orders move through an editable state machine (default: Pending → Under Review → Approved → Shipped, or Rejected). Admins can add/remove states and transitions via an interactive visual diagram editor, and every transition is written to a full audit log.
- **Notifications** — an in-app bell with unread counts, a dedicated notification stream page, and deep links into the relevant admin/user views.
- **Three-tier roles** — User, Admin, and SuperAdmin, with a role-management UI for SuperAdmins.
- **Automatic dark mode** — follows the OS/browser `prefers-color-scheme`, no manual toggle.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.14, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn |
| Database | [TinyDB](https://tinydb.readthedocs.io/) — a single embedded JSON file (`kudos_db.json`), no external DB server |
| Concurrency | A module-level `threading.RLock` serializes all reads/writes |
| Auth | GitHub OAuth (optional) + a password-free demo login; httponly cookie sessions |
| Frontend | Vanilla HTML/CSS/JS single-page app — no framework, no build step |
| Tests | pytest, 180+ tests across auth, kudos, feed, statistics, activity, swag, workflow, CRM, GitHub, notifications, settings, and roles |

## Getting started

### Prerequisites

- Python 3.14 (a Miniconda install is recommended if your system Python is older)

### Setup

```bash
python -m venv .venv

# macOS/Linux
.venv/bin/pip install -r requirements.txt

# Windows
.venv\Scripts\pip install -r requirements.txt
```

### Seed the database

Populates `kudos_db.json` with 10 employees, kudos, GitHub/CRM contributions, and swag items so the app isn't empty on first load.

```bash
# macOS/Linux
.venv/bin/python -m app.seed

# Windows
.venv\Scripts\python -m app.seed
```

### Run the server

```bash
# macOS/Linux
./scripts/start.sh          # add --reload for auto-reload during development

# Windows
powershell -ExecutionPolicy Bypass -File scripts/start.ps1   # add -Reload for auto-reload

# or, from either OS, once the venv is active
uvicorn app.main:app --reload --port 8000
```

Then open **http://localhost:8000**. Use **demo login** to sign in as any seeded employee — no GitHub app or credentials required. Two seeded users (Ada Lovelace, Grace Hopper) are SuperAdmins if you want to explore the admin panel, role management, and workflow editor.

A `Makefile` is also available on macOS/Linux (`make test`, `make seed`, `make dev`).

### Running tests

```bash
# macOS/Linux
.venv/bin/python -m pytest tests/ -v

# Windows
.venv\Scripts\python -m pytest tests/ -v
```

## Configuration

All configuration is via environment variables (see `app/config.py`); everything has a safe default so the app runs in "demo mode" without any of it set.

| Variable | Default | Purpose |
|---|---|---|
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | *(empty)* | Enables real GitHub OAuth login. Create an OAuth app at github.com/settings/developers with callback `{BASE_URL}/auth/github/callback`. |
| `GITHUB_TOKEN` | *(empty)* | Personal access token used as a fallback for syncing contributions when a user logged in via demo mode. |
| `BASE_URL` | `http://localhost:8000` | Public URL used to build the OAuth callback. |
| `DATABASE_FILE` | `kudos_db.json` | Path to the TinyDB JSON store. |
| `SECRET_KEY` | `dev-secret-change-me` | Session signing secret — set a real value outside local demo use. |
| `DEFAULT_MONTHLY_ALLOWANCE` | `100` | Points each employee can give away per month. |
| `DEMO_LOGIN` | `true` | Set to `false` to disable the no-credential demo login (e.g. once real OAuth is configured for production). |
| `SLACK_WEBHOOK_URL` | *(empty)* | **Seeds** the Slack [Incoming Webhook](https://api.slack.com/messaging/webhooks) URL the first time settings are created. The live value is normally set in **Admin → Settings** (stored in the DB); the UI value takes precedence. When set, each kudos is announced to that channel. Left empty, Slack posting is disabled and a Slack outage can never affect giving kudos. |

The CRM webhook key and all GitHub/CRM point weights are configured at runtime from the **Admin → Settings** panel rather than environment variables.

## Project structure

```
app/
  main.py          FastAPI routes: auth, kudos, feed, activity, admin statistics,
                    GitHub sync, CRM webhook, settings, swag, workflow, notifications
  db.py             TinyDB repository layer — every read/write goes through here
  auth.py           Session dependency, require_admin()/require_superadmin(), GitHub user upsert
  config.py         Environment-driven configuration
  values.py         The 6 core recognition values
  crm_events.py     The 6 CRM event types and their configurable point weights
  github_sync.py    GitHub Search API sync for merged PRs / closed issues
  workflow.py       Swag order state machine helpers (states, transitions, audit log)
  schemas.py        Pydantic request models
  seed.py           Wipes and reseeds the database with demo data

static/
  index.html        SPA shell
  styles.css        OpenTeams palette, Airbnb-minimal styling
  app.js            Client-side router, API client, and all view rendering

tests/              pytest suite (one file per feature area)
scripts/            start.sh / start.ps1 dev-server launchers
docs/
  requirements.md   Living, human-editable requirements checklist
  architecture.md   Deeper architecture notes, data flows, and known constraints
  api-reference.md  Endpoint reference
  frontend-guide.md Frontend conventions and patterns
.claude/skills/     Repo automation skills (seed, server, test, requirements, update-docs)
```

For a deeper dive into module responsibilities, data flows (giving kudos, swag orders, CRM events), and known constraints, see [docs/architecture.md](docs/architecture.md). For the full, checkbox-tracked feature list and what's explicitly out of scope, see [docs/requirements.md](docs/requirements.md).

## Known constraints

- TinyDB is single-process only — fine for this hackathon/demo scope, but not multi-process or load-balancer safe. A production deployment would move to Postgres or similar.
- Session tokens are random UUIDs with no JWT signing or expiry.
- Swag fulfilment stops at the "Shipped" workflow state — no physical fulfilment or gift-card issuing is implemented.
- In-app notifications are the primary channel. Outbound **Slack** kudos announcements are supported via an Incoming Webhook, configured in Admin → Settings (or seeded from `SLACK_WEBHOOK_URL`); disabled by default. Email/push notifications and a bidirectional Slack bot remain out of scope.
