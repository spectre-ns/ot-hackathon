"""Tests for the activity feed: combined GitHub + CRM contributions, requires auth."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


class TestActivityFeed:
    def test_activity_requires_auth(self, client):
        resp = client.get("/api/activity")
        assert resp.status_code == 401

    def test_activity_empty_when_no_contributions(self, user1_client):
        resp = user1_client.get("/api/activity")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_activity_includes_github_contributions(self, user1_client, users, seeded_db):
        import app.db as adb
        adb.upsert_contribution(
            user_id=users["user1"]["id"], kind="pr",
            repo="openteams/platform", number=1001,
            title="Test PR", url="https://github.com/openteams/platform/pull/1001",
            points=10, happened_at=adb.utcnow_iso(),
        )
        resp = user1_client.get("/api/activity")
        assert resp.status_code == 200
        items = resp.json()
        gh_items = [i for i in items if i["source"] == "github"]
        assert len(gh_items) >= 1
        assert gh_items[0]["title"] == "Test PR"
        assert gh_items[0]["user"] is not None
        assert gh_items[0]["user"]["id"] == users["user1"]["id"]

    def test_activity_includes_crm_contributions(self, user1_client, users, seeded_db):
        import app.db as adb
        adb.upsert_crm_contribution(
            user_id=users["user1"]["id"], event_type="deal_closed",
            reference_id="OPP-ACT-1", title="Test Deal",
            company="TestCo", deal_value=50000, points=25,
            happened_at=adb.utcnow_iso(),
        )
        resp = user1_client.get("/api/activity")
        assert resp.status_code == 200
        items = resp.json()
        crm_items = [i for i in items if i["source"] == "crm"]
        assert len(crm_items) >= 1
        assert crm_items[0]["event_label"] is not None
        assert crm_items[0]["event_emoji"] is not None
        assert crm_items[0]["user"] is not None

    def test_activity_items_have_source_field(self, user1_client, users, seeded_db):
        import app.db as adb
        adb.upsert_contribution(
            user_id=users["user1"]["id"], kind="issue",
            repo="openteams/platform", number=2001,
            title="Source Test Issue", url="https://github.com/openteams/platform/issues/2001",
            points=5, happened_at=adb.utcnow_iso(),
        )
        resp = user1_client.get("/api/activity")
        items = resp.json()
        assert len(items) >= 1
        for item in items:
            assert "source" in item
            assert item["source"] in ("github", "crm")

    def test_activity_sorted_newest_first(self, user1_client, users, seeded_db):
        import app.db as adb
        now = datetime.now(timezone.utc)
        older = (now - timedelta(hours=2)).isoformat()
        newer = (now - timedelta(minutes=5)).isoformat()
        adb.upsert_contribution(
            user_id=users["user1"]["id"], kind="pr",
            repo="openteams/platform", number=3001,
            title="Older PR", url="https://github.com/openteams/platform/pull/3001",
            points=10, happened_at=older,
        )
        adb.upsert_contribution(
            user_id=users["user1"]["id"], kind="issue",
            repo="openteams/platform", number=3002,
            title="Newer Issue", url="https://github.com/openteams/platform/issues/3002",
            points=5, happened_at=newer,
        )
        resp = user1_client.get("/api/activity")
        items = resp.json()
        assert len(items) >= 2
        assert items[0]["happened_at"] >= items[1]["happened_at"]

    def test_activity_limit_param(self, user1_client, users, seeded_db):
        import app.db as adb
        for i in range(5):
            adb.upsert_contribution(
                user_id=users["user1"]["id"], kind="pr",
                repo="openteams/platform", number=4000 + i,
                title=f"PR {i}", url=f"https://github.com/openteams/platform/pull/{4000 + i}",
                points=10, happened_at=adb.utcnow_iso(),
            )
        resp = user1_client.get("/api/activity?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) <= 3

    def test_activity_mixes_github_and_crm(self, user1_client, users, seeded_db):
        import app.db as adb
        adb.upsert_contribution(
            user_id=users["user1"]["id"], kind="pr",
            repo="openteams/platform", number=5001,
            title="Mixed PR", url="https://github.com/openteams/platform/pull/5001",
            points=10, happened_at=adb.utcnow_iso(),
        )
        adb.upsert_crm_contribution(
            user_id=users["user2"]["id"], event_type="nps_positive",
            reference_id="NPS-ACT-2", title="NPS 10 from Acme",
            company="Acme", deal_value=None, points=10,
            happened_at=adb.utcnow_iso(),
        )
        resp = user1_client.get("/api/activity")
        items = resp.json()
        sources = {i["source"] for i in items}
        assert "github" in sources
        assert "crm" in sources

    def test_activity_award_kudos_data_present(self, user1_client, users, seeded_db):
        """Activity items must carry user.id so the frontend can pre-fill Award kudos."""
        import app.db as adb
        adb.upsert_contribution(
            user_id=users["user1"]["id"], kind="pr",
            repo="openteams/platform", number=6001,
            title="Award Test PR", url="https://github.com/openteams/platform/pull/6001",
            points=10, happened_at=adb.utcnow_iso(),
        )
        resp = user1_client.get("/api/activity")
        items = resp.json()
        gh_items = [i for i in items if i["source"] == "github"]
        assert len(gh_items) >= 1
        item = gh_items[0]
        assert item["user"] is not None
        assert "id" in item["user"]
        # GitHub items carry url for the artifact link
        assert "url" in item
