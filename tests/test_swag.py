"""Tests for swag: catalog listing, order placement, spendable_points, stock limits."""
from __future__ import annotations

import pytest


def _create_swag_item(admin_client, name="Test T-Shirt", cost=50, stock=None):
    payload = {
        "name": name,
        "description": "A test item",
        "point_cost": cost,
        "image_url": "",
        "stock": stock,
        "is_available": True,
    }
    resp = admin_client.post("/api/swag", json=payload)
    assert resp.status_code == 200, f"Failed to create swag item: {resp.text}"
    return resp.json()


def _give_kudos_to(giver_client, receiver_id, points, value_key="great_teammate"):
    resp = giver_client.post("/api/kudos", json={
        "receiver_id": receiver_id,
        "points": points,
        "value_key": value_key,
        "message": f"Good work ({points} pts)",
    })
    assert resp.status_code == 200, f"Failed to give kudos: {resp.text}"
    return resp.json()


class TestSwagCatalog:
    def test_catalog_requires_auth(self, client):
        resp = client.get("/api/swag")
        assert resp.status_code == 401

    def test_catalog_empty_initially(self, user1_client):
        resp = user1_client.get("/api/swag")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []

    def test_catalog_shows_items_after_creation(self, admin_client, user1_client):
        _create_swag_item(admin_client, "Hoodie", 150)
        resp = user1_client.get("/api/swag")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Hoodie"

    def test_catalog_includes_spendable_points(self, user1_client):
        resp = user1_client.get("/api/swag")
        assert "spendable_points" in resp.json()

    def test_catalog_sorted_by_cost_ascending(self, admin_client, user1_client):
        _create_swag_item(admin_client, "Expensive", 500)
        _create_swag_item(admin_client, "Cheap", 50)
        _create_swag_item(admin_client, "Medium", 200)
        resp = user1_client.get("/api/swag")
        costs = [i["point_cost"] for i in resp.json()["items"]]
        assert costs == sorted(costs)

    def test_unavailable_items_hidden_from_regular_user(self, admin_client, user1_client):
        item = _create_swag_item(admin_client, "Hidden Item", 100)
        # Mark as unavailable
        admin_client.put(f"/api/swag/{item['id']}", json={
            "name": "Hidden Item",
            "description": "",
            "point_cost": 100,
            "image_url": "",
            "stock": None,
            "is_available": False,
        })
        resp = user1_client.get("/api/swag")
        names = [i["name"] for i in resp.json()["items"]]
        assert "Hidden Item" not in names

    def test_create_swag_requires_admin(self, user1_client):
        resp = user1_client.post("/api/swag", json={
            "name": "Unauthorized Item",
            "description": "",
            "point_cost": 50,
        })
        assert resp.status_code == 403


class TestSwagOrderPlacement:
    def test_place_order_succeeds(self, admin_client, user1_client, user2_client, users):
        item = _create_swag_item(admin_client, "T-Shirt", 50)
        # Give user1 enough kudos to afford the item
        _give_kudos_to(user2_client, users["user1"]["id"], 60)
        resp = user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"], "notes": "Size M"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == item["id"]
        assert data["points_cost"] == 50

    def test_order_requires_auth(self, admin_client, client):
        item = _create_swag_item(admin_client, "T-Shirt 2", 50)
        resp = client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        assert resp.status_code == 401

    def test_order_fails_insufficient_points(self, admin_client, user1_client, users):
        item = _create_swag_item(admin_client, "Expensive Hoodie", 9999)
        resp = user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        assert resp.status_code == 400
        assert "points" in resp.json()["detail"].lower()

    def test_order_unavailable_item_returns_404(self, admin_client, user1_client, user2_client, users):
        item = _create_swag_item(admin_client, "Unavailable Item", 50)
        admin_client.put(f"/api/swag/{item['id']}", json={
            "name": "Unavailable Item",
            "description": "",
            "point_cost": 50,
            "image_url": "",
            "stock": None,
            "is_available": False,
        })
        _give_kudos_to(user2_client, users["user1"]["id"], 100)
        resp = user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        assert resp.status_code == 404

    def test_spendable_points_decremented_after_order(
            self, admin_client, user1_client, user2_client, users):
        item = _create_swag_item(admin_client, "50pt Item", 50)
        _give_kudos_to(user2_client, users["user1"]["id"], 80)
        # Check before
        spendable_before = user1_client.get("/api/swag").json()["spendable_points"]
        user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        # Check after
        spendable_after = user1_client.get("/api/swag").json()["spendable_points"]
        assert spendable_after == spendable_before - 50

    def test_spendable_points_equals_earned_minus_committed(
            self, admin_client, user1_client, user2_client, users, seeded_db):
        import app.db as adb
        item = _create_swag_item(admin_client, "100pt Item", 100)
        # Give user1 150 pts
        _give_kudos_to(user2_client, users["user1"]["id"], 100)
        # Give more from admin to get to 150
        admin_client.post("/api/kudos", json={
            "receiver_id": users["user1"]["id"],
            "points": 50,
            "value_key": "above_beyond",
            "message": "Great work",
        })
        uid = users["user1"]["id"]
        earned = adb.earned_points(uid)
        user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        redeemed = adb.redeemed_points(uid)
        expected_spendable = max(0, earned - redeemed)
        actual_spendable = adb.spendable_points(uid)
        assert actual_spendable == expected_spendable

    def test_pending_order_commits_points(self, admin_client, user1_client, user2_client, users, seeded_db):
        """A pending (not yet approved) order still reduces spendable_points."""
        import app.db as adb
        item = _create_swag_item(admin_client, "200pt Item", 200)
        _give_kudos_to(user2_client, users["user1"]["id"], 100)
        admin_client.post("/api/kudos", json={
            "receiver_id": users["user1"]["id"],
            "points": 100,
            "value_key": "innovator",
            "message": "Double the points",
        })
        uid = users["user1"]["id"]
        spendable_before = adb.spendable_points(uid)
        user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        spendable_after = adb.spendable_points(uid)
        assert spendable_after == spendable_before - 200

    def test_my_orders_endpoint(self, admin_client, user1_client, user2_client, users):
        item = _create_swag_item(admin_client, "My Orders Item", 50)
        _give_kudos_to(user2_client, users["user1"]["id"], 60)
        user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        resp = user1_client.get("/api/swag/orders")
        assert resp.status_code == 200
        orders = resp.json()
        assert len(orders) >= 1

    def test_pending_orders_admin_endpoint(self, admin_client, user1_client, user2_client, users):
        item = _create_swag_item(admin_client, "Pending Item", 50)
        _give_kudos_to(user2_client, users["user1"]["id"], 60)
        user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        resp = admin_client.get("/api/swag/orders/pending")
        assert resp.status_code == 200
        orders = resp.json()
        assert len(orders) >= 1

    def test_pending_orders_requires_admin(self, user1_client):
        resp = user1_client.get("/api/swag/orders/pending")
        assert resp.status_code == 403

    def test_order_has_initial_workflow_state(self, admin_client, user1_client, user2_client, users):
        item = _create_swag_item(admin_client, "Workflow Item", 50)
        _give_kudos_to(user2_client, users["user1"]["id"], 60)
        resp = user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        order = resp.json()
        assert order["current_state"] == "pending"
