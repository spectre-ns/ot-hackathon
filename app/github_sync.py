"""Pull a user's GitHub activity for display in their profile.

GitHub activity is NON-ACCUMULATING: merged PRs and closed issues are stored
for informational display (so peers can see what someone has been working on)
but they do NOT automatically award points. Points for GitHub work come from a
human explicitly giving kudos and linking the PR/issue as the artifact.

This design is intentional: not all PRs are equally valuable, and automated
point-per-PR incentivises volume over impact. Human curation is required.

Auth precedence:
  1. The user's own OAuth token (captured at login)
  2. Server-wide GITHUB_TOKEN env var
  3. Unauthenticated (rate-limited to 60 req/h — fine for a demo)

Future Salesforce note: this module is GitHub-only.  CRM events come through
the /api/crm/event webhook instead.
"""
from __future__ import annotations

import httpx

from . import db
from .config import GITHUB_TOKEN

GITHUB_API = "https://api.github.com"


def _headers(token: str | None) -> dict:
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _search(client: httpx.Client, query: str, token: str | None) -> list[dict]:
    items: list[dict] = []
    page = 1
    while page <= 5:
        resp = client.get(
            f"{GITHUB_API}/search/issues",
            params={"q": query, "per_page": 100, "page": page},
            headers=_headers(token),
            timeout=20.0,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"GitHub API error {resp.status_code}: {resp.text[:200]}")
        batch = resp.json().get("items", [])
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


def _repo_from_url(html_url: str) -> str:
    try:
        parts = html_url.split("github.com/", 1)[1].split("/")
        return f"{parts[0]}/{parts[1]}"
    except (IndexError, ValueError):
        return "unknown/unknown"


def sync_user(user: dict, oauth_token: str | None = None) -> dict:
    """Fetch a user's merged PRs and closed issues and store them.

    The point value stored per contribution comes from the current Settings weights
    (pr_points / issue_points). Whether those points COUNT toward earned_points is
    controlled by the ``github_accumulation_enabled`` toggle in Settings — this
    function always stores the configured weight so toggling on/off is instant
    without needing a re-sync.

    Returns a summary of what was seen / newly stored.
    """
    login = user.get("github_login")
    if not login:
        raise ValueError("This user has no linked GitHub account.")

    token = oauth_token or GITHUB_TOKEN or None
    settings = db.get_settings()
    pr_pts = settings["pr_points"]
    issue_pts = settings["issue_points"]

    summary = {"prs_added": 0, "issues_added": 0,
               "prs_seen": 0, "issues_seen": 0}

    with httpx.Client() as client:
        prs = _search(client, f"author:{login} type:pr is:merged", token)
        issues = _search(client, f"author:{login} type:issue is:closed", token)

    summary["prs_seen"] = len(prs)
    summary["issues_seen"] = len(issues)

    for item in prs:
        _, created = db.upsert_contribution(
            user_id=user["id"], kind="pr",
            repo=_repo_from_url(item.get("html_url", "")),
            number=item.get("number", 0),
            title=item.get("title", ""),
            url=item.get("html_url", ""),
            points=pr_pts,
            happened_at=item.get("closed_at") or item.get("updated_at") or "",
        )
        if created:
            summary["prs_added"] += 1

    for item in issues:
        _, created = db.upsert_contribution(
            user_id=user["id"], kind="issue",
            repo=_repo_from_url(item.get("html_url", "")),
            number=item.get("number", 0),
            title=item.get("title", ""),
            url=item.get("html_url", ""),
            points=issue_pts,
            happened_at=item.get("closed_at") or item.get("updated_at") or "",
        )
        if created:
            summary["issues_added"] += 1

    return summary
