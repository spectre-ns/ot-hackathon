"""NoSQL data layer backed by TinyDB (an embedded JSON document store).

TinyDB gives us a Mongo-style document/collection model with zero external
server: everything lives in a single JSON file. Each "table" is a collection;
each document's integer ``doc_id`` is its id. We expose a small repository of
functions so the rest of the app never touches TinyDB directly.

A module-level RLock serializes ALL reads and writes because TinyDB's
JSONStorage shares a single file handle — concurrent reads on FastAPI's
threadpool would otherwise interleave seek() calls and corrupt reads.
"""
from __future__ import annotations

import secrets
import threading
from datetime import datetime, timezone

from tinydb import Query, TinyDB

from .config import DATABASE_FILE, DEFAULT_MONTHLY_ALLOWANCE
from .crm_events import CRM_SETTINGS_DEFAULTS

_lock = threading.RLock()
_db: TinyDB | None = None


def get_db() -> TinyDB:
    global _db
    if _db is None:
        _db = TinyDB(DATABASE_FILE)
    return _db


def _table(name: str):
    return get_db().table(name)


# --- helpers ------------------------------------------------------------------
def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _with_id(doc) -> dict | None:
    if doc is None:
        return None
    out = dict(doc)
    out["id"] = doc.doc_id
    return out


# --- users --------------------------------------------------------------------
ADMIN_ROLES = {"admin", "superadmin"}


def _role_is_admin(role: str) -> bool:
    return role in ADMIN_ROLES


def create_user(**fields) -> dict:
    with _lock:
        fields.setdefault("created_at", utcnow_iso())
        # Infer role from legacy is_admin if not explicitly provided
        if "role" not in fields:
            fields["role"] = "superadmin" if fields.get("is_admin") else "user"
        fields["is_admin"] = _role_is_admin(fields["role"])
        fields.setdefault("avatar_color", "#4D75FE")
        fields.setdefault("avatar_url", "")
        fields.setdefault("title", "")
        fields.setdefault("department", "")
        uid = _table("users").insert(fields)
        return get_user(uid)


def get_user(uid: int) -> dict | None:
    with _lock:
        return _with_id(_table("users").get(doc_id=uid))


def _first(table_name: str, cond) -> dict | None:
    with _lock:
        res = _table(table_name).get(cond)
        return _with_id(res) if res else None


def get_user_by_email(email: str) -> dict | None:
    return _first("users", Query().email == email)


def get_user_by_github_id(github_id: int) -> dict | None:
    return _first("users", Query().github_id == github_id)


def get_user_by_github_login(login: str) -> dict | None:
    q = Query()
    return _first("users", q.github_login.test(
        lambda v: isinstance(v, str) and v.lower() == login.lower()))


def all_users() -> list[dict]:
    with _lock:
        return [_with_id(d) for d in _table("users").all()]


def update_user(uid: int, **fields) -> dict | None:
    with _lock:
        _table("users").update(fields, doc_ids=[uid])
    return get_user(uid)


def set_user_role(uid: int, role: str) -> dict | None:
    if role not in ("user", "admin", "superadmin"):
        raise ValueError(f"Invalid role: {role!r}")
    if not get_user(uid):
        return None
    return update_user(uid, role=role, is_admin=_role_is_admin(role))


# --- kudos --------------------------------------------------------------------
def create_kudos(giver_id: int, receiver_id: int, points: int,
                 value_key: str, message: str,
                 created_at: str | None = None,
                 artifact_url: str | None = None,
                 artifact_label: str | None = None) -> dict:
    with _lock:
        kid = _table("kudos").insert({
            "giver_id": giver_id,
            "receiver_id": receiver_id,
            "points": points,
            "value_key": value_key,
            "message": message,
            "created_at": created_at or utcnow_iso(),
            "artifact_url": artifact_url or "",
            "artifact_label": artifact_label or "",
        })
    return get_kudos(kid)


def get_kudos(kid: int) -> dict | None:
    with _lock:
        return _with_id(_table("kudos").get(doc_id=kid))


def all_kudos() -> list[dict]:
    with _lock:
        return [_with_id(d) for d in _table("kudos").all()]


def kudos_received(uid: int) -> list[dict]:
    with _lock:
        return [_with_id(d) for d in _table("kudos").search(Query().receiver_id == uid)]


