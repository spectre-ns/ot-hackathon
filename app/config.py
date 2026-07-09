"""Runtime configuration, read from environment variables.

Everything has a safe default so the app runs out-of-the-box in "demo mode"
(no GitHub OAuth required). Set the GITHUB_* vars to enable real login + sync.
"""
import os

# --- GitHub OAuth (optional) ---------------------------------------------
# Create an OAuth app at https://github.com/settings/developers and set the
# callback URL to {BASE_URL}/auth/github/callback
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")

# A personal access token used as a fallback for the contribution sync when a
# user logged in via demo mode (no OAuth token of their own). Optional.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Public base URL of this app (used to build the OAuth callback).
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# --- App ------------------------------------------------------------------
# Path to the TinyDB JSON document store.
DATABASE_FILE = os.getenv("DATABASE_FILE", "kudos_db.json")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

# Default monthly allowance of points each employee can GIVE away.
DEFAULT_MONTHLY_ALLOWANCE = int(os.getenv("DEFAULT_MONTHLY_ALLOWANCE", "100"))


# Set DEMO_LOGIN=false to disable the password-free demo login endpoint in
# production. Defaults to enabled so the app works out-of-the-box without OAuth.
DEMO_LOGIN = os.getenv("DEMO_LOGIN", "true").lower() == "true"

# --- Slack (optional) -----------------------------------------------------
# Post kudos announcements to a Slack channel via an Incoming Webhook.
# Create one at https://api.slack.com/messaging/webhooks and paste the URL
# here. Leave unset to keep Slack posting disabled (the default) — the app
# works fine without it.
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


def github_oauth_enabled() -> bool:
    return bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)


def slack_enabled() -> bool:
    return bool(SLACK_WEBHOOK_URL)
