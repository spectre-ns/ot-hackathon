"""CRM event type definitions.

Each type maps to a configurable point weight stored in Settings. The webhook
payload (and the simulator) use the ``key`` field to identify the event.

Future Salesforce integration path:
  Salesforce Platform Events / Flow outbound messages send JSON to a configurable
  URL. A thin adapter (or a Salesforce Named Credential + Apex class) maps
  Salesforce field names → our webhook schema and POSTs to /api/crm/event with
  the X-CRM-Key header. No changes to this service are needed.
"""

CRM_EVENT_TYPES = [
    {
        "key": "deal_closed",
        "label": "Deal Closed",
        "emoji": "🤝",
        "default_points": 25,
        "settings_key": "crm_deal_closed_points",
        "desc": "Closed a new business deal",
        "placeholder_title": "Closed deal with {company}",
    },
    {
        "key": "contract_renewed",
        "label": "Contract Renewed",
        "emoji": "🔄",
        "default_points": 20,
        "settings_key": "crm_contract_renewed_points",
        "desc": "Successfully renewed a customer contract",
        "placeholder_title": "Renewed {company} contract",
    },
    {
        "key": "escalation_resolved",
        "label": "Escalation Resolved",
        "emoji": "🚨",
        "default_points": 15,
        "settings_key": "crm_escalation_resolved_points",
        "desc": "Resolved a customer escalation",
        "placeholder_title": "Resolved {company} escalation",
    },
    {
        "key": "nps_positive",
        "label": "Positive NPS",
        "emoji": "⭐",
        "default_points": 10,
        "settings_key": "crm_nps_positive_points",
        "desc": "Received a positive NPS/CSAT score (≥ 9)",
        "placeholder_title": "NPS 10 from {company}",
    },
    {
        "key": "ticket_resolved",
        "label": "Ticket Resolved",
        "emoji": "✅",
        "default_points": 8,
        "settings_key": "crm_ticket_resolved_points",
        "desc": "Resolved a customer support ticket",
        "placeholder_title": "Resolved support ticket for {company}",
    },
    {
        "key": "customer_call",
        "label": "Customer Call",
        "emoji": "📞",
        "default_points": 5,
        "settings_key": "crm_customer_call_points",
        "desc": "Completed a customer call or demo",
        "placeholder_title": "Demo call with {company}",
    },
]

CRM_EVENTS_BY_KEY = {e["key"]: e for e in CRM_EVENT_TYPES}

CRM_SETTINGS_DEFAULTS = {
    e["settings_key"]: e["default_points"] for e in CRM_EVENT_TYPES
}


def event_points(event_key: str, settings: dict) -> int:
    """Return the configured point value for this event type."""
    et = CRM_EVENTS_BY_KEY.get(event_key)
    if not et:
        return 0
    return settings.get(et["settings_key"], et["default_points"])
