"""FastAPI application: routes for the Kudos recognition platform."""
from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import auth, db, github_sync, workflow as wf_engine
from .config import github_oauth_enabled
from .crm_events import CRM_EVENT_TYPES, CRM_EVENTS_BY_KEY, event_points
from .schemas import (
    CRMEventBody, DemoLoginBody, DeleteTransitionBody, KudosBody,
    OrderTransitionBody, ReactBody, SettingsBody, SwagItemBody, SwagOrderBody,
    WorkflowStateBody, WorkflowTransitionBody,
)
from .values import CORE_VALUES, value_or_default

app = FastAPI(title="Kudos", docs_url="/api/docs")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

_oauth_states: set[str] = set()


# --------------------------------------------------------------------------
# Serialization helpers
# --------------------------------------------------------------------------
def public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "name": u["name"],
        "title": u.get("title", ""),
        "department": u.get("department", ""),
        "avatar_url": u.get("avatar_url", ""),
        "avatar_color": u.get("avatar_color", "#4D75FE"),
        "github_login": u.get("github_login"),
        "is_admin": u.get("is_admin", False),
        "earned_points": db.earned_points(u["id"]),
    }


def enrich_kudos(k: dict, viewer_id: int | None) -> dict:
    giver = db.get_user(k["giver_id"])
    receiver = db.get_user(k["receiver_id"])
    grouped: dict[str, dict] = {}
    for r in db.reactions_for(k["id"]):
        g = grouped.setdefault(r["emoji"], {"emoji": r["emoji"], "count": 0, "mine": False})
        g["count"] += 1
        if viewer_id and r["user_id"] == viewer_id:
            g["mine"] = True
    return {
        "id": k["id"],
        "points": k["points"],
        "message": k["message"],
        "created_at": k["created_at"],
        "value": value_or_default(k["value_key"]),
        "giver": public_user(giver) if giver else None,
        "receiver": public_user(receiver) if receiver else None,
        "reactions": sorted(grouped.values(), key=lambda x: -x["count"]),
        "artifact_url": k.get("artifact_url", ""),
        "artifact_label": k.get("artifact_label", ""),
    }


def _in_current_month(iso: str) -> bool:
    if not iso:
        return False
    try:
        dt = db.parse_iso(iso)
    except ValueError:
        return False
    now = datetime.now(timezone.utc)
    return dt.year == now.year and dt.month == now.month


def earned_in_period(uid: int, period: str) -> int:
    if period == "all":
        return db.earned_points(uid)
    settings = db.get_settings()
    total = 0
    for k in db.kudos_received(uid):
        if _in_current_month(k["created_at"]):
            total += k["points"]
    for c in db.crm_contributions_for(uid):
        if _in_current_month(c.get("happened_at", "")):
            total += c["points"]
    if settings.get("github_accumulation_enabled", False):
        for c in db.contributions_for(uid):
            if _in_current_month(c.get("happened_at", "")):
                total += c["points"]
    return total


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        auth.SESSION_COOKIE, token,
        httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30, path="/",
    )


# --------------------------------------------------------------------------
# Meta / config
# --------------------------------------------------------------------------
@app.get("/api/config")
def get_config():
    return {
        "github_oauth_enabled": github_oauth_enabled(),
        "core_values": CORE_VALUES,
        "crm_event_types": CRM_EVENT_TYPES,
        "settings": db.get_settings(),
    }


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
@app.get("/auth/github/login")
def github_login():
    if not github_oauth_enabled():
        raise HTTPException(400, "GitHub OAuth is not configured on this server.")
    state = secrets.token_urlsafe(16)
    _oauth_states.add(state)
    return RedirectResponse(auth.authorize_url(state))


@app.get("/auth/github/callback")
async def github_callback(code: str = "", state: str = ""):
    if state not in _oauth_states:
        raise HTTPException(400, "Invalid OAuth state.")
    _oauth_states.discard(state)
    token = await auth.exchange_code_for_token(code)
    profile = await auth.fetch_github_profile(token)
    user = auth.upsert_github_user(profile)
    session_token = db.create_session(user["id"], gh_access_token=token)
    response = RedirectResponse("/")
    set_session_cookie(response, session_token)
    return response