def kudos_given(uid: int) -> list[dict]:
    with _lock:
        return [_with_id(d) for d in _table("kudos").search(Query().giver_id == uid)]


# --- reactions ----------------------------------------------------------------
def toggle_reaction(kudos_id: int, user_id: int, emoji: str) -> str:
    q = Query()
    with _lock:
        existing = _table("reactions").get(
            (q.kudos_id == kudos_id) & (q.user_id == user_id) & (q.emoji == emoji))
        if existing:
            _table("reactions").remove(doc_ids=[existing.doc_id])
            return "removed"
        _table("reactions").insert({
            "kudos_id": kudos_id, "user_id": user_id,
            "emoji": emoji, "created_at": utcnow_iso(),
        })
        return "added"


def reactions_for(kudos_id: int) -> list[dict]:
    with _lock:
        return [_with_id(d) for d in _table("reactions").search(Query().kudos_id == kudos_id)]


# --- GitHub contributions -----------------------------------------------------
def upsert_contribution(user_id: int, kind: str, repo: str, number: int,
                        title: str, url: str, points: int,
                        happened_at: str) -> tuple[dict, bool]:
    """Insert or refresh a GitHub contribution. Returns (doc, created)."""
    q = Query()
    with _lock:
        existing = _table("github_contributions").get(
            (q.kind == kind) & (q.repo == repo) & (q.number == number))
        if existing:
            _table("github_contributions").update(
                {"points": points}, doc_ids=[existing.doc_id])
            return get_contribution(existing.doc_id), False
        cid = _table("github_contributions").insert({
            "user_id": user_id, "kind": kind, "repo": repo, "number": number,
            "title": title, "url": url, "points": points,
            "happened_at": happened_at, "synced_at": utcnow_iso(),
        })
        return get_contribution(cid), True


def get_contribution(cid: int) -> dict | None:
    with _lock:
        return _with_id(_table("github_contributions").get(doc_id=cid))


def contributions_for(uid: int) -> list[dict]:
    with _lock:
        return [_with_id(d) for d in
                _table("github_contributions").search(Query().user_id == uid)]


def all_contributions() -> list[dict]:
    with _lock:
        return [_with_id(d) for d in _table("github_contributions").all()]


# --- CRM contributions --------------------------------------------------------
def upsert_crm_contribution(user_id: int, event_type: str, reference_id: str,
                             title: str, company: str, deal_value: int | None,
                             points: int, happened_at: str,
                             artifact_url: str = "") -> tuple[dict, bool]:
    """Insert or refresh a CRM contribution. Unique per (event_type, reference_id)."""
    q = Query()
    with _lock:
        existing = _table("crm_contributions").get(
            (q.event_type == event_type) & (q.reference_id == reference_id))
        if existing:
            _table("crm_contributions").update(
                {"points": points}, doc_ids=[existing.doc_id])
            return _get_crm(existing.doc_id), False
        cid = _table("crm_contributions").insert({
            "user_id": user_id,
            "event_type": event_type,
            "reference_id": reference_id,
            "title": title,
            "company": company,
            "deal_value": deal_value,
            "points": points,
            "happened_at": happened_at,
            "synced_at": utcnow_iso(),
            "artifact_url": artifact_url,
        })
        return _get_crm(cid), True


def _get_crm(cid: int) -> dict | None:
    with _lock:
        return _with_id(_table("crm_contributions").get(doc_id=cid))


def crm_contributions_for(uid: int) -> list[dict]:
    with _lock:
        return [_with_id(d) for d in
                _table("crm_contributions").search(Query().user_id == uid)]


def all_crm_contributions() -> list[dict]:
    with _lock:
        return [_with_id(d) for d in _table("crm_contributions").all()]


# --- settings (singleton) ----------------------------------------------------
def get_settings() -> dict:
    with _lock:
        t = _table("settings")
        rows = t.all()
        if not rows:
            doc = {
                "pr_points": 10,
                "issue_points": 5,
                "monthly_allowance": DEFAULT_MONTHLY_ALLOWANCE,
                # GitHub accumulation off by default (manual/curated mode).
                "github_accumulation_enabled": False,
                # CRM accumulation on by default — CRM events always award points.
                "crm_accumulation_enabled": True,
                "crm_api_key": secrets.token_urlsafe(24),
                **CRM_SETTINGS_DEFAULTS,
            }
            t.insert(doc)
            rows = t.all()
        row = _with_id(rows[0])
        # Backfill keys added after initial creation (safe on old DBs).
        missing = {
            "github_accumulation_enabled": False,
            "crm_accumulation_enabled": True,
            "crm_api_key": secrets.token_urlsafe(24),
            **CRM_SETTINGS_DEFAULTS,
        }
        updates = {k: v for k, v in missing.items() if k not in row}
        if updates:
            t.update(updates, doc_ids=[row["id"]])
            row.update(updates)
        return row


