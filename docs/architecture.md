# Architecture Overview

## Project: Kudos — Peer Recognition Platform
**Hackathon:** OpenTeams Bounty Hunters · Deadline: July 20, 2026

---

## High-level structure

```
FastAPI (Python 3.13)
    └── Uvicorn (ASGI server)
         └── TinyDB (kudos_db.json — single-file NoSQL)
              └── threading.RLock (all reads + writes serialized)

Static frontend (Vanilla JS SPA, no build step)
    └── /static/index.html + styles.css + app.js
```

---

## Backend modules

### `app/main.py`
All FastAPI routes. Organized into logical groups:

| Route group | Prefix | Description |
|---|---|---|
| Auth | `/api/auth` | Demo login, GitHub OAuth, logout |
| Me / config | `/api/me`, `/api/config` | Current user + app config |
| Users | `/api/users` | List, profile, give kudos, reactions |
| Feed | `/api/feed` | Recognition feed (enriched kudos) |
| Leaderboard | `/api/leaderboard` | Points ranked by period |
| Stats | `/api/stats` | Company-wide aggregate stats |
| GitHub | `/api/github` | Sync merged PRs + closed issues |
| CRM | `/api/crm` | Webhook ingestion, simulate, list event types |
| Settings | `/api/settings` | Admin GET/PUT for all weights + toggles |
| Swag | `/api/swag` | Catalog, order, order history |
| Workflow | `/api/workflow` | Get/add/delete states + transitions |
| Notifications | `/api/notifications` | List, mark-read |
| Static | `/{path}` | Serve `static/` files |

Key helper: `enrich_kudos(k)` — joins user objects + value metadata + reactions onto a raw kudos doc before returning to the frontend.

### `app/db.py`
TinyDB repository. **Critical invariant:** every function acquires `_lock` (module-level `threading.RLock`) before touching the database. This prevents torn reads when FastAPI's threadpool runs concurrent requests.

Tables:
- `users` — employees; fields: id, name, email, title, department, avatar_color, github_login, is_admin
- `kudos` — giver_id, receiver_id, points, value_key, message, created_at, artifact_url, artifact_label
- `reactions` — kudos_id, user_id, emoji
- `github_contributions` — user_id, kind, repo, number, title, url, points, happened_at
- `crm_contributions` — user_id, event_type, reference_id, title, company, deal_value, points, happened_at, artifact_url
- `settings` — single document; auto-backfilled with defaults when new keys are added
- `sessions` — session_token → user_id mapping
- `swag_items` — catalog items
- `swag_orders` — orders with current_state + transition_log array
- `workflow` — single document: {states: [...], transitions: [...]}
- `notifications` — user_id, message, kind, link, read, created_at

Key computed values:
- `earned_points(uid)` = sum of kudos received + CRM contributions + (GitHub if `github_accumulation_enabled`)
- `giving_balance(uid)` = monthly_allowance − points given this calendar month
- `spendable_points(uid)` = earned_points − points in pending/approved swag orders

### `app/auth.py`
- `current_user()` — FastAPI `Depends()`; reads `kudos_session` httponly cookie; 401 if missing
- `require_admin()` — FastAPI `Depends()`; 403 if not admin
- `upsert_github_user(gh_profile)` — find-or-create user from GitHub OAuth profile

