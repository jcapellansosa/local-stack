"""/auth/{login,callback,logout} — the BFF endpoints."""

from __future__ import annotations

import base64
import json

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from ..auth import FLOW_COOKIE, SESSION_COOKIE, SESSION_TTL, Authenticator, FlowState
from ..deps import get_auth

router = APIRouter(prefix="/auth")


@router.get("/login")
async def login(
    request: Request,
    return_to: str = "/",
    auth: Authenticator = Depends(get_auth),
):
    # FastAPI exposes ?return=... in query string as return_to via param name.
    # We accept `return` as well for browser convenience.
    return_to = request.query_params.get("return") or return_to

    fs, authorize_url = auth.start_flow(return_to)

    resp = RedirectResponse(authorize_url, status_code=302)
    _set_flow_cookie(resp, fs, auth.cookie_insecure)
    return resp


@router.get("/callback")
async def callback(
    request: Request,
    auth: Authenticator = Depends(get_auth),
    tb_flow: str | None = Cookie(default=None, alias=FLOW_COOKIE),
):
    if not tb_flow:
        raise HTTPException(status_code=400, detail="missing flow cookie")
    try:
        fs = _read_flow_cookie(tb_flow)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"bad flow cookie: {e}") from e

    try:
        sess = await auth.complete_flow(fs, dict(request.query_params))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    resp = RedirectResponse(fs.return_to, status_code=302)
    _clear_flow_cookie(resp, auth.cookie_insecure)
    _set_session_cookie(resp, sess.id, auth.cookie_insecure)
    return resp


@router.post("/logout")
async def logout(
    auth: Authenticator = Depends(get_auth),
    tb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    auth.drop_session(tb_session)
    resp = Response(status_code=204)
    _clear_session_cookie(resp, auth.cookie_insecure)
    return resp


# --- cookie helpers ---


def _set_session_cookie(resp: Response, sid: str, insecure: bool) -> None:
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=sid,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=not insecure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(resp: Response, insecure: bool) -> None:
    resp.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=not insecure, samesite="lax")


def _set_flow_cookie(resp: Response, fs: FlowState, insecure: bool) -> None:
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "state": fs.state,
                "nonce": fs.nonce,
                "code_verifier": fs.code_verifier,
                "return_to": fs.return_to,
            }
        ).encode()
    ).decode()
    resp.set_cookie(
        key=FLOW_COOKIE,
        value=payload,
        max_age=600,
        httponly=True,
        secure=not insecure,
        samesite="lax",
        path="/auth/",
    )


def _clear_flow_cookie(resp: Response, insecure: bool) -> None:
    resp.delete_cookie(FLOW_COOKIE, path="/auth/", httponly=True, secure=not insecure, samesite="lax")


def _read_flow_cookie(raw: str) -> FlowState:
    data = json.loads(base64.urlsafe_b64decode(raw).decode())
    for k in ("state", "nonce", "code_verifier", "return_to"):
        if k not in data:
            raise ValueError(f"missing field: {k}")
    return FlowState(**data)
