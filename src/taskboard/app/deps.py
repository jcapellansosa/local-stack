"""FastAPI dependencies — small helpers that pull state out of `request.app.state`
and inject typed objects into route handlers.
"""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request, status

from .auth import SESSION_COOKIE, Authenticator, Session


def get_auth(request: Request) -> Authenticator:
    return request.app.state.auth


def get_pool(request: Request):
    return request.app.state.pool


def current_session(
    auth: Authenticator = Depends(get_auth),
    tb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> Session | None:
    """Returns the active session, or None. Use this when auth is optional."""
    return auth.get_session(tb_session)


def require_session(
    sess: Session | None = Depends(current_session),
) -> Session:
    """Use this on /api/* endpoints — 401s if unauthenticated."""
    if sess is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthenticated")
    return sess
