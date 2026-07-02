"""Swag-order approval workflow engine.

Admins define a state machine (states + directed transitions) through the UI.
Orders start in the initial state and move through transitions until they reach
a terminal state. All transition history is appended to the order document.

Default workflow mirrors a simple e-commerce flow:
  Pending ──→ Approved ──→ Shipped
     └──────────────────→ Rejected (from either Pending or Approved)

Admins can add intermediate states (e.g. "Under Review") or new paths
("Backordered", "Cancelled") without touching any backend code.
"""
from __future__ import annotations

import uuid

DEFAULT_WORKFLOW = {
    "states": [
        {"id": "pending",      "name": "Pending",      "color": "#FAA944",
         "is_initial": True,  "is_terminal": False},
        {"id": "under_review", "name": "Under Review",  "color": "#4D75FE",
         "is_initial": False, "is_terminal": False},
        {"id": "approved",     "name": "Approved",      "color": "#2E9E6B",
         "is_initial": False, "is_terminal": False},
        {"id": "shipped",      "name": "Shipped",       "color": "#000F3A",
         "is_initial": False, "is_terminal": True},
        {"id": "rejected",     "name": "Rejected",      "color": "#FF8A69",
         "is_initial": False, "is_terminal": True},
    ],
    "transitions": [
        {"id": "t_review",   "from": "pending",      "to": "under_review",
         "label": "Start Review",   "requires_admin": True,  "requires_reason": False},
        {"id": "t_approve1", "from": "pending",      "to": "approved",
         "label": "Approve",        "requires_admin": True,  "requires_reason": False},
        {"id": "t_approve2", "from": "under_review", "to": "approved",
         "label": "Approve",        "requires_admin": True,  "requires_reason": False},
        {"id": "t_ship",     "from": "approved",     "to": "shipped",
         "label": "Mark Shipped",   "requires_admin": True,  "requires_reason": False},
        {"id": "t_reject1",  "from": "pending",      "to": "rejected",
         "label": "Reject",         "requires_admin": True,  "requires_reason": True},
        {"id": "t_reject2",  "from": "under_review", "to": "rejected",
         "label": "Reject",         "requires_admin": True,  "requires_reason": True},
    ],
}


def initial_state(wf: dict) -> str:
    for s in wf["states"]:
        if s.get("is_initial"):
            return s["id"]
    return wf["states"][0]["id"] if wf["states"] else "pending"


def is_terminal(wf: dict, state_id: str) -> bool:
    for s in wf["states"]:
        if s["id"] == state_id:
            return s.get("is_terminal", False)
    return False  # unknown state treated as active, not terminal


def available_transitions(wf: dict, current_state: str) -> list[dict]:
    return [t for t in wf["transitions"] if t["from"] == current_state]


def find_transition(wf: dict, transition_id: str) -> dict | None:
    for t in wf["transitions"]:
        if t["id"] == transition_id:
            return t
    return None


def state_info(wf: dict, state_id: str) -> dict:
    for s in wf["states"]:
        if s["id"] == state_id:
            return s
    return {"id": state_id, "name": state_id.title(), "color": "#888", "is_terminal": False}


def make_state_id(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")[:32]


def add_state(wf: dict, name: str, color: str, is_terminal: bool) -> dict:
    wf = dict(wf)
    wf["states"] = list(wf["states"])
    sid = make_state_id(name)
    # Ensure unique id
    existing = {s["id"] for s in wf["states"]}
    base = sid
    i = 2
    while sid in existing:
        sid = f"{base}_{i}"; i += 1
    wf["states"].append({
        "id": sid, "name": name, "color": color,
        "is_initial": False, "is_terminal": is_terminal,
    })
    return wf


def delete_state(wf: dict, state_id: str) -> dict:
    # Can't delete the initial state.
    wf = dict(wf)
    init = initial_state(wf)
    if state_id == init:
        raise ValueError("Cannot delete the initial state.")
    wf["states"] = [s for s in wf["states"] if s["id"] != state_id]
    # Remove transitions that reference this state.
    wf["transitions"] = [t for t in wf["transitions"]
                         if t["from"] != state_id and t["to"] != state_id]
    return wf


def add_transition(wf: dict, from_state: str, to_state: str, label: str,
                   requires_admin: bool, requires_reason: bool) -> dict:
    wf = dict(wf)
    wf["transitions"] = list(wf["transitions"])
    wf["transitions"].append({
        "id": f"t_{uuid.uuid4().hex[:8]}",
        "from": from_state, "to": to_state,
        "label": label,
        "requires_admin": requires_admin,
        "requires_reason": requires_reason,
    })
    return wf


def delete_transition(wf: dict, transition_id: str) -> dict:
    wf = dict(wf)
    wf["transitions"] = [t for t in wf["transitions"] if t["id"] != transition_id]
    return wf
