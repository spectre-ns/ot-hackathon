---
description: Wipe and re-seed the Kudos database with realistic demo data (10 employees, 15 kudos, 12 GitHub contributions, 23 CRM events, 8 swag items).
---

# seed

Re-seeds the database. Use whenever the DB is stale, corrupt, or after schema-level changes.

## Steps

1. Run the seed module (it calls `db.reset_database()` internally, so no manual wipe needed):
   ```
   .venv/Scripts/python -m app.seed
   ```
   On Mac/Linux use `.venv/bin/python` instead.

2. Confirm output ends with:
   ```
   Seeded 10 employees, 15 kudos, 12 GitHub activities, 23 CRM events, 8 swag items, 1 pending order.
   Admins: Ada Lovelace, Grace Hopper
   ```

3. If the dev server is running, **restart it** (sessions were wiped by the seed) — invoke `/server` or run the server skill.

## Notes

- The seed intentionally includes items timestamped to `days_ago(0)` (today) so the Activity feed and Admin → Statistics dashboard are never empty right after seeding.
- Default logins after seed: any of the 10 employees via the demo-login picker. Ada Lovelace and Grace Hopper are admins.
- The seed is idempotent in effect — running it twice is safe, it just resets again.
