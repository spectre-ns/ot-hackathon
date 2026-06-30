"""Seed the database with a realistic set of employees and recognition history.

Run with:  python -m app.seed   (wipes and reseeds)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import db

NOW = datetime.now(timezone.utc)


def days_ago(n: int) -> str:
    return (NOW - timedelta(days=n, hours=n % 7)).isoformat()


EMPLOYEES = [
    # name, email, title, department, color, github_login, is_admin
    ("Ada Lovelace",     "ada@openteams.com",      "Principal Engineer",    "Platform",        "#000F3A", "ada-lovelace", True),
    ("Grace Hopper",     "grace@openteams.com",    "Engineering Manager",   "Platform",        "#4D75FE", "gracehopper",  True),
    ("Alan Turing",      "alan@openteams.com",     "Staff Engineer",        "Infrastructure",  "#2E9E6B", "alanturing",   False),
    ("Katherine Johnson","katherine@openteams.com","Senior Engineer",       "Data",            "#FAA944", "katherinej",   False),
    ("Linus Torvalds",   "linus@openteams.com",    "Senior Engineer",       "Infrastructure",  "#FF8A69", "torvalds",     False),
    ("Margaret Hamilton","margaret@openteams.com", "Engineer",              "Platform",        "#7C5CFF", "mhamilton",    False),
    ("Dennis Ritchie",   "dennis@openteams.com",   "Engineer",              "Languages",       "#1F8A8A", "dmr",          False),
    ("Barbara Liskov",   "barbara@openteams.com",  "Principal Engineer",    "Languages",       "#3a61e8", "bliskov",      False),
    ("Guido van Rossum", "guido@openteams.com",    "Distinguished Engineer","Languages",       "#d6502f", "gvanrossum",   False),
    ("Radia Perlman",    "radia@openteams.com",    "Network Architect",     "Infrastructure",  "#1c7a47", "rperlman",     False),
]

# (giver_idx, receiver_idx, points, value_key, message, days_ago, artifact_url, artifact_label)
KUDOS = [
    (1, 2, 25, "crisis_crusher",
     "Jumped on the prod outage at 11pm and had us back online in 40 minutes. Absolute lifesaver. 🙏",
     1, "", ""),
    (3, 0, 15, "great_teammate",
     "Always the first to answer a question in #engineering and never makes anyone feel dumb for asking.",
     2, "", ""),
    (0, 5, 20, "above_beyond",
     "Rewrote the onboarding docs without being asked — every new hire this quarter has thanked us for it.",
     3, "", ""),
    (4, 7, 30, "client_hero",
     "Handled the Northwind escalation with so much grace. The client literally asked to keep working with us BECAUSE of you.",
     4, "", ""),
    (2, 8, 10, "mentor",
     "Spent an hour pairing with me on async patterns. I finally get it. Thank you!",
     5, "", ""),
    (6, 1, 15, "great_teammate",
     "Covered my on-call shift so I could be at my daughter's recital. I won't forget it.",
     6, "", ""),
    (5, 3, 20, "innovator",
     "The caching idea you sketched on the whiteboard cut our P95 latency in half. 🚀",
     7, "https://github.com/openteams/data-pipeline/pull/588", "PR #588: Vectorized feature extraction"),
    (8, 4, 10, "great_teammate",
     "Patient code reviews that actually teach. Better engineer because of them.",
     8, "", ""),
    (7, 9, 25, "crisis_crusher",
     "Diagnosed the network partition no one else could see. Hero work under pressure.",
     9, "https://github.com/openteams/infra/issues/2298", "Issue #2298: Network partition az-1/az-2"),
    (9, 6, 15, "above_beyond",
     "Stayed late to unblock the release even though it wasn't your component. Team player of the year.",
     10, "", ""),
    (0, 3, 10, "innovator",
     "Loved your lightning talk on vector indexes — already using it in my project.",
     12, "https://github.com/openteams/data-pipeline/pull/571", "PR #571: Backfill job idempotency"),
    (1, 8, 20, "mentor",
     "Your 'guide to readable Python' thread is now required reading for the team.",
     14, "https://github.com/openteams/lang-tools/pull/130", "PR #130: Python style guide docs"),
    (3, 5, 15, "great_teammate",
     "Thanks for the thoughtful retro facilitation. Hard conversations made easy.",
     16, "", ""),
    (4, 0, 25, "crisis_crusher",
     "When the migration went sideways you stayed calm and walked us all back from the ledge.",
     20, "", ""),
    (2, 7, 10, "client_hero",
     "Turned a furious customer into a reference call. Masterclass in client comms.",
     22, "", ""),
]

# GitHub contributions — stored with configured weights but accumulation is
# off by default. Each has an artifact URL for traceability.
# (user_idx, kind, repo, number, title, days_ago)
GH_CONTRIBUTIONS = [
    (0, "pr",    "openteams/platform",      1421, "Add connection pooling to the query layer",       2),
    (0, "pr",    "openteams/platform",      1402, "Fix race condition in session cache",              6),
    (0, "issue", "openteams/platform",      1390, "Investigate elevated 5xx rate on /search",         8),
    (3, "pr",    "openteams/data-pipeline",  588, "Vectorized feature extraction (3x faster)",        3),
    (3, "pr",    "openteams/data-pipeline",  571, "Backfill job idempotency",                        11),
    (4, "pr",    "openteams/infra",          2304, "Harden network policy for prod namespace",        4),
    (4, "issue", "openteams/infra",          2298, "Network partition between az-1 and az-2",         9),
    (7, "pr",    "openteams/lang-tools",      142, "Type inference for generic protocols",            5),
    (8, "pr",    "openteams/lang-tools",      139, "Improve error messages for missing __init__",     7),
    (8, "pr",    "openteams/lang-tools",      130, "Docs: readable Python style guide",              13),
    (2, "pr",    "openteams/infra",          2289, "Autoscaler tuning for burst traffic",            10),
    (9, "issue", "openteams/infra",          2275, "Document failover runbook",                      15),
]

# CRM contributions
# (user_idx, event_type, reference_id, title, company, deal_value, days_ago, artifact_url)
CRM_CONTRIBUTIONS = [
    (8, "deal_closed",        "OPP-8821",  "Closed Acme Corp Enterprise deal",          "Acme Corp",       85000,  2,  "https://crm.example.com/opportunities/OPP-8821"),
    (8, "contract_renewed",   "REN-2204",  "Renewed TechCorp annual subscription",      "TechCorp",        42000,  5,  "https://crm.example.com/renewals/REN-2204"),
    (1, "escalation_resolved","ESC-1103",  "Resolved BigClient API integration outage", "BigClient Inc",   None,   3,  "https://crm.example.com/cases/ESC-1103"),
    (1, "nps_positive",       "NPS-5591",  "NPS 10 from CloudSystems",                  "CloudSystems",    None,   7,  ""),
    (3, "ticket_resolved",    "CASE-4421", "Resolved data export timeout for FinCo",    "FinCo",           None,   1,  "https://crm.example.com/cases/CASE-4421"),
    (3, "ticket_resolved",    "CASE-4398", "Resolved API rate limit issue for MedTech", "MedTech",         None,   6,  ""),
    (3, "ticket_resolved",    "CASE-4350", "Resolved SSO configuration for GovAgency",  "GovAgency",       None,  12,  ""),
    (3, "customer_call",      "CALL-9901", "Quarterly business review with DataCo",     "DataCo",          None,   4,  ""),
    (3, "customer_call",      "CALL-9877", "Onboarding call with NewClient",             "NewClient",       None,   9,  ""),
    (9, "nps_positive",       "NPS-5580",  "NPS 9 from NetWorks Corp",                  "NetWorks Corp",   None,  10,  ""),
    (9, "customer_call",      "CALL-9860", "Demo call with ProspectCo",                  "ProspectCo",      None,  14,  ""),
    (5, "deal_closed",        "OPP-8790",  "Closed StartupXYZ seed deal",               "StartupXYZ",     12000,  8,  ""),
]


SWAG_ITEMS = [
    # (name, description, point_cost, image_url, stock)
    ("OpenTeams T-Shirt",
     "100% cotton crew-neck tee with the OpenTeams logo. Available in S-XXL.",
     50, "", None),
    ("OpenTeams Hoodie",
     "Heavyweight zip-up hoodie in navy. Perfect for remote-work chilly mornings.",
     150, "", None),
    ("$25 Amazon Gift Card",
     "Treat yourself — a $25 Amazon gift card delivered by email.",
     100, "", None),
    ("$50 Amazon Gift Card",
     "A $50 Amazon gift card delivered by email.",
     200, "", None),
    ("Standing Desk Mat",
     "Anti-fatigue mat for standing desks. 30"×20", ergonomic support.",
     250, "", None),
    ("Charity Donation",
     "We'll donate $25 to the charity of your choice in your name.",
     75, "", None),
    ("Extra PTO Day",
     "One additional paid time-off day, pre-approved. Schedule through your manager.",
     300, "", 10),
    ("Wireless Noise-Cancelling Headphones",
     "Sony WH-1000XM5 — 30hr battery, best-in-class ANC. While supplies last.",
     500, "", 5),
]


def run():
    db.reset_database()
    settings = db.get_settings()  # creates defaults
    pr_pts = settings["pr_points"]
    issue_pts = settings["issue_points"]

    users = []
    for name, email, title, dept, color, gh, is_admin in EMPLOYEES:
        users.append(db.create_user(
            name=name, email=email, title=title, department=dept,
            avatar_color=color, github_login=gh, is_admin=is_admin,
        ))

    for gi, ri, pts, val, msg, ago, art_url, art_label in KUDOS:
        db.create_kudos(
            users[gi]["id"], users[ri]["id"], pts, val, msg,
            created_at=days_ago(ago),
            artifact_url=art_url,
            artifact_label=art_label,
        )

    for ui, kind, repo, num, title, ago in GH_CONTRIBUTIONS:
        pts = pr_pts if kind == "pr" else issue_pts
        url = f"https://github.com/{repo}/{kind}/{num}"
        db.upsert_contribution(
            user_id=users[ui]["id"], kind=kind, repo=repo, number=num,
            title=title, url=url, points=pts,
            happened_at=days_ago(ago),
        )

    for ui, etype, ref_id, title, company, deal_val, ago, art_url in CRM_CONTRIBUTIONS:
        from .crm_events import event_points
        pts = event_points(etype, settings)
        db.upsert_crm_contribution(
            user_id=users[ui]["id"], event_type=etype, reference_id=ref_id,
            title=title, company=company, deal_value=deal_val, points=pts,
            happened_at=days_ago(ago), artifact_url=art_url,
        )

    for name, desc, cost, img, stock in SWAG_ITEMS:
        db.create_swag_item(name=name, description=desc, point_cost=cost,
                            image_url=img, stock=stock)

    # Seed one pending swag order so the admin approval UI is populated.
    guido = users[8]
    item = db.all_swag_items()[0]  # first item = T-shirt
    db.create_swag_order(user_id=guido["id"], item_id=item["id"],
                         points_cost=item["point_cost"], item_name=item["name"],
                         notes="Size L please")
    from .workflow import initial_state
    wf = db.get_workflow()
    init = initial_state(wf)
    orders = db.orders_for(guido["id"])
    if orders:
        oid = orders[0]["id"]
        db._table("swag_orders").update(
            {"current_state": init, "status": init, "transition_log": []},
            doc_ids=[oid])

    # Notify admins of the seeded pending order.
    for u in users:
        if u.get("is_admin"):
            db.create_notification(
                u["id"],
                f"🛍️ {guido['name']} placed a swag order: {item['name']} ({item['point_cost']} pts)",
                kind="warning", link="/admin/orders")

    print(f"Seeded {len(users)} employees, {len(KUDOS)} kudos, "
          f"{len(GH_CONTRIBUTIONS)} GitHub activities, "
          f"{len(CRM_CONTRIBUTIONS)} CRM events, "
          f"{len(SWAG_ITEMS)} swag items, 1 pending order.")
    print("Admins:", ", ".join(u["name"] for u in users if u["is_admin"]))


if __name__ == "__main__":
    run()
