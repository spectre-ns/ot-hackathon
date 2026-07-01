---
description: Audit docs/architecture.md and docs/requirements.md against current code and update any stale content. Run after adding features, renaming modules, or changing the test suite.
---

# update-docs

Keeps `docs/architecture.md` and `docs/requirements.md` in sync with the actual codebase.

## When to use

- After adding a new backend module (`app/*.py`)
- After adding, removing, or renaming test files
- After changing the seed data counts
- After adding a new API route group
- After building a feature that satisfies a requirements checkbox
- When the test count in `/test` skill description drifts from the real count

## What to check

### `docs/architecture.md`

| Section | What can go stale |
|---|---|
| Route table | New route groups added to `main.py` |
| Backend modules | New `app/*.py` files not yet documented |
| `app/seed.py` | Counts of employees, kudos, GitHub contributions, CRM events, swag items |
| Data flow sections | New flows (e.g. GitHub sync, activity feed) |
| Known constraints | New limitations discovered |

### `docs/requirements.md`

| Section | What can go stale |
|---|---|
| Section 2 checkboxes | Features built but not ticked `[x]` |
| Section 3 checkboxes | Same |
| Section 6 tech stack | New deps or removed ones |
| Section 7 file map | New `app/*.py` or `tests/test_*.py` files |
| Test count | Listed in the Non-functional bullet and in `/test` skill |

## Steps

### 1 — Discover actual state

```bash
# List all app modules
ls app/*.py

# List all test files
ls tests/test_*.py

# Count collected tests
.venv/Scripts/python -m pytest tests/ --collect-only -q 2>&1 | tail -3

# Count seed data rows (run from repo root)
.venv/Scripts/python -c "
import re
with open('app/seed.py') as f:
    txt = f.read()
for name, pattern in [
    ('employees', r'EMPLOYEES\s*=\s*\['),
    ('kudos', r'KUDOS\s*=\s*\['),
    ('github_contributions', r'CONTRIBUTIONS\s*=\s*\['),
    ('crm_contributions', r'CRM_CONTRIBUTIONS\s*=\s*\['),
    ('swag_items', r'SWAG_ITEMS\s*=\s*\['),
]:
    m = re.search(pattern, txt)
    if m:
        chunk = txt[m.end():]
        count = 0
        depth = 1
        for ch in chunk:
            if ch == '(': count += 1
            elif ch == ']': break
        print(f'{name}: {count}')
"
```

On Mac/Linux replace `.venv/Scripts/python` with `.venv/bin/python`.

### 2 — Compare against docs

Read `docs/architecture.md` and `docs/requirements.md`, then diff against what you found in step 1. Focus on:
- Module list in both the architecture module sections and requirements file map
- Test file list in the requirements file map
- Test count in the Non-functional bullet (`test suite — N pytest tests`)
- Seed counts in the `app/seed.py` section of architecture.md

### 3 — Apply updates

Edit only the lines that are stale. Preserve all formatting, headings, and checkbox states for entries that are still accurate.

Common patterns:
- New module: add a `### app/new_module.py` section in architecture.md and a line in the file map in requirements.md
- New test file: add a line to the `tests/` block in the requirements.md file map
- New route group: add a row to the route table in architecture.md
- Test count changed: update the count in `docs/requirements.md` and in `.claude/skills/test/SKILL.md`
- Feature done: tick the corresponding checkbox in requirements.md

### 4 — Verify

Re-read both docs to confirm no stale lines remain.
