"""Tests for CRM webhook: X-CRM-Key auth, 6 event types, idempotency, points applied."""
from __future__ import annotations

import pytest


def _crm_key(seeded_db_or_adb=None) -> str:
    """Fetch the CRM API key from settings."""
    import app.db as adb
    return adb.get_settings()["crm_api_key"]


class TestCRMWebhookAuth:
    def test_missing_crm_key_returns_401(self, client, users, seeded_db):
        resp = client.post("/api/crm/event", json={
            "event_type": "deal_closed",
            "user_identifier": users["user1"]["email"],
            "reference_id": "OPP-TEST-AUTH-1",
        })
        assert resp.status_code == 401

    def test_wrong_crm_key_returns_401(self, client, users, seeded_db):
        resp = client.post("/api/crm/event",
            headers={"X-CRM-Key": "wrong-key-12345"},
            json={
                "event_type": "deal_closed",
                "user_identifier": users["user1"]["email"],
                "reference_id": "OPP-TEST-AUTH-2",
            })
        assert resp.status_code == 401

    def test_correct_crm_key_returns_200(self, client, users, seeded_db):
        key = _crm_key()
        resp = client.post("/api/crm/event",
            headers={"X-CRM-Key": key},
            json={
                "event_type": "deal_closed",
                "user_identifier": users["user1"]["email"],
                "reference_id": "OPP-AUTH-OK-1",
            })
        assert resp.status_code == 200


class TestCRMEventTypes:
    """All 6 event types should be accepted and award points."""

    @pytest.mark.parametrize("event_type,expected_min_points", [
        ("deal_closed", 1),
        ("contract_renewed", 1),
        ("escalation_resolved", 1),
        ("nps_positive", 1),
        ("ticket_resolved", 1),
        ("customer_call", 1),
    ])
    def test_event_type_awards_points(self, client, users, seeded_db, event_type, expected_min_points):
        key = _crm_key()
        import random
        ref_id = f"TEST-{event_type}-{random.randint(10000, 99999)}"
        resp = client.post("/api/crm/event",
            headers={"X-CRM-Key": key},
            json={
                "event_type": event_type,
                "user_identifier": users["user1"]["email"],
                "reference_id": ref_id,
                "company": "TestCo",
            })
        assert resp.status_code == 200, f"Event type '{event_type}' failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["points_awarded"] >= expected_min_points

    def test_unknown_event_type_returns_400(self, client, users, seeded_db):
        key = _crm_key()
        resp = client.post("/api/crm/event",
            headers={"X-CRM-Key": key},
            json={
                "event_type": "not_a_real_event",
                "user_identifier": users["user1"]["email"],
                "reference_id": "TEST-BAD-1",
            })
        assert resp.status_code == 400


class TestCRMIdempotency:
    def test_same_reference_id_not_duplicated(self, client, users, seeded_db):
        """Posting the same reference_id twice should return created=False the second time."""
        key = _crm_key()
        payload = {
            "event_type": "deal_closed",
            "user_identifier": users["user1"]["email"],
            "reference_id": "OPP-IDEMPOTENT-1",
            "company": "TestCo",
        }
        resp1 = client.post("/api/crm/event", headers={"X-CRM-Key": key}, json=payload)
        resp2 = client.post("/api/crm/event", headers={"X-CRM-Key": key}, json=payload)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["created"] is True
        assert resp2.json()["created"] is False
        # Second call should award 0 points
        assert resp2.json()["points_awarded"] == 0

    def test_different_reference_ids_create_separate_entries(self, client, users, seeded_db):
        key = _crm_key()
        for i in range(3):
            resp = client.post("/api/crm/event",
                headers={"X-CRM-Key": key},
                json={
                    "event_type": "customer_call",
                    "user_identifier": users["user1"]["email"],
                    "reference_id": f"CALL-UNIQUE-{i}",
                    "company": "TestCo",
                })
            assert resp.status_code == 200
            assert resp.json()["created"] is True


class TestCRMPointsApplied:
    def test_crm_event_increases_earned_points(self, client, users, seeded_db):
        import app.db as adb
        key = _crm_key()
        user = users["user1"]
        earned_before = adb.earned_points(user["id"])
        resp = client.post("/api/crm/event",
            headers={"X-CRM-Key": key},
            json={
                "event_type": "deal_closed",
                "user_identifier": user["email"],
                "reference_id": "OPP-POINTS-1",
                "company": "TestCo",
            })
        assert resp.status_code == 200
        points_awarded = resp.json()["points_awarded"]
        earned_after = adb.earned_points(user["id"])
        assert earned_after == earned_before + points_awarded

    def test_crm_user_can_be_identified_by_github_login(self, client, users, seeded_db):
        key = _crm_key()
        user = users["user1"]
        resp = client.post("/api/crm/event",
            headers={"X-CRM-Key": key},
            json={
                "event_type": "nps_positive",
                "user_identifier": user["github_login"],
                "reference_id": "NPS-BY-GH-1",
                "company": "TestCo",
            })
        assert resp.status_code == 200
        assert resp.json()["user"]["id"] == user["id"]

    def test_crm_user_not_found_returns_404(self, client, seeded_db):
        key = _crm_key()
        resp = client.post("/api/crm/event",
            headers={"X-CRM-Key": key},
            json={
                "event_type": "deal_closed",
                "user_identifier": "nobody@nowhere.example.com",
                "reference_id": "OPP-NOTFOUND-1",
            })
        assert resp.status_code == 404


class TestCRMSimulate:
    def test_simulate_requires_admin(self, user1_client, users):
        resp = user1_client.post("/api/crm/simulate", json={
            "event_type": "deal_closed",
            "user_identifier": users["user1"]["email"],
            "reference_id": "SIM-NOADMIN-1",
        })
        assert resp.status_code == 403

    def test_simulate_works_for_admin(self, admin_client, users, seeded_db):
        resp = admin_client.post("/api/crm/simulate", json={
            "event_type": "deal_closed",
            "user_identifier": users["user1"]["email"],
            "reference_id": "SIM-ADMIN-1",
            "company": "TestCo",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["points_awarded"] > 0

    def test_crm_events_list_requires_admin(self, user1_client):
        resp = user1_client.get("/api/crm/events")
        assert resp.status_code == 403

    def test_crm_events_list_for_admin(self, admin_client, users, seeded_db):
        import app.db as adb
        # Add a CRM contribution
        adb.upsert_crm_contribution(
            user_id=users["user1"]["id"], event_type="deal_closed",
            reference_id="OPP-LIST-1", title="Test Deal",
            company="TestCo", deal_value=50000, points=25,
            happened_at=adb.utcnow_iso(),
        )
        resp = admin_client.get("/api/crm/events")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1
        assert "event_label" in events[0]
        assert "user" in events[0]
