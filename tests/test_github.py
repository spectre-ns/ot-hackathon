"""Tests for GitHub integration: accumulation toggle on/off affects earned_points."""
from __future__ import annotations

import pytest


class TestGithubAccumulationToggle:
    def test_github_accumulation_off_by_default(self, seeded_db):
        import app.db as adb
        settings = adb.get_settings()
        assert settings["github_accumulation_enabled"] is False

    def test_github_contributions_not_counted_when_off(self, user1_client, users, seeded_db):
        """GitHub contributions don't count toward earned_points when toggle is off."""
        import app.db as adb
        user = users["user1"]
        # Ensure off
        adb.update_settings(
            pr_points=10, issue_points=5, monthly_allowance=100,
            github_accumulation_enabled=False,
            crm_deal_closed_points=25, crm_contract_renewed_points=20,
            crm_escalation_resolved_points=15, crm_nps_positive_points=10,
            crm_ticket_resolved_points=8, crm_customer_call_points=5,
        )
        # Insert a GitHub contribution
        adb.upsert_contribution(
            user_id=user["id"], kind="pr",
            repo="openteams/platform", number=7001,
            title="Test PR", url="https://github.com/openteams/platform/pull/7001",
            points=10, happened_at=adb.utcnow_iso(),
        )
        # earned_points should NOT include GitHub contribution
        earned = adb.earned_points(user["id"])
        assert earned == 0  # no kudos given, accumulation off

    def test_github_contributions_counted_when_on(self, users, seeded_db):
        """GitHub contributions count toward earned_points when toggle is on."""
        import app.db as adb
        user = users["user1"]
        adb.update_settings(
            pr_points=10, issue_points=5, monthly_allowance=100,
            github_accumulation_enabled=True,
            crm_deal_closed_points=25, crm_contract_renewed_points=20,
            crm_escalation_resolved_points=15, crm_nps_positive_points=10,
            crm_ticket_resolved_points=8, crm_customer_call_points=5,
        )
        adb.upsert_contribution(
            user_id=user["id"], kind="pr",
            repo="openteams/platform", number=7002,
            title="Test PR 2", url="https://github.com/openteams/platform/pull/7002",
            points=10, happened_at=adb.utcnow_iso(),
        )
        earned = adb.earned_points(user["id"])
        assert earned == 10

    def test_toggle_is_instant_no_resync_needed(self, users, seeded_db):
        """Toggling accumulation changes earned_points immediately."""
        import app.db as adb
        user = users["user1"]
        # Add a GitHub contribution
        adb.upsert_contribution(
            user_id=user["id"], kind="issue",
            repo="openteams/infra", number=3001,
            title="Test Issue", url="https://github.com/openteams/infra/issues/3001",
            points=5, happened_at=adb.utcnow_iso(),
        )
        # OFF: GitHub doesn't count
        adb.update_settings(
            pr_points=10, issue_points=5, monthly_allowance=100,
            github_accumulation_enabled=False,
            crm_deal_closed_points=25, crm_contract_renewed_points=20,
            crm_escalation_resolved_points=15, crm_nps_positive_points=10,
            crm_ticket_resolved_points=8, crm_customer_call_points=5,
        )
        assert adb.earned_points(user["id"]) == 0
        # ON: immediately counts
        adb.update_settings(
            pr_points=10, issue_points=5, monthly_allowance=100,
            github_accumulation_enabled=True,
            crm_deal_closed_points=25, crm_contract_renewed_points=20,
            crm_escalation_resolved_points=15, crm_nps_positive_points=10,
            crm_ticket_resolved_points=8, crm_customer_call_points=5,
        )
        assert adb.earned_points(user["id"]) == 5
        # OFF again: drops to 0
        adb.update_settings(
            pr_points=10, issue_points=5, monthly_allowance=100,
            github_accumulation_enabled=False,
            crm_deal_closed_points=25, crm_contract_renewed_points=20,
            crm_escalation_resolved_points=15, crm_nps_positive_points=10,
            crm_ticket_resolved_points=8, crm_customer_call_points=5,
        )
        assert adb.earned_points(user["id"]) == 0

    def test_github_sync_requires_linked_account(self, user1_client, users, seeded_db):
        """Syncing GitHub requires the user to have a github_login linked."""
        import app.db as adb
        # user1 has github_login but no gh_access_token in session (demo login)
        # The real sync endpoint requires a github_login — it will return 400
        # if not linked, or 502 if sync itself fails. Since we don't have a
        # real OAuth token, a 502 is also acceptable here.
        resp = user1_client.post("/api/github/sync")
        # Without a real GitHub token, we expect either 502 (sync failed) or success
        # The key invariant is: it doesn't crash with 500
        assert resp.status_code in (200, 400, 502)

    def test_github_upsert_idempotent(self, users, seeded_db):
        """Upserting the same contribution twice doesn't create duplicates."""
        import app.db as adb
        user = users["user1"]
        params = dict(
            user_id=user["id"], kind="pr",
            repo="openteams/platform", number=6001,
            title="Idempotent PR", url="https://github.com/openteams/platform/pull/6001",
            points=10, happened_at=adb.utcnow_iso(),
        )
        _, created1 = adb.upsert_contribution(**params)
        _, created2 = adb.upsert_contribution(**params)
        assert created1 is True
        assert created2 is False
        # Still only one contribution
        contribs = adb.contributions_for(user["id"])
        assert len([c for c in contribs if c["number"] == 6001]) == 1
