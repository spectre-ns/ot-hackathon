"""Tests for user profiles: returns GitHub/CRM contribution tabs, kudos history."""
from __future__ import annotations

import pytest


class TestProfile:
    def test_get_profile_returns_user_data(self, client, users):
        user = users["user1"]
        resp = client.get(f"/api/users/{user['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["id"] == user["id"]
        assert data["user"]["name"] == user["name"]

    def test_get_profile_unknown_user_returns_404(self, client):
        resp = client.get("/api/users/99999")
        assert resp.status_code == 404

    def test_profile_has_contribution_tabs(self, client, users):
        user = users["user1"]
        resp = client.get(f"/api/users/{user['id']}")
        data = resp.json()
        assert "github_contributions" in data
        assert "crm_contributions" in data
        assert isinstance(data["github_contributions"], list)
        assert isinstance(data["crm_contributions"], list)

    def test_profile_has_kudos_history(self, client, user1_client, users):
        receiver = users["user1"]
        # Give some kudos to user1
        user2_id = users["user2"]["id"]
        # We need to be user2 to give kudos; use user2_client
        from app.main import app
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            c.post("/api/auth/demo", json={"user_id": users["user2"]["id"]})
            c.post("/api/kudos", json={
                "receiver_id": receiver["id"],
                "points": 10,
                "value_key": "mentor",
                "message": "Great mentor!",
            })
        resp = client.get(f"/api/users/{receiver['id']}")
        data = resp.json()
        assert "received" in data
        assert len(data["received"]) >= 1
        assert data["kudos_count"] >= 1

    def test_profile_has_points_data(self, client, users):
        user = users["user1"]
        resp = client.get(f"/api/users/{user['id']}")
        data = resp.json()
        assert "earned_points" in data
        assert "earned_this_month" in data
        assert isinstance(data["earned_points"], int)

    def test_profile_has_value_breakdown(self, client, users):
        user = users["user1"]
        resp = client.get(f"/api/users/{user['id']}")
        data = resp.json()
        assert "value_breakdown" in data
        assert isinstance(data["value_breakdown"], list)

    def test_profile_github_contributions_appear(self, client, users, seeded_db):
        import app.db as adb
        user = users["user1"]
        # Insert a GitHub contribution for user1
        adb.upsert_contribution(
            user_id=user["id"], kind="pr",
            repo="openteams/platform", number=8001,
            title="My PR", url="https://github.com/openteams/platform/pull/8001",
            points=10, happened_at=adb.utcnow_iso(),
        )
        resp = client.get(f"/api/users/{user['id']}")
        data = resp.json()
        assert len(data["github_contributions"]) >= 1
        contrib = data["github_contributions"][0]
        assert contrib["kind"] == "pr"
        assert contrib["repo"] == "openteams/platform"

    def test_profile_crm_contributions_appear(self, client, users, seeded_db):
        import app.db as adb
        user = users["user1"]
        adb.upsert_crm_contribution(
            user_id=user["id"], event_type="deal_closed",
            reference_id="OPP-TEST-1", title="Test Deal",
            company="TestCo", deal_value=10000, points=25,
            happened_at=adb.utcnow_iso(),
        )
        resp = client.get(f"/api/users/{user['id']}")
        data = resp.json()
        assert len(data["crm_contributions"]) >= 1
        contrib = data["crm_contributions"][0]
        assert contrib["event_type"] == "deal_closed"

    def test_list_users_endpoint(self, client, users):
        resp = client.get("/api/users")
        assert resp.status_code == 200
        user_list = resp.json()
        assert isinstance(user_list, list)
        assert len(user_list) == 6  # 2 superadmins + 1 admin + 3 regular users seeded

    def test_list_users_sorted_alphabetically(self, client):
        resp = client.get("/api/users")
        names = [u["name"] for u in resp.json()]
        assert names == sorted(names, key=str.lower)

    def test_given_count_tracked(self, client, user1_client, users):
        receiver = users["user2"]
        user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 5,
            "value_key": "great_teammate",
            "message": "Nice work",
        })
        resp = client.get(f"/api/users/{users['user1']['id']}")
        data = resp.json()
        assert data["given_count"] >= 1
