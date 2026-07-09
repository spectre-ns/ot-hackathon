"""Tests for the outbound Slack integration (Incoming Webhook).

Slack is disabled unless SLACK_WEBHOOK_URL is configured. When disabled every
function is a silent no-op; when enabled a kudos post fires exactly one webhook
request. Crucially, a failing/unreachable Slack must never break giving kudos.
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
def capture_slack(monkeypatch):
    """Enable Slack and capture every httpx.post call made by app.slack."""
    import app.config as cfg
    import app.slack as slk
    monkeypatch.setattr(cfg, "SLACK_WEBHOOK_URL", WEBHOOK)
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse(200, "ok")

    monkeypatch.setattr(slk.httpx, "post", fake_post)
    return calls


class TestSlackDisabled:
    def test_disabled_by_default(self):
        import app.config as cfg
        # Default config has no webhook set.
        assert cfg.slack_enabled() is False

    def test_notify_is_noop_when_disabled(self, monkeypatch):
        import app.config as cfg
        import app.slack as slk
        monkeypatch.setattr(cfg, "SLACK_WEBHOOK_URL", "")

        posted = []
        monkeypatch.setattr(slk.httpx, "post",
                            lambda *a, **k: posted.append(1))

        result = slk.notify_kudos(
            {"name": "Ada"}, {"name": "Alan"}, 10, "great_teammate", "hi")
        assert result is False
        assert posted == []  # nothing sent when disabled


class TestSlackEnabled:
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
    def test_network_error_returns_false_not_raises(self, monkeypatch):
        import app.config as cfg
        import app.slack as slk
        monkeypatch.setattr(cfg, "SLACK_WEBHOOK_URL", WEBHOOK)

        def boom(*a, **k):
            raise httpx.ConnectError("slack down")

        monkeypatch.setattr(slk.httpx, "post", boom)
        # Must swallow the error rather than propagate it.
        assert slk.notify_kudos(
            {"name": "Ada"}, {"name": "Alan"}, 5, "mentor", "x") is False

    def test_non_200_returns_false(self, monkeypatch):
        import app.config as cfg
        import app.slack as slk
        monkeypatch.setattr(cfg, "SLACK_WEBHOOK_URL", WEBHOOK)
        monkeypatch.setattr(
            slk.httpx, "post",
            lambda *a, **k: _FakeResponse(404, "no_service"))
        assert slk.notify_kudos(
            {"name": "Ada"}, {"name": "Alan"}, 5, "mentor", "x") is False


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

    def test_kudos_succeeds_when_slack_fails(self, user1_client, users, monkeypatch):
        import app.config as cfg
        import app.slack as slk
        monkeypatch.setattr(cfg, "SLACK_WEBHOOK_URL", WEBHOOK)

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
        import app.config as cfg
        import app.slack as slk
        monkeypatch.setattr(cfg, "SLACK_WEBHOOK_URL", "")
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
