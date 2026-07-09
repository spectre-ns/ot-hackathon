"""Tests for the outbound Slack integration (Incoming Webhook).

The webhook URL lives in Settings (``settings.slack_webhook_url``) and is
editable via Admin → Settings. Slack is disabled unless it is set. When
disabled every function is a silent no-op; when enabled a kudos post fires
exactly one webhook request. A failing/unreachable Slack must never break
giving kudos.
"""
from __future__ import annotations

import httpx
import pytest


WEBHOOK = "https://hooks.slack.com/services/T000/B000/xxxxxxxx"


class _FakeResponse:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


@pytest.fixture
def enable_slack(seeded_db):
    """Set a webhook URL in settings so Slack is enabled for the test."""
    import app.db as adb
    adb.update_settings(slack_webhook_url=WEBHOOK)


@pytest.fixture
def capture_slack(enable_slack, monkeypatch):
    """Slack enabled + every httpx.post made by app.slack captured."""
    import app.slack as slk
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse(200, "ok")

    monkeypatch.setattr(slk.httpx, "post", fake_post)
    return calls


class TestSlackDisabled:
    def test_disabled_by_default(self, seeded_db):
        import app.slack as slk
        # Fresh settings have no webhook configured.
        assert slk.enabled() is False

    def test_notify_is_noop_when_disabled(self, seeded_db, monkeypatch):
        import app.slack as slk
        posted = []
        monkeypatch.setattr(slk.httpx, "post",
                            lambda *a, **k: posted.append(1))

        result = slk.notify_kudos(
            {"name": "Ada"}, {"name": "Alan"}, 10, "great_teammate", "hi")
        assert result is False
        assert posted == []  # nothing sent when disabled


class TestSlackEnabled:
    def test_enabled_when_webhook_set(self, enable_slack):
        import app.slack as slk
        assert slk.enabled() is True
        assert slk.webhook_url() == WEBHOOK

    def test_notify_posts_once(self, capture_slack):
        import app.slack as slk
        result = slk.notify_kudos(
            {"name": "Ada Lovelace"}, {"name": "Alan Turing"},
            10, "great_teammate", "Amazing pairing session!")
        assert result is True
        assert len(capture_slack) == 1

    def test_payload_contents(self, capture_slack):
        import app.slack as slk
        slk.notify_kudos(
            {"name": "Ada Lovelace"}, {"name": "Alan Turing"},
            10, "great_teammate", "Amazing pairing session!")
        payload = capture_slack[0]["json"]
        assert capture_slack[0]["url"] == WEBHOOK
        # Fallback text carries the key facts.
        assert "Ada Lovelace" in payload["text"]
        assert "Alan Turing" in payload["text"]
        assert "10 pts" in payload["text"]
        assert "Great Teammate" in payload["text"]
        # Block Kit blocks present; message rendered as a quote block.
        assert any("Amazing pairing session!" in str(b) for b in payload["blocks"])

    def test_empty_message_omits_quote_block(self, capture_slack):
        import app.slack as slk
        slk.notify_kudos(
            {"name": "Ada"}, {"name": "Alan"}, 5, "innovator", "")
        blocks = capture_slack[0]["json"]["blocks"]
        # Only the header section, no quote block for an empty message.
        assert len(blocks) == 1


class TestSlackFailureIsolation:
    def test_network_error_returns_false_not_raises(self, enable_slack, monkeypatch):
        import app.slack as slk

        def boom(*a, **k):
            raise httpx.ConnectError("slack down")

        monkeypatch.setattr(slk.httpx, "post", boom)
        # Must swallow the error rather than propagate it.
        assert slk.notify_kudos(
            {"name": "Ada"}, {"name": "Alan"}, 5, "mentor", "x") is False

    def test_non_200_returns_false(self, enable_slack, monkeypatch):
        import app.slack as slk
        monkeypatch.setattr(
            slk.httpx, "post",
            lambda *a, **k: _FakeResponse(404, "no_service"))
        assert slk.notify_kudos(
            {"name": "Ada"}, {"name": "Alan"}, 5, "mentor", "x") is False


class TestSlackSettingsEndpoint:
    def test_admin_can_set_webhook_via_settings(self, admin_client):
        body = _settings_payload(slack_webhook_url=WEBHOOK)
        resp = admin_client.put("/api/settings", json=body)
        assert resp.status_code == 200
        assert resp.json()["slack_webhook_url"] == WEBHOOK

    def test_admin_can_clear_webhook(self, admin_client):
        admin_client.put("/api/settings", json=_settings_payload(slack_webhook_url=WEBHOOK))
        resp = admin_client.put("/api/settings", json=_settings_payload(slack_webhook_url=""))
        assert resp.status_code == 200
        assert resp.json()["slack_webhook_url"] == ""

    def test_invalid_webhook_url_rejected(self, admin_client):
        body = _settings_payload(slack_webhook_url="https://evil.example.com/hook")
        resp = admin_client.put("/api/settings", json=body)
        assert resp.status_code == 422

    def test_webhook_not_leaked_in_public_config(self, admin_client, client):
        admin_client.put("/api/settings", json=_settings_payload(slack_webhook_url=WEBHOOK))
        data = client.get("/api/config").json()
        assert "slack_webhook_url" not in data.get("settings", {})


class TestKudosEndpointIntegration:
    def test_giving_kudos_posts_to_slack(self, user1_client, users, capture_slack):
        receiver = users["user2"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 10,
            "value_key": "great_teammate",
            "message": "Awesome collaboration!",
        })
        assert resp.status_code == 200
        assert len(capture_slack) == 1
        assert receiver["name"] in capture_slack[0]["json"]["text"]

    def test_kudos_succeeds_when_slack_fails(self, user1_client, users, enable_slack, monkeypatch):
        import app.slack as slk

        def boom(*a, **k):
            raise httpx.ConnectError("slack down")

        monkeypatch.setattr(slk.httpx, "post", boom)
        receiver = users["user2"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 10,
            "value_key": "great_teammate",
            "message": "Still works!",
        })
        # Slack outage must not break kudos.
        assert resp.status_code == 200
        assert resp.json()["points"] == 10

    def test_no_slack_call_when_disabled(self, user1_client, users, monkeypatch):
        import app.slack as slk
        posted = []
        monkeypatch.setattr(slk.httpx, "post", lambda *a, **k: posted.append(1))
        receiver = users["user2"]
        resp = user1_client.post("/api/kudos", json={
            "receiver_id": receiver["id"],
            "points": 10,
            "value_key": "great_teammate",
            "message": "No slack configured",
        })
        assert resp.status_code == 200
        assert posted == []


def _settings_payload(**overrides) -> dict:
    """A complete, valid SettingsBody payload with optional overrides."""
    body = {
        "pr_points": 10,
        "issue_points": 5,
        "monthly_allowance": 100,
        "github_accumulation_enabled": False,
        "crm_accumulation_enabled": True,
        "crm_deal_closed_points": 25,
        "crm_contract_renewed_points": 20,
        "crm_escalation_resolved_points": 15,
        "crm_nps_positive_points": 10,
        "crm_ticket_resolved_points": 8,
        "crm_customer_call_points": 5,
    }
    body.update(overrides)
    return body
