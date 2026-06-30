"""Tests for notifications: admin notified on order, owner on transition, mark-read."""
from __future__ import annotations

import pytest


def _create_item_and_fund_user(admin_client, giver_client, user_id, cost=50):
    """Create a swag item and give the user enough points to order it."""
    resp = admin_client.post("/api/swag", json={
        "name": "Notify Test Item",
        "description": "",
        "point_cost": cost,
        "image_url": "",
        "stock": None,
        "is_available": True,
    })
    assert resp.status_code == 200
    item = resp.json()
    giver_client.post("/api/kudos", json={
        "receiver_id": user_id,
        "points": cost + 10,
        "value_key": "great_teammate",
        "message": "Here are points for swag",
    })
    return item


class TestOrderNotifications:
    def test_admin_notified_when_order_placed(
            self, admin_client, user1_client, user2_client, users):
        """All admins receive a notification when any user places a swag order."""
        admin = users["admin1"]
        item = _create_item_and_fund_user(
            admin_client, user2_client, users["user1"]["id"], 50)
        # Check initial unread count for admin
        before = admin_client.get("/api/me").json()["unread_notifications"]
        # User1 places an order
        user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        # Admin should have more unread notifications
        after = admin_client.get("/api/me").json()["unread_notifications"]
        assert after > before

    def test_admin_notification_content(
            self, admin_client, user1_client, user2_client, users, seeded_db):
        import app.db as adb
        item = _create_item_and_fund_user(
            admin_client, user2_client, users["user1"]["id"], 50)
        user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        # Check the notification exists for admin1
        notifs = adb.notifications_for(users["admin1"]["id"])
        assert len(notifs) >= 1
        # Should mention the user's name and the item
        messages = [n["message"] for n in notifs]
        assert any(users["user1"]["name"] in msg for msg in messages)

    def test_both_admins_notified(
            self, admin_client, admin2_client, user1_client, user2_client, users, seeded_db):
        import app.db as adb
        item = _create_item_and_fund_user(
            admin_client, user2_client, users["user1"]["id"], 50)
        before_admin1 = len(adb.notifications_for(users["admin1"]["id"]))
        before_admin2 = len(adb.notifications_for(users["admin2"]["id"]))
        user1_client.post(f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        after_admin1 = len(adb.notifications_for(users["admin1"]["id"]))
        after_admin2 = len(adb.notifications_for(users["admin2"]["id"]))
        assert after_admin1 > before_admin1
        assert after_admin2 > before_admin2


class TestTransitionNotifications:
    def test_owner_notified_on_transition(
            self, admin_client, user1_client, user2_client, users, seeded_db):
        import app.db as adb
        item = _create_item_and_fund_user(
            admin_client, user2_client, users["user1"]["id"], 50)
        order_resp = user1_client.post(
            f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        order_id = order_resp.json()["id"]
        owner_uid = users["user1"]["id"]
        before = len(adb.notifications_for(owner_uid))
        # Admin approves
        admin_client.post(f"/api/swag/orders/{order_id}/transition", json={
            "transition_id": "t_approve1",
            "reason": "",
        })
        after = len(adb.notifications_for(owner_uid))
        assert after > before

    def test_transition_notification_mentions_item(
            self, admin_client, user1_client, user2_client, users, seeded_db):
        import app.db as adb
        item = _create_item_and_fund_user(
            admin_client, user2_client, users["user1"]["id"], 50)
        order_resp = user1_client.post(
            f"/api/swag/{item['id']}/order", json={"item_id": item["id"]})
        order_id = order_resp.json()["id"]
        admin_client.post(f"/api/swag/orders/{order_id}/transition", json={
            "transition_id": "t_approve1",
            "reason": "",
        })
        notifs = adb.notifications_for(users["user1"]["id"])
        messages = [n["message"] for n in notifs]
        assert any("Notify Test Item" in msg for msg in messages)


class TestNotificationEndpoints:
    def test_get_notifications_requires_auth(self, client):
        resp = client.get("/api/notifications")
        assert resp.status_code == 401

    def test_get_notifications_returns_list(self, user1_client):
        resp = user1_client.get("/api/notifications")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_unread_count_in_me_endpoint(self, user1_client, users, seeded_db):
        import app.db as adb
        adb.create_notification(users["user1"]["id"], "Test notification", kind="info")
        resp = user1_client.get("/api/me")
        assert resp.json()["unread_notifications"] >= 1

    def test_mark_all_read_clears_unread_count(self, user1_client, users, seeded_db):
        import app.db as adb
        # Create some unread notifications
        adb.create_notification(users["user1"]["id"], "Notif 1", kind="info")
        adb.create_notification(users["user1"]["id"], "Notif 2", kind="success")
        assert adb.unread_count(users["user1"]["id"]) == 2
        # Mark all read
        resp = user1_client.post("/api/notifications/read")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert adb.unread_count(users["user1"]["id"]) == 0

    def test_mark_read_requires_auth(self, client):
        resp = client.post("/api/notifications/read")
        assert resp.status_code == 401

    def test_notifications_newest_first(self, user1_client, users, seeded_db):
        import app.db as adb
        adb.create_notification(users["user1"]["id"], "First notification")
        adb.create_notification(users["user1"]["id"], "Second notification")
        resp = user1_client.get("/api/notifications")
        notifs = resp.json()
        if len(notifs) >= 2:
            # Check descending order
            assert notifs[0]["created_at"] >= notifs[-1]["created_at"]

    def test_unread_count_decrements_after_mark_read(
            self, user1_client, users, seeded_db):
        import app.db as adb
        adb.create_notification(users["user1"]["id"], "A notification")
        before = user1_client.get("/api/me").json()["unread_notifications"]
        assert before >= 1
        user1_client.post("/api/notifications/read")
        after = user1_client.get("/api/me").json()["unread_notifications"]
        assert after == 0