@app.post("/api/auth/demo")
def demo_login(body: DemoLoginBody, response: Response):
    user = db.get_user(body.user_id)
    if not user:
        raise HTTPException(404, "User not found")
    token = db.create_session(user["id"])
    set_session_cookie(response, token)
    return {"ok": True, "user": public_user(user)}


@app.post("/api/auth/logout")
def logout(response: Response, session=Depends(auth.current_session)):
    if session:
        db.delete_session(session["token"])
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(auth.current_user)):
    data = public_user(user)
    data["giving_balance"] = db.giving_balance(user["id"])
    data["given_this_month"] = db.given_points_this_month(user["id"])
    data["monthly_allowance"] = db.get_settings()["monthly_allowance"]
    data["spendable_points"] = db.spendable_points(user["id"])
    data["unread_notifications"] = db.unread_count(user["id"])
    return data


# --------------------------------------------------------------------------
# Users / profiles
# --------------------------------------------------------------------------
@app.get("/api/users")
def list_users():
    users = [public_user(u) for u in db.all_users()]
    users.sort(key=lambda u: u["name"].lower())
    return users


@app.get("/api/users/{user_id}")
def get_profile(user_id: int, viewer=Depends(auth.current_session)):
    u = db.get_user(user_id)
    if not u:
        raise HTTPException(404, "User not found")
    viewer_id = viewer["user_id"] if viewer else None
    received = sorted(db.kudos_received(user_id),
                      key=lambda k: k["created_at"], reverse=True)
    gh_contribs = sorted(db.contributions_for(user_id),
                         key=lambda c: c.get("happened_at", ""), reverse=True)
    crm_contribs = sorted(db.crm_contributions_for(user_id),
                          key=lambda c: c.get("happened_at", ""), reverse=True)
    value_tally: dict[str, int] = defaultdict(int)
    for k in received:
        value_tally[k["value_key"]] += 1
    return {
        "user": public_user(u),
        "earned_points": db.earned_points(user_id),
        "earned_this_month": earned_in_period(user_id, "month"),
        "kudos_count": len(received),
        "given_count": len(db.kudos_given(user_id)),
        "received": [enrich_kudos(k, viewer_id) for k in received[:50]],
        "github_contributions": gh_contribs[:50],
        "crm_contributions": crm_contribs[:50],
        "value_breakdown": [
            {"value": value_or_default(key), "count": count}
            for key, count in sorted(value_tally.items(), key=lambda x: -x[1])
        ],
    }


# --------------------------------------------------------------------------
# Feed / kudos
# --------------------------------------------------------------------------
@app.get("/api/feed")
def feed(viewer=Depends(auth.current_session), limit: int = 50):
    viewer_id = viewer["user_id"] if viewer else None
    items = sorted(db.all_kudos(), key=lambda k: k["created_at"], reverse=True)
    return [enrich_kudos(k, viewer_id) for k in items[:limit]]


@app.post("/api/kudos")
def give_kudos(body: KudosBody, user: dict = Depends(auth.current_user)):
    if body.receiver_id == user["id"]:
        raise HTTPException(400, "You can't give kudos to yourself.")
    if not db.get_user(body.receiver_id):
        raise HTTPException(404, "Recipient not found.")
    if body.value_key not in {v["key"] for v in CORE_VALUES}:
        raise HTTPException(400, "Unknown core value.")
    balance = db.giving_balance(user["id"])
    if body.points > balance:
        raise HTTPException(
            400, f"Not enough points. You have {balance} left to give this month.")
    k = db.create_kudos(
        user["id"], body.receiver_id, body.points,
        body.value_key, body.message.strip(),
        artifact_url=body.artifact_url or "",
        artifact_label=body.artifact_label or "",
    )
    return enrich_kudos(k, user["id"])


@app.post("/api/kudos/{kudos_id}/react")
def react(kudos_id: int, body: ReactBody, user: dict = Depends(auth.current_user)):
    if not db.get_kudos(kudos_id):
        raise HTTPException(404, "Kudos not found.")
    action = db.toggle_reaction(kudos_id, user["id"], body.emoji)
    return {"action": action, "kudos": enrich_kudos(db.get_kudos(kudos_id), user["id"])}


