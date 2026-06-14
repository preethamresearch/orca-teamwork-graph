"""Authentication — mock SSO + sessions (real-ready).

A session token is issued on sign-in and stored in the DB. The web app sends it
as an httpOnly cookie; programmatic surfaces (CLI/MCP) can pass it as a header.
Swapping in real Microsoft Entra (MSAL) only changes how the user identity is
obtained before `create_session` — the rest is unchanged.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from . import db

COOKIE = "oracle_session"


def token_from(request: Request) -> str | None:
    return request.cookies.get(COOKIE) or request.headers.get("x-oracle-token")


def current_user(request: Request) -> dict:
    user = db.user_for_token(token_from(request))
    if not user:
        raise HTTPException(401, "not signed in")
    return user


def current_workspace(request: Request) -> tuple[dict, dict]:
    user = current_user(request)
    ws = db.workspace_for_user(user["id"])
    if not ws:
        raise HTTPException(500, "no workspace for user")
    return user, ws
