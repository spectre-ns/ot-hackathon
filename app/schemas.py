"""Pydantic request bodies."""
from typing import Optional

from pydantic import BaseModel, Field


class DemoLoginBody(BaseModel):
    user_id: int


class KudosBody(BaseModel):
    receiver_id: int
    points: int = Field(ge=1, le=100)
    value_key: str
    message: str = Field(min_length=1, max_length=500)
    # Optional artifact link for traceability (GitHub PR, Jira ticket, CRM deal, etc.)
    artifact_url: Optional[str] = Field(default="", max_length=800)
    artifact_label: Optional[str] = Field(default="", max_length=200)


class ReactBody(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)


class SettingsBody(BaseModel):
    pr_points: int = Field(ge=0, le=1000)
    issue_points: int = Field(ge=0, le=1000)
    monthly_allowance: int = Field(ge=0, le=100000)
    github_accumulation_enabled: bool = False
    crm_accumulation_enabled: bool = True
    crm_deal_closed_points: int = Field(ge=0, le=1000)
    crm_contract_renewed_points: int = Field(ge=0, le=1000)
    crm_escalation_resolved_points: int = Field(ge=0, le=1000)
    crm_nps_positive_points: int = Field(ge=0, le=1000)
    crm_ticket_resolved_points: int = Field(ge=0, le=1000)
    crm_customer_call_points: int = Field(ge=0, le=1000)


class SwagItemBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    point_cost: int = Field(ge=1, le=1000000)
    image_url: str = Field(default="", max_length=800)
    stock: Optional[int] = None  # None = unlimited
    is_available: bool = True


class SwagOrderBody(BaseModel):
    item_id: int
    notes: str = Field(default="", max_length=500)


class OrderTransitionBody(BaseModel):
    transition_id: str
    reason: str = Field(default="", max_length=500)


class WorkflowStateBody(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: str = Field(default="#4D75FE", max_length=20)
    is_terminal: bool = False


class WorkflowTransitionBody(BaseModel):
    from_state: str
    to_state: str
    label: str = Field(min_length=1, max_length=80)
    requires_admin: bool = True
    requires_reason: bool = False


class DeleteTransitionBody(BaseModel):
    transition_id: str


class CRMEventBody(BaseModel):
    """Webhook payload schema.

    This is what a real CRM (Salesforce, HubSpot, Pipedrive) would POST to
    /api/crm/event.  When wiring up Salesforce: create a Flow or Apex trigger
    that fires on the relevant object (Opportunity, Case, etc.) and use a
    Named Credential + HTTP Callout Action to POST this JSON with the
    'X-CRM-Key' header set to the value shown in the Admin panel.

    ``user_identifier`` can be a GitHub login (preferred) or an email address.
    """
    event_type: str  # one of the keys in CRM_EVENT_TYPES
    user_identifier: str  # github_login or email
    reference_id: str  # unique external ID (e.g. "OPP-8821", "CASE-004")
    title: str = Field(default="", max_length=300)
    company: str = Field(default="", max_length=200)
    deal_value: Optional[int] = None  # USD, optional, informational
    notes: str = Field(default="", max_length=500)
    happened_at: str = Field(default="")
    artifact_url: str = Field(default="", max_length=800)
