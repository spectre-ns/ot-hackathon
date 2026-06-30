"""Tests for leaderboard: ranking by period (month/all), points computed correctly."""
from __future__ import annotations

import pytest


class TestLeaderboard:
    def test_leaderboard_empty_when_no_kudos(self, client):
        resp = client.get("/api/leaderboard")
        assert resp.status_code == 200
        # Fresh DB with no kudos: everyone has 0 points so nobody appears
        assert resp.json() == []

    def test_leaderboard_default_period_is_month(self, client, user1_client, users):
        receiver = users["user2"]
        user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 20,
            "value_key": "great_teammate",
            "message": "Great work",
        })
        resp = client.get("/api/leaderboard")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        assert items[0]["user"]["id"] == receiver["id"]
        assert items[0]["points"] == 20

    def test_leaderboard_all_period(self, client, user1_client, users):
        receiver = users["user2"]
        user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 30,
            "value_key": "innovator",
            "message": "Brilliant!",
        })
        resp = client.get("/api/leaderboard?period=all")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        user_ids = [r["user"]["id"] for r in items]
        assert receiver["id"] in user_ids
        matching = next(r for r in items if r["user"]["id"] == receiver["id"])
        assert matching["points"] == 30

    def test_leaderboard_ranked_by_points_descending(self, user1_client, users):
        # user2 gets 30 pts, user3 gets 10 pts
        user1_client.post("/api/kudos", json={
            "receiver_id": users["user2"]["id"],
            "points": 30,
            "value_key": "innovator",
            "message": "First",
        })
        user1_client.post("/api/kudos", json={
            "receiver_id": users["user3"]["id"],
            "points": 10,
            "value_key": "mentor",
            "message": "Second",
        })
        resp = user1_client.get("/api/leaderboard?period=all")
        items = resp.json()
        assert len(items) >= 2
        assert items[0]["points"] >= items[1]["points"]
        # user2 should be ranked higher
        assert items[0]["user"]["id"] == users["user2"]["id"]

    def test_leaderboard_has_rank_field(self, user1_client, users):
        user1_client.post("/api/kudos", json={
            "receiver_id": users["user2"]["id"],
            "points": 10,
            "value_key": "great_teammate",
            "message": "Nice",
        })
        resp = user1_client.get("/api/leaderboard?period=all")
        items = resp.json()
        assert len(items) >= 1
        assert "rank" in items[0]
        assert items[0]["rank"] == 1

    def test_leaderboard_invalid_period_defaults_to_month(self, client):
        resp = client.get("/api/leaderboard?period=invalid")
        assert resp.status_code == 200
        # Should not error — silently defaults to month

    def test_leaderboard_points_exclude_github_when_accumulation_off(
            self, admin_client, user1_client, users, seeded_db):
        """When github_accumulation_enabled=False, GitHub contributions don't count."""
        import app.db as adb
        # Ensure accumulation is OFF
        adb.update_settings(
            pr_points=10, issue_points=5, monthly_allowance=100,
            github_accumulation_enabled=False,
            crm_deal_closed_points=25, crm_contract_renewed_points=20,
            crm_escalation_resolved_points=15, crm_nps_positive_points=10,
            crm_ticket_resolved_points=8, crm_customer_call_points=5,
        )
        # Add a GitHub contribution for user2
        adb.upsert_contribution(
            user_id=users["user2"]["id"], kind="pr",
            repo="openteams/platform", number=9001,
            title="Test PR", url="https://github.com/openteams/platform/pull/9001",
            points=10, happened_at=adb.utcnow_iso(),
        )
        # Also give peer kudos so user2 appears in leaderboard
        user1_client.post("/api/kudos", json={
            "receiver_id": users["user2"]["id"],
            "points": 5,
            "value_key": "great_teammate",
            "message": "Good work",
        })
        resp = user1_client.get("/api/leaderboard?period=all")
        user2_entry = next(
            (r for r in resp.json() if r["user"]["id"] == users["user2"]["id"]), None
        )
        # GitHub points (10) should NOT be included; only kudos (5)
        assert user2_entry is not None
        assert user2_entry["points"] == 5

    def test_leaderboard_points_include_github_when_accumulation_on(
            self, admin_client, user1_client, users, seeded_db):
        """When github_accumulation_enabled=True, GitHub contributions count."""
        import app.db as adb
        adb.update_settings(
            pr_points=10, issue_points=5, monthly_allowance=100,
            github_accumulation_enabled=True,
            crm_deal_closed_points=25, crm_contract_renewed_points=20,
            crm_escalation_resolved_points=15, crm_nps_positive_points=10,
            crm_ticket_resolved_points=8, crm_customer_call_points=5,
        )
        # Add GitHub contribution for user2 (in current month)
        adb.upsert_contribution(
            user_id=users["user2"]["id"], kind="pr",
            repo="openteams/platform", number=9002,
            title="Another Test PR", url="https://github.com/openteams/platform/pull/9002",
            points=10, happened_at=adb.utcnow_iso(),
        )
        resp = user1_client.get("/api/leaderboard?period=all")
        user2_entry = next(
            (r for r in resp.json() if r["user"]["id"] == users["user2"]["id"]), None
        )
        # GitHub points should be included
        assert user2_entry is not None
        assert user2_entry["points"] >= 10