### `app/config.py`
Reads environment variables. Key settings:
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` — for OAuth (optional)
- `GITHUB_TOKEN` — personal access token for API calls
- `BASE_URL` — for OAuth redirect
- `DATABASE_FILE` — default `kudos_db.json`
- `SECRET_KEY` — session signing
- `DEFAULT_MONTHLY_ALLOWANCE` = 100

### `app/values.py`
6 core values: `great_teammate`, `client_hero`, `crisis_crusher`, `above_beyond`, `innovator`, `mentor`. Each has emoji + label + color + desc.

### `app/crm_events.py`
6 event types: `deal_closed`, `contract_renewed`, `escalation_resolved`, `nps_positive`, `ticket_resolved`, `customer_call`. Each has `settings_key` for admin-configurable weight. `event_points(event_key, settings)` resolves the current weight.

### `app/workflow.py`
Workflow state machine helpers:
- `DEFAULT_WORKFLOW` — 5 states (pending, under_review, approved, shipped, rejected), 6 transitions
- `initial_state(wf)` — state with `is_initial: True`
- `is_terminal(wf, state_id)` — true if state has `is_terminal: True`
- `available_transitions(wf, current_state)` — valid next transitions from a state
- `add_state(wf, ...)` / `delete_state(wf, state_id)` — mutation helpers; delete raises `ValueError` for initial state
- `add_transition(wf, ...)` / `delete_transition(wf, transition_id)` — mutation helpers

### `app/schemas.py`
Pydantic v2 request bodies for all endpoints. Key models:
- `KudosBody` — includes `artifact_url`, `artifact_label`
- `SettingsBody` — all weights including `github_accumulation_enabled`
- `CRMEventBody` — webhook payload; `user_identifier` can be github_login or email
- `SwagOrderBody`, `OrderTransitionBody`, `WorkflowStateBody`, `WorkflowTransitionBody`

### `app/seed.py`
Wipes and reseeds the database. Run with `python -m app.seed`. Seeds:
- 10 employees (2 admins: Ada Lovelace, Grace Hopper)
- 15 kudos (some with artifact URLs)
- 12 GitHub contributions
- 12 CRM contributions across 6 event types
- 8 swag items (T-shirt 50pts … Headphones 500pts)
- 1 pending swag order (Guido van Rossum, T-shirt)
- Admin notifications for the pending order

---

## Frontend

Single-page app. No framework, no build step. Entry: `static/index.html`.

### `static/app.js`
Routing: `go(route, arg)` dispatches to `ROUTES[route](view, arg)`. Routes: `feed`, `leaderboard`, `people`, `profile`, `rewards`, `admin`.

Admin sub-tabs: `settings`, `crm`, `orders`, `workflow`, `catalog`.

Key patterns:
- `api.get/post/put/delete` — thin fetch wrappers; throw on non-2xx
- `avatarHTML(user, size)` — renders colored-initial avatar or image
- `kudosCard(k)` — renders a full kudos feed card with reactions + artifact link
- `openGive(prefill)` — opens give-kudos modal; `prefill` can include receiverId + artifact fields
- `openRedeemModal(itemId, name, cost)` — dynamic modal for placing a swag order
- `renderWFDiagram(wf)` — SVG workflow diagram from state machine data
- `fireConfetti()` — canvas particle burst on kudos sent

### `static/styles.css`
CSS custom properties for OpenTeams palette. Component namespaces: `.kudos-*`, `.lb-*`, `.swag-*`, `.wf-*`, `.notif-*`, `.contrib-*`.

---

## Data flow: giving kudos

1. User opens Give Kudos modal (`openGive()`)
2. POST `/api/kudos` with `{receiver_id, points, value_key, message, artifact_url?, artifact_label?}`
3. `main.py` checks giving_balance; inserts kudos doc; decrements nothing (balance is computed live)
4. Response: enriched kudos object
5. Frontend fires confetti, re-renders feed

## Data flow: swag order

1. User clicks Redeem on a swag card → `openRedeemModal()`
2. POST `/api/swag/{item_id}/order` with `{notes}`
3. `main.py` checks `spendable_points >= item.point_cost`; inserts order at `initial_state`; notifies all admins
4. Admin sees notification badge; opens Admin → Approvals tab
5. Admin clicks transition button → POST `/api/swag/orders/{id}/transition` with `{transition_id, reason?}`
6. `db.transition_swag_order()` validates transition, appends audit log entry, notifies order owner
7. Order advances through workflow until terminal state (shipped or rejected)

## Data flow: CRM event

1. CRM POSTs to `/api/crm/event` with `X-CRM-Key` header
2. `main.py` validates key; resolves `user_identifier` to a user (github_login or email)
3. `db.upsert_crm_contribution()` — idempotent on `reference_id`
4. Points visible immediately in `earned_points(uid)` and on user profile CRM tab

---

## Known constraints

- **TinyDB is not multi-process safe** — single process only. If running behind a load balancer,
  each instance has its own DB file (not shared state). Acceptable for demo; use Postgres for prod.
- **GitHub token** must have `repo:read` scope (or `public_repo` for public repos only).
- **CRM API key** is stored in the `settings` TinyDB document — rotate by updating settings.
- **Session tokens** are random UUIDs stored in TinyDB; no JWT signing or expiry currently.
