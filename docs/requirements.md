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
- [x] **Browser history navigation** — back and forward buttons work correctly; each route change pushes a history entry and `popstate` restores the correct view and arguments.

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
- [x] **CRM auto-accumulation toggle** — admin can enable/disable whether CRM events auto-award points.
  When disabled, events are recorded but informational only. Defaults to ON (mirrors GitHub toggle).
  Toggle correctly gates CRM points in both the "all-time" and "this month" leaderboard periods.
- [x] **Admin CRM Simulator** — fire a test CRM event from the UI, including an artifact URL linking
  to the source CRM record (opportunity, case, etc.).
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
- [x] Admin can **edit swag items inline** — each catalog row shows a description textarea, cost
  input, stock select ("Unlimited" / "Track stock" with optional qty), availability toggle, and
  Save button directly in the table; no separate expand panel or edit button required.
- [x] **Swag card image thumbnails** — each catalog card shows a large visual thumbnail; falls back to
  a styled emoji on a colored background if no `image_url` is set.
- [x] **Visual workflow stepper on orders** — each order card (user "My Orders" tab and admin Approvals
  tab) shows a horizontal progress bar through all workflow states, color-coded and labeled.
- [x] **Swag cart & grouped checkout** — users add multiple swag items (with quantities) to a client-side
  cart and check out via `POST /api/swag/order`; the cart becomes a single grouped order carrying all
  line items, approved/shipped as one unit through the existing workflow. The legacy single-item endpoint
  `POST /api/swag/{id}/order` remains for backward compatibility.
- [x] **Stock enforcement** — placing an order reserves (decrements) stock on finite-stock items; orders
  exceeding available stock are rejected with HTTP 409, and rejecting an order restores its reserved
  stock. Unlimited-stock items (`stock = null`) are never gated.

### Configurable workflow manager (JIRA-inspired)
- [x] **State machine** stored in TinyDB and fully editable via the admin UI.
- [x] **Default workflow**: Pending → Under Review → Approved → Shipped | Rejected.
- [x] Admin can **add states** (name, color, terminal flag) without writing code.
- [x] Admin can **delete states** and **delete transitions** (initial state is protected from deletion).
- [x] Each order transition is written to a **full audit log** (who, from, to, reason, timestamp).
- [x] **Interactive visual workflow diagram** — click a state to select it, click another state to
  draw a transition arrow (prompts for label and requires-reason flag), hover states and arrows to
  reveal delete buttons directly on the diagram.
- [x] Transitions can be marked **requires_reason** — UI prompts for a note before advancing.
- [x] **Styled transition creation dialog** — clicking a state in the workflow diagram to draw a
  transition opens a `.modal-overlay` / `.modal-card` dialog (label input + "Requires a reason"
  toggle; Enter to submit, Escape or overlay-click to cancel) instead of browser `prompt()`.

### Notification system
- [x] **In-app notification bell** in the topbar with unread count badge.
- [x] **Notification stream page** — clicking the bell navigates to a full `/notifications` stream page; marks all unread on open.
- [x] **Admin notified** when a new swag order is placed.
- [x] **Order owner notified** when an admin transitions their order to a new state.
- [x] Notifications stored in TinyDB, retrieved per-user, with `read` flag.
- [x] **Notification deep-link navigation** — clicking a notification routes to the relevant action (approval notifications → Admin panel Approvals tab).
- [x] **Full notification stream page** — clicking the bell opens a dedicated notification stream page, not just a dropdown.
- [x] **Seeded notifications** — seed data includes realistic pending notifications (3 per admin, 1 per regular user) so the stream is non-empty on first load.

### Slack integration
- [x] **Outbound kudos announcements** — when a kudos is given, post an announcement (giver, receiver,
  points, core value, message) to a Slack channel via an **Incoming Webhook** (`SLACK_WEBHOOK_URL`).
- [x] **Disabled by default** — with no `SLACK_WEBHOOK_URL` set, `slack.notify_kudos()` is a silent
  no-op; the app runs identically in demo mode.
- [x] **Failure isolation** — a Slack outage, timeout, or non-200 response must never fail the kudos
  request; errors are swallowed and logged, and `notify_kudos` returns `False`.

---

## 3. Implicit requirements (inferred from brief + decisions)

### Recognition & points model
- [x] **Three distinct balances** per person:
  - [x] **Giving allowance** — points each employee can give away, **resets monthly** (default 100).
  - [x] **Earned points** — accumulate from kudos received + (optionally) CRM events + (optionally) GitHub activity.
  - [x] **Spendable points** — earned minus committed (pending + approved swag orders).
