"""Tests for the activity feed: returns enriched kudos, reactions toggle."""
from __future__ import annotations

import pytest


class TestFeed:
    def test_feed_returns_list(self, client):
        resp = client.get("/api/feed")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_feed_starts_empty(self, client):
        """Fresh DB has no kudos."""
        resp = client.get("/api/feed")
        assert resp.json() == []

    def test_feed_returns_kudos_after_giving(self, user1_client, user2_client, users):
        receiver = users["user2"]
        user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 10,
            "value_key": "great_teammate",
            "message": "Fantastic work!",
        })
        resp = user2_client.get("/api/feed")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["message"] == "Fantastic work!"

    def test_feed_items_are_enriched(self, user1_client, users):
        """Feed items must have giver, receiver, value, reactions."""
        receiver = users["user2"]
        user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 5,
            "value_key": "innovator",
            "message": "Bright idea!",
        })
        resp = user1_client.get("/api/feed")
        item = resp.json()[0]
        assert "giver" in item
        assert "receiver" in item
        assert "value" in item
        assert "reactions" in item
        assert item["giver"] is not None
        assert item["receiver"] is not None

    def test_feed_sorted_newest_first(self, user1_client, users):
        import app.db as adb
        from datetime import datetime, timedelta, timezone
        receiver = users["user2"]
        giver = users["user1"]
        now = datetime.now(timezone.utc)
        # Insert with explicit timestamps so ordering is deterministic on fast hardware
        adb.create_kudos(giver["id"], receiver["id"], 1, "mentor", "first",
                         created_at=(now - timedelta(minutes=2)).isoformat())
        adb.create_kudos(giver["id"], receiver["id"], 1, "mentor", "second",
                         created_at=(now - timedelta(minutes=1)).isoformat())
        adb.create_kudos(giver["id"], receiver["id"], 1, "mentor", "third",
                         created_at=now.isoformat())
        resp = user1_client.get("/api/feed")
        messages = [item["message"] for item in resp.json()]
        # Most recently created is first; all three should be present
        assert set(messages) == {"first", "second", "third"}
        # The last one added (with the latest timestamp) should appear first
        assert messages[0] == "third"

    def test_feed_limit_param(self, user1_client, users):
        receiver = users["user2"]
        for i in range(5):
            user1_client.post("/api/kudos", json={
                "receiver_id": receiver["id"],
                "points": 1,
                "value_key": "great_teammate",
                "message": f"kudos {i}",
            })
        resp = user1_client.get("/api/feed?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 3


class TestReactions:
    def test_add_reaction_returns_added(self, user1_client, user2_client, users):
        receiver = users["user2"]
        # Give kudos
        kudos_resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 5,
            "value_key": "great_teammate",
            "message": "React to me!",
        })
        kudos_id = kudos_resp.json()["id"]
        # React
        resp = user2_client.post(f"/api/kudos/{kudos_id}/react", json={"emoji": "🎉"})
        assert resp.status_code == 200
        assert resp.json()["action"] == "added"

    def test_reaction_appears_on_kudos(self, user1_client, user2_client, users):
        receiver = users["user2"]
        kudos_resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 5,
            "value_key": "great_teammate",
            "message": "React to me!",
        })
        kudos_id = kudos_resp.json()["id"]
        user2_client.post(f"/api/kudos/{kudos_id}/react", json={"emoji": "👍"})
        # Check feed
        feed = user2_client.get("/api/feed").json()
        item = next(i for i in feed if i["id"] == kudos_id)
        reactions = {r["emoji"]: r for r in item["reactions"]}
        assert "👍" in reactions
        assert reactions["👍"]["count"] == 1
        assert reactions["👍"]["mine"] is True

    def test_reaction_toggle_removes_on_second_call(self, user1_client, user2_client, users):
        receiver = users["user2"]
        kudos_resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 5,
            "value_key": "great_teammate",
            "message": "Toggle me!",
        })
        kudos_id = kudos_resp.json()["id"]
        # Add
        user2_client.post(f"/api/kudos/{kudos_id}/react", json={"emoji": "❤️"})
        # Remove
        resp = user2_client.post(f"/api/kudos/{kudos_id}/react", json={"emoji": "❤️"})
        assert resp.json()["action"] == "removed"
        # Verify gone
        feed = user2_client.get("/api/feed").json()
        item = next(i for i in feed if i["id"] == kudos_id)
        emoji_list = [r["emoji"] for r in item["reactions"]]
        assert "❤️" not in emoji_list

    def test_react_to_nonexistent_kudos_returns_404(self, user1_client):
        resp = user1_client.post("/api/kudos/99999/react", json={"emoji": "👍"})
        assert resp.status_code == 404

    def test_react_requires_auth(self, client):
        resp = client.post("/api/kudos/1/react", json={"emoji": "👍"})
        assert resp.status_code == 401

    def test_mine_flag_false_for_other_user(self, user1_client, user2_client, users):
        """The 'mine' flag on a reaction should be False for a user who didn't react."""
        receiver = users["user2"]
        kudos_resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 5,
            "value_key": "great_teammate",
            "message": "Reactions test",
        })
        kudos_id = kudos_resp.json()["id"]
        # user2 reacts
        user2_client.post(f"/api/kudos/{kudos_id}/react", json={"emoji": "🔥"})
        # user1 checks the feed - they didn't react
        feed = user1_client.get("/api/feed").json()
        item = next(i for i in feed if i["id"] == kudos_id)
        reactions = {r["emoji"]: r for r in item["reactions"]}
        assert reactions["🔥"]["mine"] is False
