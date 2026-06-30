# Kudos — Requirements

A living, human-editable requirements doc for the **Bounty Hunters: Kudos Program** hackathon
submission. Checkboxes track status — tick/untick freely, add, reword, or delete bullets.

Legend: `[x]` done · `[ ]` planned / not yet built · ⛔ explicitly out of scope · ❓ open question

---

## 1. Goal & context (from the brief)

- [x] Let employees **recognize colleagues** for going above and beyond (great friend, handling
  difficult clients, critical help during a crisis).
- [x] A **point system** backing the recognition (design left to our discretion).
- [x] Take design inspiration from the **Nectar** platform.
- [x] Be a **standalone web app** (chosen integration approach).
- [x] Point **redemption** for swag / gift cards — swag catalog with approval workflow implemented.
- Logistics (not product features, but tracked):
  - [ ] Code submitted to a **personal GitHub repo** by **midnight CST, July 20, 2026**.
  - [ ] **5–10 min shareout** prepared (Tue Jul 21 or Wed Jul 22).

---

## 2. Explicit requirements (asked for directly)

### Core platform
- [x] **Standalone web app** interface (not Slack-first).
- [x] **Python backend (FastAPI)**.
- [x] **NoSQL database** — using **TinyDB** (embedded JSON document store, zero external server).
- [x] **Polished, intuitive UX** as a priority.
- [x] **OpenTeams color palette** (navy `#000F3A`, brand blue `#4D75FE`, coral `#FF8A69`, gold `#FAA944`).
- [x] **Airbnb-style minimal** frontend (whitespace, white cards, hairline borders, restrained color).
- [x] This **human-editable requirements document** (Markdown bullets, implicit + explicit).

### GitHub integration
- [x] **GitHub login** for users (OAuth), so accounts map to GitHub identities.
- [x] **Automatic kudos from GitHub activity**: award points for **merged PRs** and **closed issues**.
- [x] **Configurable weights** for how many points a PR vs. an issue is worth (admin-tunable).
- [x] **GitHub accumulation toggle**: admin can enable/disable whether GitHub activity auto-awards
  points. When disabled (manual mode), contributions are informational only; points come from
  peer kudos. Toggle takes effect instantly — no re-sync required.
- [x] **Per-event weights stored always** — toggling accumulation on/off does not lose weight config.
- [x] **Manual kudos** that can be sent **outside of GitHub** (peer-to-peer recognition).

### CRM integration
- [x] **CRM webhook endpoint** (`POST /api/crm/event`, secured by `X-CRM-Key` header) — accepts
  events from any CRM that can send HTTP webhooks.
- [x] **Six CRM event types**: `deal_closed` (25 pts), `contract_renewed` (20), `escalation_resolved` (15),
  `nps_positive` (10), `ticket_resolved` (8), `customer_call` (5) — all weights admin-configurable.
- [x] **Admin CRM Simulator** — fire a test CRM event from the UI, see the result live.
- [x] **Salesforce future integration path** documented in code comments — Flow/Apex trigger + Named
  Credential + HTTP Callout Action posting to `/api/crm/event` with `X-CRM-Key`.
- [x] **Idempotency** — repeated webhook calls for the same `reference_id` refresh, not double-award.

### Artifact traceability
- [x] Each kudos can carry an optional **artifact URL** + **label** linking to the source PR, ticket,
  deal, or other reference.
- [x] Artifacts are rendered as clickable pills on the kudos feed card.
- [x] "Award kudos" button on a user's GitHub contributions tab **pre-fills** artifact fields.
- [x] CRM contributions store an `artifact_url` linking back to the CRM record.

### Swag catalog & point redemption
- [x] **Swag catalog** — admin-managed list of items, each with a point cost and optional stock limit.
- [x] **Spendable points** = earned points minus points committed to pending/approved orders (prevents
  over-spending; approved but not shipped orders are still "reserved").
- [x] Users can **redeem swag** by placing an order (deducted from spendable balance immediately).
- [x] Orders enter a **configurable approval workflow** before fulfillment.
- [x] Admin can view **all orders** and **pending approvals** in the Admin panel.
- [x] Admin can **add swag items** (name, description, cost, stock, availability) from the Admin panel.

### Configurable workflow manager (JIRA-inspired)
- [x] **State machine** stored in TinyDB and fully editable via the admin UI.
- [x] **Default workflow**: Pending → Under Review → Approved → Shipped | Rejected.
- [x] Admin can **add states** (name, color, terminal flag) and **add transitions** (from, to, label,
  requires-reason flag) without writing code.
- [x] Admin can **delete states** and **delete transitions** (initial state is protected from deletion).
- [x] Each order transition is written to a **full audit log** (who, from, to, reason, timestamp).
- [x] **SVG workflow diagram** rendered live in the admin panel — updates as states/transitions change.
- [x] Transitions can be marked **requires_reason** — UI prompts for a note before advancing.

### Notification system
- [x] **In-app notification bell** in the topbar with unread count badge.
- [x] **Notification dropdown** — lists recent notifications with read/unread state; marks all read on open.
- [x] **Admin notified** when a new swag order is placed.
- [x] **Order owner notified** when an admin transitions their order to a new state.
- [x] Notifications stored in TinyDB, retrieved per-user, with `read` flag.

---

## 3. Implicit requirements (inferred from brief + decisions)

### Recognition & points model
- [x] **Three distinct balances** per person:
  - [x] **Giving allowance** — points each employee can give away, **resets monthly** (default 100).
  - [x] **Earned points** — accumulate from kudos received + CRM events + (optionally) GitHub activity.
  - [x] **Spendable points** — earned minus committed (pending + approved swag orders).
