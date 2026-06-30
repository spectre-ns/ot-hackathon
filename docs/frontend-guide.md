# Frontend Guide

## Overview

The frontend is a vanilla JavaScript SPA. No framework, no build step, no npm. Everything is in three files:

- `static/index.html` — HTML shell: login screen, app shell, modals, canvas for confetti
- `static/styles.css` — All CSS using OpenTeams CSS custom properties
- `static/app.js` — All JavaScript: routing, views, API calls, modal logic

Served by FastAPI's `StaticFiles` mount at `/static/`.

---

## Boot sequence

1. `boot()` fetches `/api/config` (always) then `/api/me` (may 401)
2. If logged in → `showApp()` → `renderTopbar()` → `go(state.route)`
3. If not logged in → `showLogin()` — populates the demo-login dropdown

---

## Routing

```js
go(route, arg)   // renders a view into #view
```

Routes are registered in the `ROUTES` object:
```js
ROUTES.feed = async (view, arg) => { ... }
ROUTES.leaderboard = async (view, arg) => { ... }
ROUTES.people = async (view, arg) => { ... }
ROUTES.profile = async (view, userId) => { ... }
ROUTES.rewards = async (view, tab) => { ... }   // tab: "catalog" | "orders"
ROUTES.admin = async (view, subTab) => { ... }   // subTab: "settings" | "crm" | "orders" | "workflow" | "catalog"
```

Nav links use `data-route="<name>"` attributes — a single delegated click handler on `document` calls `go()`.

---

## API helper

```js
api.get('/api/feed')
api.post('/api/kudos', body)
api.put('/api/settings', body)
api.delete('/api/workflow/transitions', body)
```

Throws `Error` with `.message = detail` on non-2xx. Await in try/catch and call `toast(e.message, "error")`.

---

## State

```js
state.me        // current user object from /api/me (includes computed balances)
state.config    // app config from /api/config (core_values, crm_event_types, settings)
state.users     // array of all users (populated on login)
state.route     // current route name
state.routeArg  // current route argument
```

After a mutation that changes balances, call `await refreshMe()` to pull a fresh `/api/me`.

---

## Common helpers

```js
avatarHTML(user, size)     // colored-initial <span> or background-image if avatar_url exists
timeAgo(isoString)         // "2h ago", "3d ago", etc.
esc(string)                // HTML-encode for innerHTML injection
toast(msg, kind)           // kind: "" | "error" | "success" — shows a floating pill
empty(emoji, msg)          // returns HTML for an empty state placeholder
wireReactions(scope)       // attaches click handlers to .react-chip and [data-toggle-react] elements
wireProfileLinks(scope)    // attaches click handlers to [data-profile] elements
```

---

## Adding a new view

1. Add an entry to `ROUTES`:
```js
ROUTES.myview = async (view, arg) => {
  const data = await api.get('/api/something');
  view.innerHTML = `<div class="page-head"><h2>My View</h2></div>...`;
  // wire event handlers
};
```

2. Add a nav link to `static/index.html`:
```html
<a class="nav-link" data-route="myview">My View</a>
```
If admin-only: `<a class="nav-link admin-only hidden" data-route="myview">My View</a>`

3. Add component styles to `static/styles.css`.

4. Update `REQUIREMENTS.md`.

---

## CSS patterns

CSS custom properties (defined in `:root`):
```css
--navy: #000F3A         /* primary text + headings */
--blue: #4D75FE         /* primary action color */
--blue-dark: #3a61e8    /* hover state */
--blue-soft: #eef1ff    /* soft backgrounds */
--coral: #FF8A69        /* warning / alert accent */
--gold: #FAA944         /* points badge */
--surface-2: #f7f7f7    /* secondary background */
--line: #ebebeb          /* card borders */
--muted: #717171        /* secondary text */
```

Card pattern:
```css
.card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
```

Hover lift (used on swag cards, people cards):
```css
transition: transform .12s, box-shadow .15s;
:hover { transform: translateY(-3px); box-shadow: var(--shadow-hover); }
```

Badge:
```css
.points-badge { font-weight: 800; padding: 6px 13px; border-radius: 999px; background: var(--gold); color: var(--navy); }
```

---

## Give Kudos modal

`openGive(prefill)` — `prefill` is optional:
```js
openGive()                           // blank form
openGive({ receiverId: 5 })          // pre-select recipient
openGive({                           // pre-fill artifact from GitHub tab
  receiverId: 5,
  artifactUrl: 'https://github.com/.../pull/42',
  artifactLabel: 'PR #42: Add caching'
})
```

The modal reads `state.config.core_values` to render value chips. Selected value is stored in `selectedValue`.

---

## Admin sub-panels

Admin view (`ROUTES.admin`) renders sub-tabs and delegates to:
```
renderAdminSettings(el, settings)     — point weights, GitHub toggle, CRM weights
renderCRMSimulator(el)                — fire test CRM events from the UI
renderAdminOrders(el, pending, all)   — order list with transition buttons
renderWorkflowEditor(el)              — SVG diagram + state/transition CRUD
renderSwagCatalog(el)                 — item list + add-item form
```

Each function is self-contained and re-renders its `el` on mutation (no full page reload).

---

## Notification bell

`#notif-btn` click → fetches `/api/notifications` → renders dropdown → marks all read.

The unread count is on `state.me.unread_notifications` (updated by `refreshMe()`).
The badge `#notif-badge` is updated in `renderTopbar()`.
