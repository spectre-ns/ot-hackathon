"""Authentication: GitHub OAuth + a demo-login fallback, on cookie sessions.

If GITHUB_CLIENT_ID/SECRET are configured the real OAuth flow is used. If not,
the UI offers a "demo login" that signs in as any seeded employee so the app is
always demoable without external credentials.
"""
from __future__ import annotations

import httpx
from fastapi import Cookie, Depends, HTTPException

from . import db
from .config import (
    BASE_URL, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, github_oauth_enabled,
)

SESSION_COOKIE = "kudos_session"
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"


def authorize_url(state: str) -> str:
    from urllib.parse import urlencode
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": f"{BASE_URL}/auth/github/callback",
        "scope": "read:user user:email",
        "state": state,
    }
    return f"{GITHUB_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": f"{BASE_URL}/auth/github/callback",
            },
            headers={"Accept": "application/json"},
            timeout=20.0,
        )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise HTTPException(400, "GitHub did not return an access token.")
    return token


async def fetch_github_profile(token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient() as client:
        u = await client.get(f"{GITHUB_API}/user", headers=headers, timeout=20.0)
        u.raise_for_status()
        profile = u.json()
        email = profile.get("email")
        if not email:  # primary email may be private; fetch the list
            er = await client.get(f"{GITHUB_API}/user/emails",
                                  headers=headers, timeout=20.0)
            if er.status_code == 200:
                emails = er.json()
                primary = next((e for e in emails if e.get("primary")), None)
                email = (primary or (emails[0] if emails else {})).get("email")
        profile["_email"] = email or f"{profile['login']}@users.noreply.github.com"
    return profile


def upsert_github_user(profile: dict) -> dict:
    """Find or create the local user for a GitHub profile."""
    existing = db.get_user_by_github_id(profile["id"])
    if existing:
        return db.update_user(
            existing["id"],
            avatar_url=profile.get("avatar_url", ""),
            github_login=profile.get("login"),
        )
    # Match a seeded user by email/login so demo accounts link cleanly.
    by_email = db.get_user_by_email(profile["_email"])
    by_login = db.get_user_by_github_login(profile.get("login", "")) \
        if profile.get("login") else None
    target = by_email or by_login
    if target:
        return db.update_user(
            target["id"],
            github_id=profile["id"],
            github_login=profile.get("login"),
            avatar_url=profile.get("avatar_url", ""),
        )
    return db.create_user(
        name=profile.get("name") or profile.get("login"),
        email=profile["_email"],
        github_id=profile["id"],
        github_login=profile.get("login"),
        avatar_url=profile.get("avatar_url", ""),
        title="",
        department="",
    )


def current_user(kudos_session: str | None = Cookie(default=None)) -> dict:
    """FastAPI dependency: the logged-in user, or 401."""
    session = db.get_session(kudos_session)
    if not session:
        raise HTTPException(401, "Not authenticated")
    user = db.get_user(session["user_id"])
    if not user:
        raise HTTPException(401, "Session user no longer exists")
    return user


def current_session(kudos_session: str | None = Cookie(default=None)) -> dict | None:
    return db.get_session(kudos_session)


def require_admin(user: dict = Depends(current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(403, "Admin privileges required")
    return user
