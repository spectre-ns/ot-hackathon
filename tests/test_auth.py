"""Tests for authentication: demo login, session cookie, logout, 401 on protected routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestDemoLogin:
    def test_demo_login_returns_ok_and_user(self, client, users):
        user = users["user1"]
        resp = client.post("/api/auth/demo", json={"user_id": user["id"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["user"]["id"] == user["id"]
        assert data["user"]["name"] == user["name"]

    def test_demo_login_sets_session_cookie(self, client, users):
        user = users["user1"]
        resp = client.post("/api/auth/demo", json={"user_id": user["id"]})
        assert resp.status_code == 200
        # Cookie should be present in the response
        assert "kudos_session" in resp.cookies

    def test_demo_login_unknown_user_returns_404(self, client):
        resp = client.post("/api/auth/demo", json={"user_id": 99999})
        assert resp.status_code == 404

    def test_demo_login_admin_flag_reflected(self, client, users):
        admin = users["admin1"]
        resp = client.post("/api/auth/demo", json={"user_id": admin["id"]})
        assert resp.status_code == 200
        assert resp.json()["user"]["is_admin"] is True

    def test_demo_login_regular_user_not_admin(self, client, users):
        user = users["user1"]
        resp = client.post("/api/auth/demo", json={"user_id": user["id"]})
        assert resp.status_code == 200
        assert resp.json()["user"]["is_admin"] is False


class TestLogout:
    def test_logout_succeeds_when_logged_in(self, user1_client):
        resp = user1_client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_after_logout_protected_routes_return_401(self, user1_client):
        # Logout
        user1_client.post("/api/auth/logout")
        # Session cookie is gone; /api/me requires auth
        resp = user1_client.get("/api/me")
        assert resp.status_code == 401

    def test_logout_without_session_still_returns_ok(self, client):
        # No cookie at all; logout should still succeed gracefully
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200


class TestProtectedRoutes:
    def test_me_requires_auth(self, client):
        resp = client.get("/api/me")
        assert resp.status_code == 401

    def test_give_kudos_requires_auth(self, client, users):
        resp = client.post("/api/kudos", json={
            "receiver_id": users["user2"]["id"],
            "points": 5,
            "value_key": "great_teammate",
            "message": "great work",
        })
        assert resp.status_code == 401

    def test_swag_catalog_requires_auth(self, client):
        resp = client.get("/api/swag")
        assert resp.status_code == 401

    def test_admin_settings_requires_admin(self, user1_client):
        resp = user1_client.put("/api/settings", json={
            "pr_points": 10,
            "issue_points": 5,
            "monthly_allowance": 100,
            "github_accumulation_enabled": False,
            "crm_deal_closed_points": 25,
            "crm_contract_renewed_points": 20,
            "crm_escalation_resolved_points": 15,
            "crm_nps_positive_points": 10,
            "crm_ticket_resolved_points": 8,
            "crm_customer_call_points": 5,
        })
        assert resp.status_code == 403

    def test_admin_settings_accessible_by_admin(self, admin_client):
        resp = admin_client.put("/api/settings", json={
            "pr_points": 10,
            "issue_points": 5,
            "monthly_allowance": 100,
            "github_accumulation_enabled": False,
            "crm_deal_closed_points": 25,
            "crm_contract_renewed_points": 20,
            "crm_escalation_resolved_points": 15,
            "crm_nps_positive_points": 10,
            "crm_ticket_resolved_points": 8,
            "crm_customer_call_points": 5,
        })
        assert resp.status_code == 200

    def test_me_returns_user_info_when_authenticated(self, user1_client, users):
        resp = user1_client.get("/api/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == users["user1"]["id"]
        assert "giving_balance" in data
        assert "spendable_points" in data
        assert "unread_notifications" in data

    def test_public_feed_accessible_without_auth(self, client):
        # Feed is public (no auth required) — viewer is optional
        resp = client.get("/api/feed")
        assert resp.status_code == 200
