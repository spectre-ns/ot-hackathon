# API Reference

All endpoints are relative to `http://localhost:8000`. Auth: httponly cookie `kudos_session`
(set by `/api/auth/demo` or `/api/auth/github/callback`).

---

## Auth

### `POST /api/auth/demo`
Body: `{"user_id": <int>}`  
Sets session cookie. No credentials required. Use for demo/dev.

### `GET /auth/github/login`
Redirects to GitHub OAuth. Only available if `GITHUB_CLIENT_ID` is set.

### `GET /auth/github/callback?code=<code>`
GitHub OAuth callback. Sets session cookie, redirects to `/`.

### `POST /api/auth/logout`
Clears session cookie. Returns `{"ok": true}`.

---

## Current user

### `GET /api/me`
Returns current user object with computed fields:
```json
{
  "id": 1, "name": "Ada Lovelace", "email": "ada@openteams.com",
  "title": "Principal Engineer", "department": "Platform",
  "avatar_color": "#000F3A", "github_login": "ada-lovelace",
  "is_admin": true,
  "earned_points": 285, "giving_balance": 75, "spendable_points": 285,
  "unread_notifications": 2
}
```
401 if not logged in.

### `GET /api/config`
Returns app configuration (does not require auth):
```json
{
  "github_oauth_enabled": false,
  "core_values": [{"key": "great_teammate", "label": "Great Teammate", "emoji": "🤝", "color": "#4D75FE", "desc": "..."}],
  "crm_event_types": [{"key": "deal_closed", "label": "Deal Closed", "emoji": "💼", "default_points": 25, "settings_key": "crm_deal_closed_points", "desc": "..."}],
  "settings": { "crm_api_key": "..." }
}
```

---

## Users

### `GET /api/users`
Returns array of all users with computed `earned_points`.

### `GET /api/users/{user_id}`
Returns full profile:
```json
{
  "user": {...},
  "earned_points": 285, "kudos_count": 8, "given_count": 5,
  "received": [...enriched kudos...],
  "github_contributions": [...],
  "crm_contributions": [...],
  "value_breakdown": [{"value": {...}, "count": 3}]
}
```

---

## Kudos / Feed

### `POST /api/kudos`
Requires auth. Body: `KudosBody`
```json
{
  "receiver_id": 3, "points": 15, "value_key": "innovator",
  "message": "Great work on the caching PR!",
  "artifact_url": "https://github.com/org/repo/pull/42",
  "artifact_label": "PR #42: Add Redis caching"
}
```
Errors: 400 if self-kudos, insufficient balance, or unknown value_key.

### `GET /api/feed?limit=<n>`
Returns array of enriched kudos (default limit 50).

Enriched kudos shape:
```json
{
  "id": 1, "points": 15, "message": "...", "created_at": "...",
  "artifact_url": "...", "artifact_label": "...",
  "giver": {"id": 1, "name": "...", "avatar_color": "...", ...},
  "receiver": {...},
  "value": {"key": "innovator", "label": "Innovator", "emoji": "💡", "color": "#2E9E6B"},
  "reactions": [{"emoji": "🎉", "count": 2, "mine": true}]
}
```

### `POST /api/kudos/{kudos_id}/react`
Body: `{"emoji": "🎉"}`. Toggles reaction for current user.

---

## Leaderboard / Stats

### `GET /api/leaderboard?period=<month|all>`
Returns array sorted by points descending:
```json
[{"rank": 1, "user": {...}, "points": 285}]
```

### `GET /api/stats`
```json
{"kudos_count": 15, "points_awarded": 280, "people_recognized": 8, "crm_events": 12}
```

---

## GitHub

### `POST /api/github/sync`
Requires auth. Fetches and stores merged PRs + closed issues for the current user.
Requires `GITHUB_TOKEN` in env and `github_login` on user record.
```json
{"summary": {"prs_added": 2, "issues_added": 1, "prs_updated": 0, "issues_updated": 0}}
```

---

## CRM

### `POST /api/crm/event`
**Webhook endpoint.** Requires `X-CRM-Key` header (value from settings).
Body: `CRMEventBody`
```json
{
  "event_type": "deal_closed",
  "user_identifier": "ada-lovelace",
  "reference_id": "OPP-8821",
  "title": "Closed Acme Corp deal",
  "company": "Acme Corp",
  "deal_value": 85000,
  "happened_at": "2026-06-28T14:00:00Z",
  "artifact_url": "https://crm.example.com/opportunities/OPP-8821"
}
```
Idempotent on `reference_id`. Returns `{"created": true, "points_awarded": 25, "user": {...}, "event_type": {...}}`.

### `POST /api/crm/simulate`
Same as `/api/crm/event` but requires admin session cookie (no X-CRM-Key needed). For admin UI.

### `GET /api/crm/event-types`
Returns the 6 event type definitions.

---

## Settings (admin only)

### `GET /api/settings`
Returns full settings document (all weights, toggles, API key).

### `PUT /api/settings`
Body: `SettingsBody`. All fields required:
```json
{
  "pr_points": 10, "issue_points": 5,
  "monthly_allowance": 100,
  "github_accumulation_enabled": false,
  "crm_deal_closed_points": 25,
  "crm_contract_renewed_points": 20,
  "crm_escalation_resolved_points": 15,
  "crm_nps_positive_points": 10,
  "crm_ticket_resolved_points": 8,
  "crm_customer_call_points": 5
}
```

---

## Swag Catalog

### `GET /api/swag`
Returns `{"items": [...], "spendable_points": <int>}`.

Item shape: `{"id": 1, "name": "T-Shirt", "description": "...", "point_cost": 50, "stock": null, "is_available": true}`.

### `POST /api/swag`
Admin only. Body: `SwagItemBody`. Creates a swag item.

### `POST /api/swag/{item_id}/order`
Requires auth. Body: `{"notes": "Size L"}`.  
Checks `spendable_points >= item.point_cost`. Creates order at initial workflow state.
Notifies all admins.

### `GET /api/swag/orders`
Returns orders for the current user (with `state_info` and `available_transitions`).

### `GET /api/swag/orders/pending`
Admin only. Returns orders in non-terminal states.

### `GET /api/swag/orders/all`
Admin only. Returns all orders.

### `POST /api/swag/orders/{order_id}/transition`
Body: `{"transition_id": "approve", "reason": ""}`.  
Admin only (currently). Advances order, appends audit log, notifies order owner.

---

## Workflow

### `GET /api/workflow`
Returns workflow document:
```json
{
  "states": [{"id": "pending", "name": "Pending", "color": "#FAA944", "is_initial": true, "is_terminal": false}],
  "transitions": [{"id": "start_review", "from": "pending", "to": "under_review", "label": "Start Review", "requires_admin": true, "requires_reason": false}]
}
```

### `POST /api/workflow/states`
Admin only. Body: `WorkflowStateBody` — `{name, color, is_terminal}`.

### `DELETE /api/workflow/states/{state_id}`
Admin only. 400 if trying to delete initial state.

### `POST /api/workflow/transitions`
Admin only. Body: `WorkflowTransitionBody` — `{from_state, to_state, label, requires_admin, requires_reason}`.

### `DELETE /api/workflow/transitions`
Admin only. Body: `{"transition_id": "<id>"}`.

---

## Notifications

### `GET /api/notifications`
Returns notifications for current user, newest first.

### `POST /api/notifications/read`
Marks all notifications as read for the current user.