# --------------------------------------------------------------------------
# Leaderboard / stats
# --------------------------------------------------------------------------
@app.get("/api/leaderboard")
def leaderboard(period: str = "month"):
    if period not in ("month", "all"):
        period = "month"
    rows = []
    for u in db.all_users():
        pts = earned_in_period(u["id"], period)
        if pts <= 0:
            continue
        rows.append({"user": public_user(u), "points": pts})
    rows.sort(key=lambda r: -r["points"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


@app.get("/api/stats")
def stats():
    all_k = db.all_kudos()
    crm_c = db.all_crm_contributions()
    given_points = sum(k["points"] for k in all_k)
    crm_points = sum(c["points"] for c in crm_c)
    value_tally: dict[str, int] = defaultdict(int)
    for k in all_k:
        value_tally[k["value_key"]] += 1
    top_value = max(value_tally.items(), key=lambda x: x[1])[0] if value_tally else None
    return {
        "kudos_count": len(all_k),
        "people_recognized": len({k["receiver_id"] for k in all_k}),
        "points_awarded": given_points + crm_points,
        "crm_events": len(crm_c),
        "github_activities": len(db.all_contributions()),
        "top_value": value_or_default(top_value) if top_value else None,
    }


# --------------------------------------------------------------------------
# GitHub sync
# --------------------------------------------------------------------------
@app.post("/api/github/sync")
async def github_sync_me(user: dict = Depends(auth.current_user),
                         session=Depends(auth.current_session)):
    if not user.get("github_login"):
        raise HTTPException(400, "Link a GitHub account first (log in with GitHub).")
    token = session.get("gh_access_token") if session else None
    try:
        summary = await run_in_threadpool(github_sync.sync_user, user, token)
    except Exception as e:
        raise HTTPException(502, f"GitHub sync failed: {e}")
    return {"ok": True, "summary": summary}


# --------------------------------------------------------------------------
# CRM webhook  (called by real CRM or the simulator)
# --------------------------------------------------------------------------
def _resolve_user(identifier: str) -> dict:
    """Find a user by github_login or email."""
    by_login = db.get_user_by_github_login(identifier)
    if by_login:
        return by_login
    by_email = db.get_user_by_email(identifier)
    if by_email:
        return by_email
    raise HTTPException(404, f"No user found for identifier '{identifier}'.")


def _apply_crm_event(body: CRMEventBody) -> dict:
    """Core logic shared by the webhook and the admin simulator."""
    if body.event_type not in CRM_EVENTS_BY_KEY:
        raise HTTPException(400, f"Unknown event_type '{body.event_type}'.")
    user = _resolve_user(body.user_identifier)
    settings = db.get_settings()
    points = event_points(body.event_type, settings)
    if not points:
        raise HTTPException(400, "This CRM event type has 0 points configured.")
    et = CRM_EVENTS_BY_KEY[body.event_type]
    title = body.title or et["placeholder_title"].replace("{company}", body.company or "customer")
    happened_at = body.happened_at or db.utcnow_iso()
    contrib, created = db.upsert_crm_contribution(
        user_id=user["id"],
        event_type=body.event_type,
        reference_id=body.reference_id,
        title=title,
        company=body.company,
        deal_value=body.deal_value,
        points=points,
        happened_at=happened_at,
        artifact_url=body.artifact_url,
    )
    return {
        "ok": True,
        "created": created,
        "user": public_user(user),
        "event_type": et,
        "contribution": contrib,
        "points_awarded": points if created else 0,
    }


@app.post("/api/crm/event")
async def crm_webhook(body: CRMEventBody, request: Request):
    """Webhook endpoint for CRM systems (Salesforce, HubSpot, Pipedrive, etc.).

    Authenticate by sending the API key in the X-CRM-Key header.
    Salesforce wiring: create a Flow / Apex HTTP Callout Action that POSTs this
    JSON to this URL with the header. No changes to this service are needed.
    """
    key = request.headers.get("X-CRM-Key", "")
    settings = db.get_settings()
    if not key or key != settings.get("crm_api_key", ""):
        raise HTTPException(401, "Invalid or missing X-CRM-Key header.")
    return _apply_crm_event(body)


@app.post("/api/crm/simulate")
def crm_simulate(body: CRMEventBody, admin=Depends(auth.require_admin)):
    """Admin-only endpoint that fires a simulated CRM event without an API key.
    Used for demos and testing the CRM integration locally.
    """
    return _apply_crm_event(body)


@app.get("/api/crm/events")
def crm_events(admin=Depends(auth.require_admin)):
    """Return all CRM contributions, newest first, for the admin dashboard."""
    events = sorted(db.all_crm_contributions(),
                    key=lambda c: c.get("happened_at", ""), reverse=True)
    enriched = []
    for c in events:
        user = db.get_user(c["user_id"])
        et = CRM_EVENTS_BY_KEY.get(c["event_type"], {})
        enriched.append({**c, "user": public_user(user) if user else None,
                         "event_label": et.get("label", c["event_type"]),
                         "event_emoji": et.get("emoji", "📋")})
    return enriched


# --------------------------------------------------------------------------
# Admin settings
# --------------------------------------------------------------------------
@app.get("/api/settings")
def read_settings():
    return db.get_settings()


@app.put("/api/settings")
def write_settings(body: SettingsBody, admin=Depends(auth.require_admin)):
    return db.update_settings(**body.model_dump())


# --------------------------------------------------------------------------
# Swag catalog
# --------------------------------------------------------------------------
@app.get("/api/swag")
def list_swag(user: dict = Depends(auth.current_user)):
    items = db.all_swag_items(include_unavailable=user.get("is_admin", False))
    spendable = db.spendable_points(user["id"])
    return {"items": items, "spendable_points": spendable}


@app.post("/api/swag")
def create_swag(body: SwagItemBody, admin=Depends(auth.require_admin)):
    return db.create_swag_item(**body.model_dump())


@app.put("/api/swag/{item_id}")
def update_swag(item_id: int, body: SwagItemBody, admin=Depends(auth.require_admin)):
    item = db.update_swag_item(item_id, **body.model_dump())
    if not item:
        raise HTTPException(404, "Item not found")
    return item


@app.post("/api/swag/{item_id}/order")
def place_order(item_id: int, body: SwagOrderBody, user: dict = Depends(auth.current_user)):
    item = db.get_swag_item(item_id)
    if not item or not item.get("is_available"):
        raise HTTPException(404, "Item not available")
    spendable = db.spendable_points(user["id"])
    if item["point_cost"] > spendable:
        raise HTTPException(400,
            f"Not enough points. You have {spendable} available "
            f"but this item costs {item['point_cost']}.")
    wf = db.get_workflow()
    order = db.create_swag_order(
        user_id=user["id"], item_id=item_id,
        points_cost=item["point_cost"], item_name=item["name"],
        notes=body.notes,
    )
    # Set initial workflow state and seed the transition log.
    init = wf_engine.initial_state(wf)
    db.transition_swag_order.__wrapped__ if False else None  # sentinel
    with db._lock:
        from tinydb import Query as Q
        db._table("swag_orders").update(
            {"current_state": init, "status": init, "transition_log": []},
            doc_ids=[order["id"]],
        )
    order = db.get_swag_order(order["id"])
    # Notify all admins of the new order.
    for admin_user in db.all_users():
        if admin_user.get("is_admin"):
            db.create_notification(
                admin_user["id"],
                f"🛍️ {user['name']} placed a swag order: {item['name']} ({item['point_cost']} pts)",
                kind="warning",
                link="/admin/orders",
            )
    return order


@app.get("/api/swag/orders")
def my_orders(user: dict = Depends(auth.current_user)):
    orders = sorted(db.orders_for(user["id"]),
                    key=lambda o: o["created_at"], reverse=True)
    wf = db.get_workflow()
    return [_enrich_order(o, wf) for o in orders]


@app.get("/api/swag/orders/pending")
def pending_orders(admin=Depends(auth.require_admin)):
    wf = db.get_workflow()
    orders = sorted(db.all_swag_orders(), key=lambda o: o["created_at"], reverse=True)
    # Return orders whose current state is non-terminal.
    active = [o for o in orders
              if not wf_engine.is_terminal(wf, o.get("current_state", "pending"))]
    return [_enrich_order(o, wf) for o in active]


@app.get("/api/swag/orders/all")
def all_orders(admin=Depends(auth.require_admin)):
    wf = db.get_workflow()
    orders = sorted(db.all_swag_orders(), key=lambda o: o["created_at"], reverse=True)
    return [_enrich_order(o, wf) for o in orders]


def _enrich_order(order: dict, wf: dict) -> dict:
    user = db.get_user(order["user_id"])
    item = db.get_swag_item(order["item_id"])
    state = wf_engine.state_info(wf, order.get("current_state", "pending"))
    transitions = wf_engine.available_transitions(wf, order.get("current_state", "pending"))
    return {
        **order,
        "user": public_user(user) if user else None,
        "item": item,
        "state_info": state,
        "available_transitions": transitions,
    }


@app.post("/api/swag/orders/{order_id}/transition")
def transition_order(order_id: int, body: OrderTransitionBody,
                     actor: dict = Depends(auth.current_user)):
    wf = db.get_workflow()
    order = db.get_swag_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    # Non-admins can only cancel their own order from the initial state.
    t = wf_engine.find_transition(wf, body.transition_id)
    if not t:
        raise HTTPException(400, "Transition not found")
    if t.get("requires_admin") and not actor.get("is_admin"):
        raise HTTPException(403, "This transition requires admin privileges")
    if t.get("requires_reason") and not body.reason.strip():
        raise HTTPException(400, "A reason is required for this transition")
    try:
        updated = db.transition_swag_order(
            order_id, body.transition_id, actor["id"], body.reason.strip())
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not updated:
        raise HTTPException(404, "Order not found")
    # Notify the order owner of the state change.
    owner = db.get_user(order["user_id"])
    state = wf_engine.state_info(wf, updated["current_state"])
    msg = f"Your order for **{order['item_name']}** moved to: {state['name']}"
    if body.reason:
        msg += f" — {body.reason}"
    db.create_notification(order["user_id"], msg,
                           kind="success" if wf_engine.is_terminal(wf, state["id"]) else "info")
    return _enrich_order(updated, wf)


# --------------------------------------------------------------------------
# Workflow editor
# --------------------------------------------------------------------------
@app.get("/api/workflow")
def get_workflow(_user: dict = Depends(auth.current_user)):
    return db.get_workflow()


@app.post("/api/workflow/states")
def add_state(body: WorkflowStateBody, admin=Depends(auth.require_admin)):
    wf = db.get_workflow()
    try:
        wf = wf_engine.add_state(wf, body.name, body.color, body.is_terminal)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return db.save_workflow(wf)


@app.delete("/api/workflow/states/{state_id}")
def delete_state(state_id: str, admin=Depends(auth.require_admin)):
    wf = db.get_workflow()
    try:
        wf = wf_engine.delete_state(wf, state_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return db.save_workflow(wf)


@app.post("/api/workflow/transitions")
def add_transition(body: WorkflowTransitionBody, admin=Depends(auth.require_admin)):
    wf = db.get_workflow()
    state_ids = {s["id"] for s in wf["states"]}
    if body.from_state not in state_ids or body.to_state not in state_ids:
        raise HTTPException(400, "Unknown state id")
    wf = wf_engine.add_transition(wf, body.from_state, body.to_state,
                                   body.label, body.requires_admin, body.requires_reason)
    return db.save_workflow(wf)


@app.delete("/api/workflow/transitions")
def delete_transition(body: DeleteTransitionBody, admin=Depends(auth.require_admin)):
    wf = db.get_workflow()
    wf = wf_engine.delete_transition(wf, body.transition_id)
    return db.save_workflow(wf)


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
@app.get("/api/notifications")
def get_notifications(user: dict = Depends(auth.current_user)):
    return db.notifications_for(user["id"])


@app.post("/api/notifications/read")
def mark_read(user: dict = Depends(auth.current_user)):
    db.mark_all_read(user["id"])
    return {"ok": True}


# --------------------------------------------------------------------------
# Static frontend
# --------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
