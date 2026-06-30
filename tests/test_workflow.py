"""Tests for the workflow state machine: states, transitions, audit log."""
from __future__ import annotations

import json
import pytest


def _create_swag_item(admin_client, name="Test Item", cost=50):
    resp = admin_client.post("/api/swag", json={
        "name": name, "description": "", "point_cost": cost,
        "image_url": "", "stock": None, "is_available": True,
    })
    assert resp.status_code == 200
    return resp.json()


def _give_points(giver_client, receiver_id, points):
    resp = giver_client.post("/api/kudos", json={
        "receiver_id": receiver_id,
        "points": points,
        "value_key": "great_teammate",
        "message": "Points for swag",
    })
    assert resp.status_code == 200


def _place_order(user_client, item_id):
    resp = user_client.post(f"/api/swag/{item_id}/order", json={"item_id": item_id})
    assert resp.status_code == 200
    return resp.json()


class TestDefaultWorkflow:
    def test_workflow_has_default_states(self, admin_client):
        resp = admin_client.get("/api/workflow")
        assert resp.status_code == 200
        wf = resp.json()
        state_ids = {s["id"] for s in wf["states"]}
        assert "pending" in state_ids
        assert "approved" in state_ids
        assert "rejected" in state_ids
        assert "shipped" in state_ids

    def test_workflow_has_initial_state(self, admin_client):
        resp = admin_client.get("/api/workflow")
        wf = resp.json()
        initial = [s for s in wf["states"] if s.get("is_initial")]
        assert len(initial) == 1
        assert initial[0]["id"] == "pending"

    def test_workflow_has_terminal_states(self, admin_client):
        resp = admin_client.get("/api/workflow")
        wf = resp.json()
        terminals = [s for s in wf["states"] if s.get("is_terminal")]
        terminal_ids = {s["id"] for s in terminals}
        assert "shipped" in terminal_ids
        assert "rejected" in terminal_ids

    def test_get_workflow_requires_auth(self, client):
        resp = client.get("/api/workflow")
        assert resp.status_code == 401


class TestWorkflowStates:
    def test_add_state(self, admin_client):
        resp = admin_client.post("/api/workflow/states", json={
            "name": "Under Legal Review",
            "color": "#FF5733",
            "is_terminal": False,
        })
        assert resp.status_code == 200
        wf = resp.json()
        state_names = [s["name"] for s in wf["states"]]
        assert "Under Legal Review" in state_names

    def test_add_terminal_state(self, admin_client):
        resp = admin_client.post("/api/workflow/states", json={
            "name": "Cancelled",
            "color": "#888888",
            "is_terminal": True,
        })
        assert resp.status_code == 200
        wf = resp.json()
        cancelled = next(s for s in wf["states"] if s["name"] == "Cancelled")
        assert cancelled["is_terminal"] is True

    def test_delete_state(self, admin_client):
        # Add a state first
        add_resp = admin_client.post("/api/workflow/states", json={
            "name": "Temp State",
            "color": "#123456",
            "is_terminal": False,
        })
        wf = add_resp.json()
        temp_state = next(s for s in wf["states"] if s["name"] == "Temp State")
        # Delete it
        resp = admin_client.delete(f"/api/workflow/states/{temp_state['id']}")
        assert resp.status_code == 200
        final_wf = resp.json()
        state_names = [s["name"] for s in final_wf["states"]]
        assert "Temp State" not in state_names

    def test_cannot_delete_initial_state(self, admin_client):
        resp = admin_client.delete("/api/workflow/states/pending")
        assert resp.status_code == 400

    def test_add_state_requires_admin(self, user1_client):
        resp = user1_client.post("/api/workflow/states", json={
            "name": "Unauthorized State",
            "color": "#000",
            "is_terminal": False,
        })
        assert resp.status_code == 403


