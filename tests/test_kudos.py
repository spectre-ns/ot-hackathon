"""Tests for peer kudos: give, receive, self-kudos blocked, balance enforced, artifact fields."""
from __future__ import annotations

import pytest


class TestGiveKudos:
    def test_give_kudos_succeeds(self, user1_client, users):
        receiver = users["user2"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 10,
            "value_key": "great_teammate",
            "message": "Awesome collaboration!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["points"] == 10
        assert data["receiver"]["id"] == receiver["id"]
        assert data["message"] == "Awesome collaboration!"

    def test_give_kudos_returns_enriched_kudos(self, user1_client, users):
        receiver = users["user2"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 5,
            "value_key": "innovator",
            "message": "Great idea!",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Enriched fields
        assert "giver" in data
        assert "receiver" in data
        assert "value" in data
        assert "reactions" in data
        assert data["giver"] is not None
        assert data["receiver"] is not None

    def test_self_kudos_rejected(self, user1_client, users):
        user = users["user1"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": user["id"],
            "points": 10,
            "value_key": "great_teammate",
            "message": "I'm the best!",
        })
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()

    def test_unknown_receiver_rejected(self, user1_client):
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": 99999,
            "points": 10,
            "value_key": "great_teammate",
            "message": "Hello ghost",
        })
        assert resp.status_code == 404

    def test_unknown_value_key_rejected(self, user1_client, users):
        receiver = users["user2"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 10,
            "value_key": "not_a_real_value",
            "message": "Testing invalid value",
        })
        assert resp.status_code == 400

    def test_balance_enforced(self, user1_client, users):
        """Giving more points than the monthly balance should be rejected.

        The monthly allowance is 100 by default. Drain the balance first by
        giving 100 pts legitimately, then try to give 1 more — that must fail
        with 400 (not 422 which is a schema error).
        """
        import app.db as adb
        receiver = users["user2"]
        # Give the full allowance in one shot to drain the balance.
        user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 100,
            "value_key": "great_teammate",
            "message": "Using up all the balance",
        })
        # Now the balance is 0; any amount > 0 should be rejected.
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 1,
            "value_key": "great_teammate",
            "message": "Should fail — no balance left",
        })
        assert resp.status_code == 400
        assert "points" in resp.json()["detail"].lower()

    def test_balance_decrements_after_giving(self, user1_client, users):
        """After giving kudos, /api/me giving_balance should decrease."""
        me_before = user1_client.get("/api/me").json()
        balance_before = me_before["giving_balance"]

        receiver = users["user2"]
        user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 10,
            "value_key": "great_teammate",
            "message": "Good job",
        })

        me_after = user1_client.get("/api/me").json()
        assert me_after["giving_balance"] == balance_before - 10

    def test_artifact_url_and_label_stored(self, user1_client, users):
        receiver = users["user2"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 5,
            "value_key": "innovator",
            "message": "Great PR!",
            "artifact_url": "https://github.com/org/repo/pull/42",
            "artifact_label": "PR #42: Add feature X",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["artifact_url"] == "https://github.com/org/repo/pull/42"
        assert data["artifact_label"] == "PR #42: Add feature X"

    def test_kudos_without_artifact_has_empty_strings(self, user1_client, users):
        receiver = users["user2"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 5,
            "value_key": "mentor",
            "message": "Great mentoring!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["artifact_url"] == ""
        assert data["artifact_label"] == ""

    def test_give_kudos_increments_receiver_earned_points(self, user1_client, user2_client, users):
        """Giving kudos to user2 should increase user2's earned_points."""
        me_before = user2_client.get("/api/me").json()
        earned_before = me_before["earned_points"]

        receiver = users["user2"]
        user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 15,
            "value_key": "above_beyond",
            "message": "Outstanding work!",
        })

        me_after = user2_client.get("/api/me").json()
        assert me_after["earned_points"] == earned_before + 15

    def test_points_must_be_at_least_1(self, user1_client, users):
        receiver = users["user2"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 0,
            "value_key": "great_teammate",
            "message": "Zero points test",
        })
        assert resp.status_code == 422  # Pydantic validation: ge=1

    def test_message_cannot_be_empty(self, user1_client, users):
        receiver = users["user2"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 5,
            "value_key": "great_teammate",
            "message": "",
        })
        assert resp.status_code == 422  # Pydantic validation: min_length=1

    def test_all_core_values_accepted(self, user1_client, users):
        receiver = users["user2"]
        for value_key in ["great_teammate", "client_hero", "crisis_crusher",
                           "above_beyond", "innovator", "mentor"]:
            resp = user1_client.post("/api/kudos", json={
                "receiver_id": receiver["id"],
                "points": 1,
                "value_key": value_key,
                "message": f"Testing {value_key}",
            })
            assert resp.status_code == 200, f"Value key '{value_key}' should be accepted"