def update_settings(**fields) -> dict:
    cur = get_settings()
    with _lock:
        _table("settings").update(fields, doc_ids=[cur["id"]])
    return get_settings()


# --- sessions -----------------------------------------------------------------
def create_session(user_id: int, gh_access_token: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _table("sessions").insert({
            "token": token, "user_id": user_id,
            "gh_access_token": gh_access_token, "created_at": utcnow_iso(),
        })
    return token


def get_session(token: str) -> dict | None:
    if not token:
        return None
    return _first("sessions", Query().token == token)


def delete_session(token: str) -> None:
    with _lock:
        _table("sessions").remove(Query().token == token)


# --- derived point calculations ----------------------------------------------
def earned_points(uid: int) -> int:
    """All-time earned points.

    Always included:
      - Kudos received (peer-to-peer, manually given)
      - CRM contributions (auto-awarded on CRM events)

    Conditionally included (when github_accumulation_enabled = True in settings):
      - GitHub contributions (merged PRs + closed issues, weighted)
      When disabled (manual mode), GitHub activity is informational only;
      points for GitHub work come from peer kudos with artifact links.
    """
    s = get_settings()
    received = sum(k["points"] for k in kudos_received(uid))
    crm = sum(c["points"] for c in crm_contributions_for(uid)) if s.get("crm_accumulation_enabled", True) else 0
    github = sum(c["points"] for c in contributions_for(uid)) if s.get("github_accumulation_enabled", False) else 0
    return received + crm + github


def given_points_this_month(uid: int) -> int:
    now = datetime.now(timezone.utc)
    return sum(
        k["points"] for k in kudos_given(uid)
        if parse_iso(k["created_at"]).year == now.year
        and parse_iso(k["created_at"]).month == now.month
    )


def giving_balance(uid: int) -> int:
    return max(0, get_settings()["monthly_allowance"] - given_points_this_month(uid))


def redeemed_points(uid: int) -> int:
    """Points locked in approved + pending swag orders (not available to spend again)."""
    with _lock:
        orders = _table("swag_orders").search(Query().user_id == uid)
    return sum(
        o["points_cost"] for o in orders
        if o.get("status") in ("pending", "approved")
    )


def spendable_points(uid: int) -> int:
    """Points available for swag redemption."""
    return max(0, earned_points(uid) - redeemed_points(uid))


# --- swag catalog ------------------------------------------------------------
def create_swag_item(**fields) -> dict:
    with _lock:
        fields.setdefault("created_at", utcnow_iso())
        fields.setdefault("is_available", True)
        fields.setdefault("stock", None)   # None = unlimited
        fields.setdefault("image_url", "")
        fields.setdefault("description", "")
        iid = _table("swag_items").insert(fields)
        return get_swag_item(iid)


def get_swag_item(iid: int) -> dict | None:
    with _lock:
        return _with_id(_table("swag_items").get(doc_id=iid))


def all_swag_items(include_unavailable: bool = False) -> list[dict]:
    with _lock:
        items = [_with_id(d) for d in _table("swag_items").all()]
    if not include_unavailable:
        items = [i for i in items if i.get("is_available", True)]
    return sorted(items, key=lambda i: i["point_cost"])


def update_swag_item(iid: int, **fields) -> dict | None:
    with _lock:
        _table("swag_items").update(fields, doc_ids=[iid])
    return get_swag_item(iid)


# --- swag orders -------------------------------------------------------------
def create_swag_order(user_id: int, item_id: int, points_cost: int,
                      item_name: str, notes: str = "") -> dict:
    with _lock:
        oid = _table("swag_orders").insert({
            "user_id": user_id,
            "item_id": item_id,
            "item_name": item_name,
            "points_cost": points_cost,
            "notes": notes,
            "status": "pending",
            "created_at": utcnow_iso(),
            "reviewed_at": None,
            "reviewer_id": None,
            "rejection_reason": "",
        })
    return get_swag_order(oid)


def get_swag_order(oid: int) -> dict | None:
    with _lock:
        return _with_id(_table("swag_orders").get(doc_id=oid))


def orders_for(uid: int) -> list[dict]:
    with _lock:
        return [_with_id(d) for d in _table("swag_orders").search(Query().user_id == uid)]


def all_swag_orders() -> list[dict]:
    with _lock:
        return [_with_id(d) for d in _table("swag_orders").all()]


def pending_swag_orders() -> list[dict]:
    with _lock:
        return [_with_id(d) for d in
                _table("swag_orders").search(Query().status == "pending")]


def approve_swag_order(oid: int, reviewer_id: int) -> dict | None:
    with _lock:
        _table("swag_orders").update(
            {"status": "approved", "reviewed_at": utcnow_iso(),
             "reviewer_id": reviewer_id},
            doc_ids=[oid])
    return get_swag_order(oid)


def reject_swag_order(oid: int, reviewer_id: int, reason: str = "") -> dict | None:
    with _lock:
        _table("swag_orders").update(
            {"status": "rejected", "reviewed_at": utcnow_iso(),
             "reviewer_id": reviewer_id, "rejection_reason": reason},
            doc_ids=[oid])
    return get_swag_order(oid)


# --- workflow (singleton document) ------------------------------------------
def get_workflow() -> dict:
    from .workflow import DEFAULT_WORKFLOW
    with _lock:
        t = _table("workflow")
        rows = t.all()
        if not rows:
            t.insert(DEFAULT_WORKFLOW)
            rows = t.all()
        return dict(rows[0])


def save_workflow(wf: dict) -> dict:
    current = get_workflow()
    doc_id = current.get("id") or _table("workflow").all()[0].doc_id
    with _lock:
        _table("workflow").update(wf, doc_ids=[doc_id])
    return get_workflow()


# --- swag order transitions --------------------------------------------------
def transition_swag_order(oid: int, transition_id: str,
                           actor_id: int, reason: str = "") -> dict | None:
    """Apply a workflow transition to an order. Appends to the transition log."""
    from .workflow import find_transition, is_terminal, available_transitions
    wf = get_workflow()
    order = get_swag_order(oid)
    if not order:
        return None
    current_state = order.get("current_state", "pending")
    transition = find_transition(wf, transition_id)
    if not transition or transition["from"] != current_state:
        raise ValueError(f"Transition '{transition_id}' not valid from state '{current_state}'.")
    new_state = transition["to"]
    log_entry = {
        "transition_id": transition_id,
        "label": transition["label"],
        "from": current_state,
        "to": new_state,
        "actor_id": actor_id,
        "reason": reason,
        "at": utcnow_iso(),
    }
    with _lock:
        existing_log = order.get("transition_log", [])
        _table("swag_orders").update(
            {"current_state": new_state,
             "status": new_state,  # keep status in sync for simple checks
             "transition_log": existing_log + [log_entry],
             "reviewed_at": utcnow_iso(),
             "reviewer_id": actor_id},
            doc_ids=[oid],
        )
    return get_swag_order(oid)


# --- notifications -----------------------------------------------------------
def create_notification(user_id: int, message: str, kind: str = "info",
                        link: str = "") -> dict:
    with _lock:
        nid = _table("notifications").insert({
            "user_id": user_id,
            "message": message,
            "kind": kind,  # "info" | "success" | "warning"
            "link": link,
            "read": False,
            "created_at": utcnow_iso(),
        })
        return _with_id(_table("notifications").get(doc_id=nid))


def notifications_for(uid: int) -> list[dict]:
    with _lock:
        items = [_with_id(d) for d in
                 _table("notifications").search(Query().user_id == uid)]
    return sorted(items, key=lambda n: n["created_at"], reverse=True)[:50]


def unread_count(uid: int) -> int:
    with _lock:
        return len(_table("notifications").search(
            (Query().user_id == uid) & (Query().read == False)))  # noqa: E712


def mark_all_read(uid: int) -> None:
    with _lock:
        _table("notifications").update(
            {"read": True},
            (Query().user_id == uid) & (Query().read == False))  # noqa: E712


def reset_database() -> None:
    with _lock:
        get_db().drop_tables()