class TestWorkflowTransitions:
    def test_add_transition(self, admin_client):
        # Add a state to transition to
        admin_client.post("/api/workflow/states", json={
            "name": "Backordered",
            "color": "#FF9900",
            "is_terminal": False,
        })
        wf = admin_client.get("/api/workflow").json()
        backorder_state = next(s for s in wf["states"] if s["name"] == "Backordered")
        resp = admin_client.post("/api/workflow/transitions", json={
            "from_state": "pending",
            "to_state": backorder_state["id"],
            "label": "Put on Backorder",
            "requires_admin": True,
            "requires_reason": False,
        })
        assert resp.status_code == 200
        wf = resp.json()
        labels = [t["label"] for t in wf["transitions"]]
        assert "Put on Backorder" in labels

    def test_delete_transition(self, admin_client):
        wf = admin_client.get("/api/workflow").json()
        # Get the first transition (e.g. t_review)
        t = wf["transitions"][0]
        # TestClient.delete() doesn't accept json= directly; pass body via content.
        resp = admin_client.request(
            "DELETE", "/api/workflow/transitions",
            content=json.dumps({"transition_id": t["id"]}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        updated_wf = resp.json()
        t_ids = [tr["id"] for tr in updated_wf["transitions"]]
        assert t["id"] not in t_ids

    def test_transition_to_unknown_state_returns_400(self, admin_client):
        resp = admin_client.post("/api/workflow/transitions", json={
            "from_state": "pending",
            "to_state": "nonexistent_state",
            "label": "Bad Transition",
            "requires_admin": True,
            "requires_reason": False,
        })
        assert resp.status_code == 400


class TestOrderTransitions:
    def test_advance_order_through_workflow(
            self, admin_client, user1_client, user2_client, users):
        """Approve an order: pending -> approved -> shipped."""
        item = _create_swag_item(admin_client)
        _give_points(user2_client, users["user1"]["id"], 60)
        order = _place_order(user1_client, item["id"])
        order_id = order["id"]
        assert order["current_state"] == "pending"

        # Approve (pending -> approved)
        resp = admin_client.post(f"/api/swag/orders/{order_id}/transition", json={
            "transition_id": "t_approve1",
            "reason": "",
        })
        assert resp.status_code == 200
        assert resp.json()["current_state"] == "approved"

        # Ship (approved -> shipped)
        resp = admin_client.post(f"/api/swag/orders/{order_id}/transition", json={
            "transition_id": "t_ship",
            "reason": "",
        })
        assert resp.status_code == 200
        assert resp.json()["current_state"] == "shipped"

    def test_transition_blocked_from_wrong_state(
            self, admin_client, user1_client, user2_client, users):
        """Can't apply a transition whose 'from' doesn't match current state."""
        item = _create_swag_item(admin_client, "Wrong State Item", 50)
        _give_points(user2_client, users["user1"]["id"], 60)
        order = _place_order(user1_client, item["id"])
        order_id = order["id"]
        # t_ship is from 'approved', not 'pending'
        resp = admin_client.post(f"/api/swag/orders/{order_id}/transition", json={
            "transition_id": "t_ship",
            "reason": "",
        })
        assert resp.status_code == 400

    def test_transition_from_terminal_state_blocked(
            self, admin_client, user1_client, user2_client, users):
        """Once in a terminal state, no further transitions are valid."""
        item = _create_swag_item(admin_client, "Terminal Item", 50)
        _give_points(user2_client, users["user1"]["id"], 60)
        order = _place_order(user1_client, item["id"])
        order_id = order["id"]
        # Reject it (with reason)
        admin_client.post(f"/api/swag/orders/{order_id}/transition", json={
            "transition_id": "t_reject1",
            "reason": "Out of stock",
        })
        # Try to approve from rejected — should fail
        resp = admin_client.post(f"/api/swag/orders/{order_id}/transition", json={
            "transition_id": "t_approve1",
            "reason": "",
        })
        assert resp.status_code == 400

    def test_audit_log_populated_on_transition(
            self, admin_client, user1_client, user2_client, users, seeded_db):
        import app.db as adb
        item = _create_swag_item(admin_client, "Audit Log Item", 50)
        _give_points(user2_client, users["user1"]["id"], 60)
        order = _place_order(user1_client, item["id"])
        order_id = order["id"]
        admin_client.post(f"/api/swag/orders/{order_id}/transition", json={
            "transition_id": "t_approve1",
            "reason": "",
        })
        updated = adb.get_swag_order(order_id)
        assert len(updated["transition_log"]) >= 1
        log_entry = updated["transition_log"][0]
        assert log_entry["from"] == "pending"
        assert log_entry["to"] == "approved"
        assert "at" in log_entry
        assert "actor_id" in log_entry

    def test_reject_requires_reason(
            self, admin_client, user1_client, user2_client, users):
        item = _create_swag_item(admin_client, "Rejection Test Item", 50)
        _give_points(user2_client, users["user1"]["id"], 60)
        order = _place_order(user1_client, item["id"])
        order_id = order["id"]
        # Reject without reason should fail
        resp = admin_client.post(f"/api/swag/orders/{order_id}/transition", json={
            "transition_id": "t_reject1",
            "reason": "",
        })
        assert resp.status_code == 400

    def test_admin_transition_blocked_for_regular_user(
            self, admin_client, user1_client, user2_client, users):
        item = _create_swag_item(admin_client, "Admin Only Transition", 50)
        _give_points(user2_client, users["user1"]["id"], 60)
        order = _place_order(user1_client, item["id"])
        order_id = order["id"]
        # t_approve1 requires_admin=True
        resp = user1_client.post(f"/api/swag/orders/{order_id}/transition", json={
            "transition_id": "t_approve1",
            "reason": "",
        })
        assert resp.status_code == 403
