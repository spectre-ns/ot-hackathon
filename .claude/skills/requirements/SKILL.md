---
description: Log a new requirement into docs/requirements.md. Pass the requirement text as args, or invoke without args to scan the conversation for any requirements mentioned since the last update.
---

# requirements

Adds one or more new requirements to `docs/requirements.md` so future agents have a complete, up-to-date picture.

## When to invoke

- A user states a new feature, constraint, or question in the chat ("I want X", "we need Y", "can it do Z?")
- An open question surfaces that needs a decision later
- A scope change, integration, or non-functional constraint is mentioned
- After a design discussion where decisions were made

## Steps

### 1 — Identify the requirement(s)

If `args` is provided, treat it as the raw requirement text (one or more lines).

If invoked without args, scan the current conversation for anything that looks like a new requirement:
- Feature requests ("I want / we need / it should / add / build / support …")
- Constraints ("must / cannot / should not / only / always …")
- Open questions ("what about / how do we / should we / ❓ …")
- Decisions made ("we decided / going with / confirmed …")

Only capture things **not already in `docs/requirements.md`**.

### 2 — Classify each item

Pick the best-fit section and sub-section from the table below:

| Keyword signals | Target section |
|---|---|
| core feature, UX, backend, database, API | §2 Core platform |
| GitHub OAuth, PR, issue, sync, accumulation toggle | §2 GitHub integration |
| CRM, Salesforce, webhook, deal, ticket | §2 CRM integration |
| artifact, URL, traceability | §2 Artifact traceability |
| swag, catalog, redemption, order, stock | §2 Swag catalog |
| workflow, state machine, transition, approval | §2 Configurable workflow manager |
| notification, bell, badge, read | §2 Notification system |
| points model, allowance, budget, balance | §3 Recognition & points model |
| feed, statistics dashboard, profile, reaction, confetti | §3 Social / engagement |
| auth, role, session, admin | §3 Auth, roles, sessions |
| performance, test, deploy, setup, maintainability | §3 Non-functional / quality |
| out of scope, not building, skip | §4 Out of scope |
| open question, undecided, TBD, ❓ | §5 Open questions |

If none match well, append to the most closely related section in §2. If it is a new domain entirely, create a new `###` sub-section in §2.

### 3 — Format the entry

**Functional requirement (new feature / constraint):**
```
- [ ] **Short bold name** — one-sentence description of what it does or requires.
```

**Decision already made:**
```
- [x] **Short bold name** — one-sentence description, marked done if implemented.
```

**Open question:**
```
- [ ] ❓ **Short bold name** — phrased as a question, e.g. "Should X support Y?".
```

**Out of scope:**
```
- ⛔ **Short bold name** — brief rationale or "noted for future work".
```

Use `[ ]` (not done) unless the requirement is already implemented. When uncertain, default to `[ ]`.

### 4 — Insert into the document

Read `docs/requirements.md`, find the right section, and insert the new line(s) at the **end of that sub-section** (just before the next `###` or `---`).

Preserve all existing formatting and checkbox states exactly.

### 5 — Confirm

Print a one-line summary: `Added N requirement(s) to docs/requirements.md — sections: §2 GitHub integration, §5 Open questions` (or whichever sections changed).

Do **not** run `/update-docs` — this skill is additive only. `update-docs` does a full audit; this skill handles real-time chat capture.

### 6 — Identify test coverage gaps

For each `[ ]` (planned, not yet built) requirement just added, identify what test(s) would verify it and whether a test file already covers that area.

Check `tests/` for relevant existing test files:
```
tests/test_auth.py, test_kudos.py, test_feed.py, test_statistics.py,
test_activity.py, test_profile.py, test_swag.py,
test_crm.py, test_workflow.py, test_github.py, test_notifications.py,
test_settings.py, test_roles.py
```

For each requirement without coverage, do one of the following (choose based on scope):

**A — Add to an existing test file** (for small additions to a well-defined area):
Open the relevant file and append a test class or test function at the end with a `# TODO: implement` body and a clear docstring describing what the test must assert.

```python
class TestNotificationDeepLink:
    def test_notification_link_field_is_returned(self, admin_client):
        """Notifications returned by GET /api/notifications must include a 'link' field."""
        # TODO: implement
        pass
```

**B — Create a new test file** (for new features with no existing coverage):
Create `tests/test_<feature>.py` following the same pattern as existing test files (import fixtures from conftest, group tests in classes by feature area). Add stubs for all obvious test cases.

**C — Note the gap inline** (for out-of-scope or frontend-only requirements that have no backend surface to test):
Print a note: `⚠️ No backend test surface for: "<requirement>" — manual verification required.`

After this step, print a summary:
```
Test coverage:
  ✅ Already covered by test_notifications.py
  📝 Stub added to test_notifications.py: TestNotificationDeepLink
  📄 New file created: tests/test_roles.py (N stubs)
  ⚠️  No backend surface: "Bell opens full stream page"
```