- [x] Giving is **budget-constrained** — can't give more than your monthly allowance.
- [x] Can't give kudos **to yourself**.
- [x] Each kudos has: recipient, **point amount**, a **core value/category**, **message**, optional **artifact link**.
- [x] **Core values**: Great Teammate, Client Hero, Crisis Crusher, Above & Beyond, Innovator, Mentor.

### Social / engagement
- [x] **Recognition feed** — public, reverse-chronological wall of kudos.
- [x] **Emoji reactions** on kudos (toggle on/off, one per emoji per person).
- [x] **Admin statistics dashboard** — replaces the public leaderboard; only Admins/SuperAdmins can
  view org-wide totals, points-by-source breakdown, top earners (all-time), recognition by core
  value, users by role, and swag orders by status, via `GET /api/admin/statistics` (Admin panel →
  Statistics tab).
- [x] **People directory** and **individual profiles** (points, value breakdown, history).
- [x] **Profile tabs**: Kudos received · GitHub contributions · CRM contributions.
- [x] **Company stats** (total kudos, points awarded, people recognized, CRM events).
- [x] A **celebratory moment** on giving kudos (confetti) — reinforces the positive ritual.
- [x] **Activity view** (`/activity` nav item) — combined feed of all GitHub and CRM contributions
  across all users, filterable by source. Each card has an **Award kudos** button that pre-fills
  the give-kudos modal with the contributor and artifact link.
- [x] **Award kudos from CRM profile tab** — CRM contributions on user profiles now have an
  "Award kudos" button (matching the existing GitHub tab behavior).
- [x] **Admin panel theme consistency** — all admin tabs use a unified container style, section
  group titles replace bare `<h3>` tags, Orders tab wrapped in a consistent card.

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
- [x] **Three-tier role system** — SuperAdmin, Admin, and User roles replace the current binary admin flag.
- [x] **SuperAdmin privileges** — full access; can create and promote other SuperAdmins; all Admin capabilities included.
- [x] **Admin privileges** — can approve swag orders and add/manage users; cannot promote to SuperAdmin or modify system settings.
- [x] **User privileges** — can give kudos, redeem swag, and view all social features; no admin access.
- [x] **Role management UI** — Admin screen lets SuperAdmins assign and change roles for any user.

### Non-functional / quality
- [x] **Ease of use** — intuitive, minimal interface (judging criterion).
- [x] **Maintainability** — small, documented modules; clear data layer; single codebase.
- [x] **Runs out-of-the-box** — `pip install` + seed + run; no external DB/server to stand up.
- [x] **Concurrency-safe** data access (module-level `threading.RLock` serializes all reads and writes).
- [x] **Seed data** — 10 employees, 15 kudos, 13 GitHub contributions, 23 CRM events across 7 employees, 9 swag items.
  Seed intentionally timestamps a subset of events to `days_ago(0)` so "This month" leaderboard is
  never empty regardless of what day of the month the seed is run.
- [x] **Test suite** — 192 pytest tests covering auth, kudos, feed, statistics, activity, swag,
  workflow, CRM, GitHub, notifications, settings, roles, and Slack. Includes `TestSeedActivity` (guards
  against seed-timing regressions), `TestActivityFeed` (9 tests), `TestStatisticsAccess`/
  `TestStatisticsData` (admin-only dashboard, access control), and `TestRoleAPI` (role hierarchy
  enforcement).
- [ ] **README / setup docs** and a **demo script** for the shareout.
- [ ] ❓ **Deployment** target — local-only for demo, or hosted somewhere?
- [x] **Automatic dark mode** — theme follows the OS/browser `prefers-color-scheme` setting site-wide
  via CSS custom properties (no manual toggle). Introduced a `--heading` variable (distinct from the
  fixed brand `--navy`) so heading/accent text flips for contrast against dark surfaces, and a
  `--header-bg` variable so the topbar can be lightened independently of card surfaces for logo contrast.

---

## 4. Out of scope (for now)

- [x] **Outbound Slack** kudos announcements via Incoming Webhook — see §2 Slack integration.
- ⛔ **Bidirectional Slack bot** (slash commands to give kudos, Socket Mode, DMs) — outbound
  webhook announcements are built; a full interactive bot remains future work.
- ⛔ **Email / push notifications** — in-app only.
- ⛔ Production-grade **auth hardening**, multi-tenant, audit logging.
- ⛔ Migration to a **server-based DB** (Postgres/Mongo) — TinyDB sufficient for hackathon.
- ⛔ Swag **physical fulfilment** or gift-card issuing — workflow stops at "Shipped" state.
- ⛔ **Public leaderboard / peer ranking** — removed to avoid incentivizing competition or gaming
  the recognition system; ranking data is now visible to Admins/SuperAdmins only.

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

