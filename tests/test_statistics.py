"""Tests for the admin-only statistics dashboard (replaces the public leaderboard)."""
from __future__ import annotations

import pytest


class TestStatisticsAccess:
    def test_requires_auth(self, client):
        resp = client.get("/api/admin/statistics")
        assert resp.status_code == 401

    def test_regular_user_forbidden(self, user1_client):
        resp = user1_client.get("/api/admin/statistics")
        assert resp.status_code == 403

    def test_admin_role_can_access(self, admin_basic_client):
        """role=admin (not just superadmin) can view statistics."""
        resp = admin_basic_client.get("/api/admin/statistics")
        assert resp.status_code == 200

    def test_superadmin_can_access(self, admin_client):
        resp = admin_client.get("/api/admin/statistics")
        assert resp.status_code == 200


class TestStatisticsData:
    def test_empty_state(self, admin_client):
        resp = admin_client.get("/api/admin/statistics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["kudos_count"] == 0
        assert data["points_awarded"] == 0
        assert data["top_earners"] == []

    def test_reflects_kudos_given(self, admin_client, user1_client, users):
        receiver = users["user2"]
        user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 20,
            "value_key": "great_teammate",
            "message": "Great work",
        })
        resp = admin_client.get("/api/admin/statistics")
        data = resp.json()
        assert data["kudos_count"] == 1
        assert data["kudos_points"] == 20
        assert data["points_awarded"] == 20
        assert data["people_recognized"] == 1

    def test_top_earners_ranked_and_capped(self, admin_client, user1_client, users):
        user1_client.post("/api/kudos", json={
            "receiver_id": users["user2"]["id"],
            "points": 30, "value_key": "innovator", "message": "First",
        })
        user1_client.post("/api/kudos", json={
            "receiver_id": users["user3"]["id"],
            "points": 10, "value_key": "mentor", "message": "Second",
        })
        resp = admin_client.get("/api/admin/statistics")
        earners = resp.json()["top_earners"]
        assert len(earners) >= 2
        assert earners[0]["points"] >= earners[1]["points"]
        assert earners[0]["user"]["id"] == users["user2"]["id"]
        assert earners[0]["rank"] == 1

    def test_includes_role_counts(self, admin_client):
        resp = admin_client.get("/api/admin/statistics")
        data = resp.json()
        assert "role_counts" in data
        assert sum(data["role_counts"].values()) == data["total_users"]

    def test_includes_value_breakdown(self, admin_client, user1_client, users):
        user1_client.post("/api/kudos", json={
            "receiver_id": users["user2"]["id"],
            "points": 15, "value_key": "innovator", "message": "Nice",
        })
        resp = admin_client.get("/api/admin/statistics")
        breakdown = resp.json()["value_breakdown"]
        assert any(v["value"]["key"] == "innovator" and v["count"] == 1 for v in breakdown)


class TestLeaderboardRemoved:
    def test_public_leaderboard_endpoint_gone(self, client):
        """No JSON API route for /api/leaderboard; unmatched paths fall through to the SPA shell."""
        resp = client.get("/api/leaderboard")
        assert "application/json" not in resp.headers.get("content-type", "")
