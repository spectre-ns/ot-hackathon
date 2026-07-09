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

from . import auth, db, github_sync, slack, workflow as wf_engine
from .config import DEMO_LOGIN, github_oauth_enabled
from .crm_events import CRM_EVENT_TYPES, CRM_EVENTS_BY_KEY, event_points
from .schemas import (
    CartOrderBody, CRMEventBody, DemoLoginBody, DeleteTransitionBody, KudosBody,
    OrderTransitionBody, ReactBody, SettingsBody, SwagItemBody, SwagOrderBody,
    UserRoleBody, WorkflowStateBody, WorkflowTransitionBody,
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
        "role": u.get("role", "user"),
        "email": u.get("email", ""),
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
    if settings.get("crm_accumulation_enabled", True):
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
    settings = db.get_settings()
    public_settings = {k: v for k, v in settings.items() if k != "crm_api_key"}
    return {
        "github_oauth_enabled": github_oauth_enabled(),
        "core_values": CORE_VALUES,
        "crm_event_types": CRM_EVENT_TYPES,
        "settings": public_settings,
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
    if not DEMO_LOGIN:
        raise HTTPException(403, "Demo login is disabled on this server.")
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


@app.put("/api/users/{user_id}/role")
def update_user_role(user_id: int, body: UserRoleBody,
                     superadmin=Depends(auth.require_superadmin)):
    try:
        updated = db.set_user_role(user_id, body.role)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not updated:
        raise HTTPException(404, "User not found")
    return public_user(updated)


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
    receiver = db.get_user(body.receiver_id)
    k = db.create_kudos(
        user["id"], body.receiver_id, body.points,
        body.value_key, body.message.strip(),
        artifact_url=body.artifact_url or "",
        artifact_label=body.artifact_label or "",
    )
    # Announce to Slack if configured. Never fails the request (see slack.py).
    slack.notify_kudos(user, receiver, body.points, body.value_key,
                       body.message.strip())
    return enrich_kudos(k, user["id"])


@app.post("/api/kudos/{kudos_id}/react")
def react(kudos_id: int, body: ReactBody, user: dict = Depends(auth.current_user)):
    if not db.get_kudos(kudos_id):
        raise HTTPException(404, "Kudos not found.")
    action = db.toggle_reaction(kudos_id, user["id"], body.emoji)
    return {"action": action, "kudos": enrich_kudos(db.get_kudos(kudos_id), user["id"])}


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------
@app.get("/api/activity")
def activity_feed(_user=Depends(auth.current_user), limit: int = 100):
    """Combined GitHub + CRM contributions across all users, newest first."""
    users_map = {u["id"]: u for u in db.all_users()}
    items = []
    for c in db.all_contributions():
        u = users_map.get(c["user_id"])
        items.append({**c, "source": "github", "user": public_user(u) if u else None})
    for c in db.all_crm_contributions():
        u = users_map.get(c["user_id"])
        et = CRM_EVENTS_BY_KEY.get(c["event_type"], {})
        items.append({**c, "source": "crm", "user": public_user(u) if u else None,
                      "event_label": et.get("label", c["event_type"]),
                      "event_emoji": et.get("emoji", "📋")})
    items.sort(key=lambda x: x.get("happened_at", ""), reverse=True)
    return items[:limit]


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


@app.get("/api/admin/statistics")
def admin_statistics(admin=Depends(auth.require_admin)):
    """Org-wide statistics dashboard. Admin/SuperAdmin only — no public ranking."""
    all_k = db.all_kudos()
    crm_c = db.all_crm_contributions()
    gh_c = db.all_contributions()
    users = db.all_users()

    kudos_points = sum(k["points"] for k in all_k)
    crm_points = sum(c["points"] for c in crm_c)
    gh_points = sum(c["points"] for c in gh_c)

    value_tally: dict[str, int] = defaultdict(int)
    for k in all_k:
        value_tally[k["value_key"]] += 1
    value_breakdown = [
        {"value": value_or_default(key), "count": count}
        for key, count in sorted(value_tally.items(), key=lambda x: -x[1])
    ]

    earners = []
    for u in users:
        pts = earned_in_period(u["id"], "all")
        if pts > 0:
            earners.append({"user": public_user(u), "points": pts})
    earners.sort(key=lambda r: -r["points"])
    for i, r in enumerate(earners):
        r["rank"] = i + 1

    role_counts: dict[str, int] = defaultdict(int)
    for u in users:
        role_counts[u.get("role", "user")] += 1

    order_counts: dict[str, int] = defaultdict(int)
    for o in db.all_swag_orders():
        order_counts[o.get("status", "pending")] += 1

    return {
        "kudos_count": len(all_k),
        "kudos_points": kudos_points,
        "crm_events": len(crm_c),
        "crm_points": crm_points,
        "github_activities": len(gh_c),
        "github_points": gh_points,
        "points_awarded": kudos_points + crm_points,
        "people_recognized": len({k["receiver_id"] for k in all_k}),
        "total_users": len(users),
        "role_counts": dict(role_counts),
        "value_breakdown": value_breakdown,
        "top_earners": earners[:10],
        "swag_orders_by_status": dict(order_counts),
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
    expected = settings.get("crm_api_key", "")
    if not key or not secrets.compare_digest(key, expected):
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
def read_settings(admin=Depends(auth.require_admin)):
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


def _place_order(user: dict, specs: list[tuple[int, int]], notes: str) -> dict:
    """Validate points + stock for a cart of (item_id, qty) and place one order.

    Raises HTTPException on any failure; on success reserves stock, creates a
    single grouped order and notifies admins.
    """
    line_items: list[dict] = []
    for item_id, qty in specs:
        item = db.get_swag_item(item_id)
        if not item or not item.get("is_available"):
            raise HTTPException(404, "Item not available")
        line_items.append({
            "item_id": item_id,
            "item_name": item["name"],
            "qty": qty,
            "unit_cost": item["point_cost"],
        })
    total = sum(li["qty"] * li["unit_cost"] for li in line_items)
    spendable = db.spendable_points(user["id"])
    if total > spendable:
        raise HTTPException(400,
            f"Not enough points. You have {spendable} available "
            f"but this order costs {total}.")
    # Atomically verify + reserve stock for every finite-stock line.
    err = db.adjust_stock([(li["item_id"], -li["qty"]) for li in line_items],
                          verify=True)
    if err:
        raise HTTPException(409, err)
    wf = db.get_workflow()
    init = wf_engine.initial_state(wf)
    order = db.create_swag_order(
        user_id=user["id"], line_items=line_items,
        notes=notes, current_state=init,
    )
    # Notify all admins of the new order.
    for admin_user in db.all_users():
        if admin_user.get("is_admin"):
            db.create_notification(
                admin_user["id"],
                f"🛍️ {user['name']} placed a swag order: {order['item_name']} ({total} pts)",
                kind="warning",
                link="/admin/orders",
            )
    return order


@app.post("/api/swag/{item_id}/order")
def place_order(item_id: int, body: SwagOrderBody, user: dict = Depends(auth.current_user)):
    return _place_order(user, [(item_id, 1)], body.notes)


@app.post("/api/swag/order")
def place_cart_order(body: CartOrderBody, user: dict = Depends(auth.current_user)):
    # Consolidate duplicate lines for the same item into a single qty.
    qty_by_item: dict[int, int] = {}
    for line in body.items:
        qty_by_item[line.item_id] = qty_by_item.get(line.item_id, 0) + line.qty
    return _place_order(user, list(qty_by_item.items()), body.notes)


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
    # Attach current catalog details (image/availability) to each line item.
    lines = order.get("line_items") or [{
        "item_id": order.get("item_id"),
        "item_name": order.get("item_name"),
        "qty": 1,
        "unit_cost": order.get("points_cost", 0),
    }]
    enriched_lines = [{**li, "item": db.get_swag_item(li["item_id"])} for li in lines]
    return {
        **order,
        "user": public_user(user) if user else None,
        "item": item,
        "line_items": enriched_lines,
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
    if not actor.get("is_admin") and order["user_id"] != actor["id"]:
        raise HTTPException(403, "You can only modify your own orders.")
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
    if wf_engine.is_terminal(wf, state["id"]):
        kind = "warning" if "reject" in state["id"].lower() else "success"
    else:
        kind = "info"
    db.create_notification(order["user_id"], msg, kind=kind)
    # A rejected order returns any reserved stock to the catalog.
    if wf_engine.is_terminal(wf, state["id"]) and "reject" in state["id"].lower():
        db.adjust_stock([(li["item_id"], li["qty"])
                         for li in order.get("line_items", [])])
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


@app.get("/{path:path}")
def spa_fallback(path: str):
    return FileResponse(STATIC_DIR / "index.html")
