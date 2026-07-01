"""Three-tier role system: SuperAdmin > Admin > User."""
import pytest


class TestRoleFields:
    def test_create_user_defaults_to_user_role(self, seeded_db):
        import app.db as db
        u = db.create_user(name="Test", email="test@x.com", role="user")
        assert u["role"] == "user"
        assert u["is_admin"] is False

    def test_create_admin_sets_is_admin_true(self, seeded_db):
        import app.db as db
        u = db.create_user(name="Test Admin", email="tadmin@x.com", role="admin")
        assert u["role"] == "admin"
        assert u["is_admin"] is True

    def test_create_superadmin_sets_is_admin_true(self, seeded_db):
        import app.db as db
        u = db.create_user(name="Test SA", email="tsa@x.com", role="superadmin")
        assert u["role"] == "superadmin"
        assert u["is_admin"] is True

    def test_legacy_is_admin_true_becomes_superadmin(self, seeded_db):
        import app.db as db
        u = db.create_user(name="Legacy", email="legacy@x.com", is_admin=True)
        assert u["role"] == "superadmin"
        assert u["is_admin"] is True

    def test_set_user_role_updates_both_fields(self, seeded_db):
        import app.db as db
        u = seeded_db["user1"]
        updated = db.set_user_role(u["id"], "admin")
        assert updated["role"] == "admin"
        assert updated["is_admin"] is True

    def test_set_user_role_rejects_invalid(self, seeded_db):
        import app.db as db
        u = seeded_db["user1"]
        with pytest.raises(ValueError, match="Invalid role"):
            db.set_user_role(u["id"], "god")

    def test_superadmin_fixture_has_correct_role(self, seeded_db):
        assert seeded_db["admin1"]["role"] == "superadmin"
        assert seeded_db["admin1"]["is_admin"] is True

    def test_admin_basic_fixture_has_correct_role(self, seeded_db):
        assert seeded_db["admin_basic"]["role"] == "admin"
        assert seeded_db["admin_basic"]["is_admin"] is True

    def test_user_fixture_has_correct_role(self, seeded_db):
        assert seeded_db["user1"]["role"] == "user"
        assert seeded_db["user1"]["is_admin"] is False


class TestRoleAPI:
    def test_me_returns_role_field(self, admin_client):
        resp = admin_client.get("/api/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "superadmin"
        assert data["is_admin"] is True

    def test_users_list_returns_role(self, admin_client):
        resp = admin_client.get("/api/users")
        assert resp.status_code == 200
        users = resp.json()
        assert all("role" in u for u in users)

    def test_superadmin_can_change_role(self, admin_client, seeded_db):
        uid = seeded_db["user1"]["id"]
        resp = admin_client.put(f"/api/users/{uid}/role", json={"role": "admin"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"
        assert resp.json()["is_admin"] is True

    def test_superadmin_can_demote_to_user(self, admin_client, seeded_db):
        uid = seeded_db["user2"]["id"]
        resp = admin_client.put(f"/api/users/{uid}/role", json={"role": "user"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "user"
        assert resp.json()["is_admin"] is False

    def test_regular_admin_cannot_change_role(self, admin_basic_client, seeded_db):
        uid = seeded_db["user1"]["id"]
        resp = admin_basic_client.put(f"/api/users/{uid}/role", json={"role": "admin"})
        assert resp.status_code == 403

    def test_user_cannot_change_role(self, user1_client, seeded_db):
        uid = seeded_db["user2"]["id"]
        resp = user1_client.put(f"/api/users/{uid}/role", json={"role": "admin"})
        assert resp.status_code == 403

    def test_unauthenticated_cannot_change_role(self, client, seeded_db):
        uid = seeded_db["user1"]["id"]
        resp = client.put(f"/api/users/{uid}/role", json={"role": "admin"})
        assert resp.status_code == 401

    def test_invalid_role_returns_400(self, admin_client, seeded_db):
        uid = seeded_db["user1"]["id"]
        resp = admin_client.put(f"/api/users/{uid}/role", json={"role": "overlord"})
        assert resp.status_code == 400

    def test_nonexistent_user_returns_404(self, admin_client):
        resp = admin_client.put("/api/users/99999/role", json={"role": "admin"})
        assert resp.status_code == 404


class TestAdminPrivileges:
    def test_admin_can_access_pending_orders(self, admin_basic_client):
        resp = admin_basic_client.get("/api/swag/orders/pending")
        assert resp.status_code == 200

    def test_user_cannot_access_pending_orders(self, user1_client):
        resp = user1_client.get("/api/swag/orders/pending")
        assert resp.status_code == 403

    def test_admin_can_access_all_orders(self, admin_basic_client):
        resp = admin_basic_client.get("/api/swag/orders/all")
        assert resp.status_code == 200

    def test_user_cannot_access_settings(self, user1_client):
        resp = user1_client.put("/api/settings", json={
            "pr_points": 10, "issue_points": 5, "monthly_allowance": 100,
            "github_accumulation_enabled": False, "crm_accumulation_enabled": True,
            "crm_deal_closed_points": 25, "crm_contract_renewed_points": 20,
            "crm_escalation_resolved_points": 15, "crm_nps_positive_points": 10,
            "crm_ticket_resolved_points": 8, "crm_customer_call_points": 5,
        })
        assert resp.status_code == 403
