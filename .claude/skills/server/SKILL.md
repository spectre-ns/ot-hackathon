---
description: Kill any process on port 8000 and start the Kudos dev server (uvicorn). Use after code changes, after seeding, or when the Activity page or Admin Statistics tab returns "Not Found".
---

# server

Starts (or restarts) the Kudos FastAPI dev server on port 8000.

## Steps

### 1 — Free port 8000

On **Windows** (PowerShell):
```powershell
$owningPids = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
foreach ($procId in $owningPids) {
    taskkill /F /PID $procId 2>$null
}
Start-Sleep -Milliseconds 600
```

On **Mac/Linux** (Bash):
```bash
lsof -ti tcp:8000 | xargs kill -9 2>/dev/null; sleep 0.5
```

### 2 — Start uvicorn

**Windows:**
```
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Mac/Linux:**
```
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run in the background if you need to keep issuing commands, or in a dedicated terminal.

### 3 — Verify

```bash
curl -s http://localhost:8000/api/config | python -c "import sys,json; print('OK:', json.load(sys.stdin)['settings']['monthly_allowance'])"
```

Expected: `OK: 100`

## When "Not Found" on Activity or Admin Statistics

This always means the server process is stale — it predates a code change that added the route. Kill + restart is the fix. No DB changes needed unless you also want fresh seed data (invoke `/seed` first).

## Notes

- The server does **not** hot-reload by default. Add `--reload` for watch mode during active development (slightly slower).
- After a `/seed` run, sessions are wiped. Users must log in again.
- App is served at `http://localhost:8000`.