- [x] Giving is **budget-constrained** — can't give more than your monthly allowance.
- [x] Can't give kudos **to yourself**.
- [x] Each kudos has: recipient, **point amount**, a **core value/category**, **message**, optional **artifact link**.
- [x] **Core values**: Great Teammate, Client Hero, Crisis Crusher, Above & Beyond, Innovator, Mentor.

### Social / engagement
- [x] **Recognition feed** — public, reverse-chronological wall of kudos.
- [x] **Emoji reactions** on kudos (toggle on/off, one per emoji per person).
- [x] **Leaderboard** — top earners, with **This month** and **All time** views.
- [x] **People directory** and **individual profiles** (points, value breakdown, history).
- [x] **Profile tabs**: Kudos received · GitHub contributions · CRM contributions.
- [x] **Company stats** (total kudos, points awarded, people recognized, CRM events).
- [x] A **celebratory moment** on giving kudos (confetti) — reinforces the positive ritual.

### GitHub integration
- [x] Pull a user's **merged PRs** and **closed issues** via the GitHub Search API.
- [x] Convert each to points using configurable weights; **never double-count** on re-sync.
- [x] Re-syncing **refreshes points** if weights changed.
- [ ] ❓ Decide **scope of sync**: all public activity vs. specific org/repos only.
- [ ] ❓ Consider **PR reviews / approvals** as a future weighted contribution type.

### Auth, roles, sessions
- [x] **Cookie-based sessions** (httponly) after login.
- [x] **Demo-login fallback** — pick any seeded employee; no GitHub app required.
- [x] **Admin role** — can edit settings, manage workflow, manage swag catalog, approve orders.
- [ ] ❓ How are **admins** designated in real use (config, first user, SSO group)?

### Non-functional / quality
- [x] **Ease of use** — intuitive, minimal interface (judging criterion).
- [x] **Maintainability** — small, documented modules; clear data layer; single codebase.
- [x] **Runs out-of-the-box** — `pip install` + seed + run; no external DB/server to stand up.
- [x] **Concurrency-safe** data access (module-level `threading.RLock` serializes all reads and writes).
- [x] **Seed data** — 10 employees, 15 kudos, 12 GitHub contributions, 12 CRM events, 8 swag items.
- [ ] **README / setup docs** and a **demo script** for the shareout.
- [ ] ❓ **Deployment** target — local-only for demo, or hosted somewhere?

---

## 4. Out of scope (for now)

- ⛔ Real **Slack** (or other chat) integration — noted as a possible future integration.
- ⛔ **Email / push notifications** — in-app only.
- ⛔ Production-grade **auth hardening**, multi-tenant, audit logging.
- ⛔ Migration to a **server-based DB** (Postgres/Mongo) — TinyDB sufficient for hackathon.
- ⛔ Swag **physical fulfilment** or gift-card issuing — workflow stops at "Shipped" state.

---

## 5. Open questions / decisions to revisit

- [ ] ❓ Final **core-values list** and copy — confirm with stakeholders.
- [ ] ❓ **Monthly allowance** amount and whether it varies by role/tenure.
- [ ] ❓ **Anti-gaming**: caps per recipient, manager approvals, or leave it open & trust-based?
- [ ] ❓ GitHub sync **org/repo scoping** and trigger model (manual vs. scheduled).
- [ ] ❓ How **admins** are assigned in real deployment.
- [ ] ❓ **Hosting / deployment** for the live demo.
- [ ] ❓ Connect to **real Salesforce** (documented adapter pattern exists in code).
- [ ] ❓ **CRM API key rotation** — how will the key be distributed/rotated?

---

## 6. Tech stack (as built)

- **Backend:** Python 3.13 + FastAPI; Uvicorn server.
- **Data:** TinyDB (JSON document store) — single `kudos_db.json` file; tables: users, kudos,
  reactions, github_contributions, crm_contributions, settings, sessions, swag_items, swag_orders,
  workflow, notifications.
- **Thread safety:** module-level `threading.RLock()` wraps ALL reads and writes.
- **Auth:** GitHub OAuth (optional) + demo login; httponly cookie sessions.
- **GitHub:** `httpx` against the GitHub Search API for merged PRs / closed issues.
- **CRM:** Webhook endpoint + 6 event types + admin simulator; Salesforce adapter pattern documented.
- **Workflow:** JIRA-inspired state machine stored in TinyDB; full transition audit log per order.
- **Frontend:** Vanilla HTML/CSS/JS SPA (no build step), OpenTeams palette, Airbnb-minimal styling.
- **venv:** `~/miniconda3/bin/python -m venv .venv` (requires Python 3.13 from Miniconda, not system Python).

---

## 7. File map

```
app/
  main.py          — All FastAPI routes (auth, kudos, feed, GitHub, CRM, swag, workflow, notifications)
  db.py            — TinyDB repository layer (all reads + writes; thread-safe RLock)
  auth.py          — Session dependency; require_admin(); upsert_github_user()
  config.py        — Env vars; github_oauth_enabled() helper
  values.py        — 6 core values with colors
  crm_events.py    — 6 CRM event types, configurable weights, event_points()
  workflow.py      — Workflow state machine helpers (add/delete states & transitions)
  schemas.py       — Pydantic request body models
  seed.py          — Wipe + reseed with 10 employees, 15 kudos, contributions, swag, orders

static/
  index.html       — HTML shell (login, topbar with notif bell + Rewards nav, give modal)
  styles.css       — OpenTeams palette, Airbnb-minimal + swag/workflow/notification styles
  app.js           — Vanilla JS SPA: feed, leaderboard, people, profile, rewards, admin

requirements.txt   — Python dependencies (fastapi, uvicorn, pydantic, httpx, tinydb)
requirements.md    — This file
```
