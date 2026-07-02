"""Shared test fixtures for the Kudos recognition platform.

Each test gets a fresh in-memory-style TinyDB backed by a temp file.
The module-level _db handle in app.db is reset between tests so there
is no cross-test state leakage.

Key design decisions:
- We patch app.config.DATABASE_FILE before reinitializing the DB handle
  (app.db._db = None) so that get_db() picks up the temp path.
- The fixture seeds a minimal but realistic dataset: 2 admins, 3 regular
  users, the default workflow, and the default settings.
- `client` is a plain TestClient (no auth cookie).
- `logged_in_client(user_dict)` returns a TestClient that has a valid
  session cookie for the given user.
"""
from __future__ import annotations

import tempfile
import os
import pytest

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers used at fixture-construction time
# ---------------------------------------------------------------------------

ADMIN1 = dict(
    name="Ada Lovelace",
    email="ada@test.com",
    title="Principal Engineer",
    department="Platform",
    avatar_color="#000F3A",
    github_login="ada-lovelace",
    role="superadmin",
)
ADMIN2 = dict(
    name="Grace Hopper",
    email="grace@test.com",
    title="Engineering Manager",
    department="Platform",
    avatar_color="#4D75FE",
    github_login="gracehopper",
    role="superadmin",
)
ADMIN_BASIC = dict(
    name="Margaret Hamilton",
    email="margaret@test.com",
    title="Engineer",
    department="Platform",
    avatar_color="#7C5CFF",
    github_login="mhamilton",
    role="admin",
)
USER1 = dict(
    name="Alan Turing",
    email="alan@test.com",
    title="Staff Engineer",
    department="Infrastructure",
    avatar_color="#2E9E6B",
    github_login="alanturing",
    role="user",
)
USER2 = dict(
    name="Katherine Johnson",
    email="katherine@test.com",
    title="Senior Engineer",
    department="Data",
    avatar_color="#FAA944",
    github_login="katherinej",
    role="user",
)
USER3 = dict(
    name="Linus Torvalds",
    email="linus@test.com",
    title="Senior Engineer",
    department="Infrastructure",
    avatar_color="#FF8A69",
    github_login="torvalds",
    role="user",
)


@pytest.fixture
def db_path(tmp_path):
    """Return a temp file path for TinyDB (one per test)."""
    return str(tmp_path / "test_kudos.json")


@pytest.fixture
def seeded_db(db_path, monkeypatch):
    """
    Patch DATABASE_FILE, reset the module-level DB handle, seed minimal
    data, and yield a dict with the created user records keyed by role.

    Teardown: close the DB and re-reset the handle so the next test is clean.
    """
    # Patch the config before any DB calls
    import app.config as cfg
    monkeypatch.setattr(cfg, "DATABASE_FILE", db_path)

    # Also patch the value that was already imported into app.db
    import app.db as adb
    monkeypatch.setattr(adb, "DATABASE_FILE", db_path)

    # Reset the singleton so get_db() opens the temp file
    adb._db = None

    # Seed
    admin1      = adb.create_user(**ADMIN1)
    admin2      = adb.create_user(**ADMIN2)
    admin_basic = adb.create_user(**ADMIN_BASIC)
    user1       = adb.create_user(**USER1)
    user2       = adb.create_user(**USER2)
    user3       = adb.create_user(**USER3)

    # Ensure settings and workflow are initialized
    adb.get_settings()
    adb.get_workflow()

    yield {
        "admin1":      admin1,
        "admin2":      admin2,
        "admin_basic": admin_basic,
        "user1":       user1,
        "user2":       user2,
        "user3":       user3,
    }

    # Teardown
    if adb._db is not None:
        adb._db.close()
    adb._db = None


@pytest.fixture
def client(seeded_db):
    """Unauthenticated TestClient with a fresh seeded DB."""
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def users(seeded_db):
    """Expose the seeded users dict directly."""
    return seeded_db


def make_logged_in_client(app, user: dict):
    """
    Create a TestClient that carries a valid session cookie for *user*.
    Uses the demo-login endpoint so we exercise the real auth path.
    """
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post("/api/auth/demo", json={"user_id": user["id"]})
        assert resp.status_code == 200, f"Demo login failed: {resp.text}"
        # The cookie is stored in the client's cookie jar automatically
        yield c


@pytest.fixture
def admin_client(seeded_db):
    """TestClient authenticated as admin1 (Ada Lovelace)."""
    from app.main import app
    admin = seeded_db["admin1"]
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post("/api/auth/demo", json={"user_id": admin["id"]})
        assert resp.status_code == 200
        yield c


@pytest.fixture
def admin2_client(seeded_db):
    """TestClient authenticated as admin2 (Grace Hopper)."""
    from app.main import app
    admin = seeded_db["admin2"]
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post("/api/auth/demo", json={"user_id": admin["id"]})
        assert resp.status_code == 200
        yield c


@pytest.fixture
def admin_basic_client(seeded_db):
    """TestClient authenticated as admin_basic (Alan Turing, role=admin)."""
    from app.main import app
    user = seeded_db["admin_basic"]
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post("/api/auth/demo", json={"user_id": user["id"]})
        assert resp.status_code == 200
        yield c


@pytest.fixture
def user1_client(seeded_db):
    """TestClient authenticated as user1 (Alan Turing)."""
    from app.main import app
    user = seeded_db["user1"]
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post("/api/auth/demo", json={"user_id": user["id"]})
        assert resp.status_code == 200
        yield c


@pytest.fixture
def user2_client(seeded_db):
    """TestClient authenticated as user2 (Katherine Johnson)."""
    from app.main import app
    user = seeded_db["user2"]
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post("/api/auth/demo", json={"user_id": user["id"]})
        assert resp.status_code == 200
        yield c


@pytest.fixture
def full_seed_client(db_path, monkeypatch):
    """TestClient backed by the REAL app seed (app/seed.py).

    Runs seed.run() so tests can verify that production seed data
    produces a correct application state (e.g. the activity feed and
    admin statistics dashboard are populated after seeding).
    """
    import app.config as cfg
    monkeypatch.setattr(cfg, "DATABASE_FILE", db_path)
    import app.db as adb
    monkeypatch.setattr(adb, "DATABASE_FILE", db_path)
    adb._db = None

    from app.seed import run as seed_run
    seed_run()

    from app.main import app
    # Log in as Ada Lovelace (first user, always admin after seed)
    with TestClient(app, raise_server_exceptions=True) as c:
        users = adb.all_users()
        ada = next(u for u in users if u["name"] == "Ada Lovelace")
        resp = c.post("/api/auth/demo", json={"user_id": ada["id"]})
        assert resp.status_code == 200
        yield c

    if adb._db is not None:
        adb._db.close()
    adb._db = None
