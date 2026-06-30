"""Tests for settings: admin can update weights; non-admin gets 403."""
from __future__ import annotations

import pytest


VALID_SETTINGS = {
    "pr_points": 15,
    "issue_points": 7,
    "monthly_allowance": 200,
    "github_accumulation_enabled": True,
    "crm_deal_closed_points": 30,
    "crm_contract_renewed_points": 25,
    "crm_escalation_resolved_points": 20,
    "crm_nps_positive_points": 12,
    "crm_ticket_resolved_points": 10,
    "crm_customer_call_points": 6,
}


class TestSettingsRead:
    def test_read_settings_is_public(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200

    def test_settings_has_expected_fields(self, client):
        resp = client.get("/api/settings")
        data = resp.json()
        assert "pr_points" in data
        assert "issue_points" in data
        assert "monthly_allowance" in data
        assert "github_accumulation_enabled" in data
        assert "crm_api_key" in data

    def test_default_github_accumulation_is_false(self, client):
        resp = client.get("/api/settings")
        assert resp.json()["github_accumulation_enabled"] is False

    def test_default_monthly_allowance(self, client):
        resp = client.get("/api/settings")
        assert resp.json()["monthly_allowance"] == 100  # DEFAULT_MONTHLY_ALLOWANCE

    def test_api_config_endpoint(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "core_values" in data
        assert "crm_event_types" in data
        assert "settings" in data


class TestSettingsWrite:
    def test_non_admin_cannot_update_settings(self, user1_client):
        resp = user1_client.put("/api/settings", json=VALID_SETTINGS)
        assert resp.status_code == 403

    def test_admin_can_update_settings(self, admin_client):
        resp = admin_client.put("/api/settings", json=VALID_SETTINGS)
        assert resp.status_code == 200

    def test_settings_actually_updated(self, admin_client):
        resp = admin_client.put("/api/settings", json=VALID_SETTINGS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["pr_points"] == 15
        assert data["issue_points"] == 7
        assert data["monthly_allowance"] == 200
        assert data["github_accumulation_enabled"] is True

    def test_update_monthly_allowance_affects_giving_balance(
            self, admin_client, user1_client):
        """Changing the monthly allowance should immediately affect giving_balance."""
        new_allowance = 250
        admin_client.put("/api/settings", json={**VALID_SETTINGS, "monthly_allowance": new_allowance})
        me = user1_client.get("/api/me").json()
        assert me["monthly_allowance"] == new_allowance
        assert me["giving_balance"] <= new_allowance

    def test_update_github_accumulation_to_true(self, admin_client):
        resp = admin_client.put("/api/settings", json={**VALID_SETTINGS, "github_accumulation_enabled": True})
        assert resp.json()["github_accumulation_enabled"] is True

    def test_update_github_accumulation_to_false(self, admin_client):
        # First enable it
        admin_client.put("/api/settings", json={**VALID_SETTINGS, "github_accumulation_enabled": True})
        # Then disable
        resp = admin_client.put("/api/settings", json={**VALID_SETTINGS, "github_accumulation_enabled": False})
        assert resp.json()["github_accumulation_enabled"] is False

    def test_update_crm_points_affects_new_events(self, admin_client, users, seeded_db):
        """Updating CRM points affects newly processed events."""
        import app.db as adb
        # Set deal_closed to 50 points
        admin_client.put("/api/settings", json={**VALID_SETTINGS, "crm_deal_closed_points": 50})
        key = adb.get_settings()["crm_api_key"]
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            resp = c.post("/api/crm/event",
                headers={"X-CRM-Key": key},
                json={
                    "event_type": "deal_closed",
                    "user_identifier": users["user1"]["email"],
                    "reference_id": "OPP-CUSTOM-PTS-1",
                    "company": "TestCo",
                })
        assert resp.status_code == 200
        assert resp.json()["points_awarded"] == 50

    def test_unauthenticated_cannot_update_settings(self, client):
        resp = client.put("/api/settings", json=VALID_SETTINGS)
        assert resp.status_code == 401

    def test_settings_validation_rejects_negative_pr_points(self, admin_client):
        bad = {**VALID_SETTINGS, "pr_points": -1}
        resp = admin_client.put("/api/settings", json=bad)
        assert resp.status_code == 422

    def test_settings_validation_rejects_oversized_allowance(self, admin_client):
        bad = {**VALID_SETTINGS, "monthly_allowance": 999999}
        resp = admin_client.put("/api/settings", json=bad)
        assert resp.status_code == 422
