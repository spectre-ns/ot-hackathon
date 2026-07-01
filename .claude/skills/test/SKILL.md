---
description: Run the Kudos pytest suite. Use after any code change to confirm no regressions. 183 tests across auth, kudos, leaderboard, activity, feed, swag, workflow, CRM, notifications, settings, and roles.
---

# test

Runs the full test suite with verbose output.

## Steps

```
.venv\Scripts\python -m pytest tests/ -v
```

On Mac/Linux use `.venv/bin/python` instead.

## Common options

| Flag | Purpose |
|---|---|
| `-x` | Stop on first failure (faster feedback cycle) |
| `-k "leaderboard"` | Run only tests matching a keyword |
| `tests/test_leaderboard.py` | Run a single test file |
| `--tb=short` | Shorter tracebacks (default is `long`) |
| `-q` | Quiet mode — just pass/fail counts |

## Expected baseline

```
183 passed in ~Ns
```

If the count is lower, tests were filtered or the suite has been extended since this skill was written.

## Fixtures

- `seeded_db` / `client` / `user1_client` / `admin_client` — isolated temp-DB per test; no cross-test state
- `full_seed_client` — runs real `app/seed.py` seed; used by `TestSeedLeaderboard` and `test_seed_activity_not_empty`

## Known gotcha

On Windows, rapid API calls within a single test may get identical `utcnow_iso()` timestamps. Use `adb.create_kudos(..., created_at=...)` with explicit `timedelta`-spread timestamps in sort-order tests instead of relying on insertion order.