- **Backend:** Python 3.14 + FastAPI; Uvicorn server.
- **Data:** TinyDB (JSON document store) — single `kudos_db.json` file; tables: users, kudos,
  reactions, github_contributions, crm_contributions, settings, sessions, swag_items, swag_orders,
  workflow, notifications.
- **Thread safety:** module-level `threading.RLock()` wraps ALL reads and writes.
- **Auth:** GitHub OAuth (optional) + demo login; httponly cookie sessions.
- **GitHub:** `httpx` against the GitHub Search API for merged PRs / closed issues.
- **CRM:** Webhook endpoint + 6 event types + admin simulator; Salesforce adapter pattern documented.
- **Slack:** Outbound-only via `httpx` POST to an Incoming Webhook (`SLACK_WEBHOOK_URL`); posts a
  Block Kit kudos announcement on each kudos. Disabled by default; failures never break the request.
- **Workflow:** JIRA-inspired state machine stored in TinyDB; full transition audit log per order.
- **Frontend:** Vanilla HTML/CSS/JS SPA (no build step), OpenTeams palette, Airbnb-minimal styling.
- **venv:** `~/miniconda3/bin/python -m venv .venv` (requires Python 3.14 from Miniconda, not system Python).

---

## 7. File map

```
app/
  main.py          — All FastAPI routes (auth, kudos, feed, activity, GitHub, CRM, swag, workflow, notifications)
  db.py            — TinyDB repository layer (all reads + writes; thread-safe RLock)
  auth.py          — Session dependency; require_admin(); upsert_github_user()
  config.py        — Env vars; github_oauth_enabled() + slack_enabled() helpers
  values.py        — 6 core values with colors
  crm_events.py    — 6 CRM event types, configurable weights, event_points()
  github_sync.py   — GitHub Search API sync (merged PRs + closed issues); see architecture.md for details
  slack.py         — Outbound Slack Incoming Webhook posting (notify_kudos); no-op when unconfigured
  workflow.py      — Workflow state machine helpers (add/delete states & transitions)
  schemas.py       — Pydantic request body models
  seed.py          — Wipe + reseed with 10 employees, 15 kudos, 13 GitHub + 23 CRM contributions, 9 swag items, swag orders

static/
  index.html             — HTML shell (login, topbar, floating 🎉 give button, give modal)
  styles.css             — OpenTeams palette, Airbnb-minimal + swag/workflow/notification styles
  app.js                 — Vanilla JS SPA: feed, people, profile, rewards, admin (incl. Statistics tab)
  openteams-logo.png     — OpenTeams horizontal logo (dark, for light backgrounds)
  openteams-morale-logo.svg — Composite logo: OpenTeams PNG + "Kudos" SVG text; used in topbar + login

requirements.txt   — Python dependencies (fastapi, uvicorn, pydantic, httpx, tinydb)
requirements.md    — This file

tests/
  conftest.py         — Shared fixtures (seeded_db, client, admin_client, user*_client, full_seed_client)
  test_auth.py        — Auth / session tests
  test_kudos.py       — Kudos creation, allowance, validation
  test_feed.py        — Recognition feed ordering and reactions
  test_statistics.py  — Admin-only statistics dashboard: access control, data aggregation
  test_activity.py    — Activity feed (GitHub + CRM combined; auth, filters, sort, Award kudos data;
                         includes TestSeedActivity, the seed-timing guard formerly in test_leaderboard.py)
  test_profile.py     — User profiles, contribution tabs
  test_swag.py        — Swag catalog, orders, spendable balance
  test_crm.py         — CRM webhook endpoint, event types, idempotency
  test_workflow.py    — Workflow state machine, transitions, audit log
  test_github.py      — GitHub accumulation toggle (TestGithubAccumulationToggle)
  test_notifications.py — Order and transition notifications; notification endpoints
  test_settings.py    — Settings read/write; admin-only enforcement; defaults validation
  test_roles.py       — Three-tier role system (SuperAdmin/Admin/User); role field, API enforcement
  test_slack.py       — Outbound Slack webhook: disabled-by-default no-op, payload contents, failure isolation, kudos endpoint integration

.claude/skills/
  seed/SKILL.md          — How to wipe + reseed the database (Windows + Mac/Linux steps)
  server/SKILL.md        — How to free port 8000 and restart uvicorn
  test/SKILL.md          — How to run the full pytest suite with common flag options
  requirements/SKILL.md  — Log new requirements from chat into docs/requirements.md in real time
```
