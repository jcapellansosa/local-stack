"""OIDC backend-for-frontend.

Flow:
  /auth/login    -> generate state+nonce+PKCE, stash in short-lived cookie,
                    redirect to Keycloak's authorization endpoint.
  /auth/callback -> validate state, exchange code for tokens (PKCE),
                    verify the ID token, create an in-memory session,
                    drop a tb_session cookie, redirect back to the SPA.
  /auth/logout   -> drop the session and clear cookies.

Tokens NEVER reach the browser — only an opaque session ID does. That's
the BFF pattern.
"""

from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError

SESSION_COOKIE = "tb_session"
FLOW_COOKIE = "tb_flow"  # short-lived cookie carrying state/nonce/verifier
SESSION_TTL = timedelta(hours=8)


@dataclass
class Session:
    id: str
    sub: str          # OIDC subject — stable user ID
    email: str
    name: str
    id_token: str
    access_token: str
    refresh_token: str | None
    expires_at: datetime


@dataclass
class FlowState:
    state: str
    nonce: str
    code_verifier: str
    return_to: str


@dataclass
class OIDCMetadata:
    """Parsed /.well-known/openid-configuration plus the JWKS."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks: Any  # authlib KeySet


class Authenticator:
    """Holds OIDC config + the in-memory session store.

    Constructed once at startup via `build()`. The store is a plain dict;
    restarting the pod logs everyone out — fine for a single-replica demo.
    """

    def __init__(
        self,
        meta: OIDCMetadata,
        client_id: str,
        redirect_uri: str,
        cookie_insecure: bool,
    ) -> None:
        self.meta = meta
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.cookie_insecure = cookie_insecure
        self._sessions: dict[str, Session] = {}

    @classmethod
    async def build(
        cls,
        issuer: str,
        client_id: str,
        redirect_uri: str,
        cookie_insecure: bool,
    ) -> "Authenticator":
        async with httpx.AsyncClient(timeout=10.0) as client:
            disc = (await client.get(f"{issuer}/.well-known/openid-configuration")).json()
            jwks_raw = (await client.get(disc["jwks_uri"])).json()
        meta = OIDCMetadata(
            issuer=disc["issuer"],
            authorization_endpoint=disc["authorization_endpoint"],
            token_endpoint=disc["token_endpoint"],
            jwks=JsonWebKey.import_key_set(jwks_raw),
        )
        return cls(meta, client_id, redirect_uri, cookie_insecure)

    # --- session lifecycle ---

    def get_session(self, session_id: str | None) -> Session | None:
        if not session_id:
            return None
        sess = self._sessions.get(session_id)
        if sess is None:
            return None
        if datetime.now(timezone.utc) > sess.expires_at:
            self._sessions.pop(session_id, None)
            return None
        return sess

    def put_session(self, sess: Session) -> None:
        self._sessions[sess.id] = sess

    def drop_session(self, session_id: str | None) -> None:
        if session_id:
            self._sessions.pop(session_id, None)

    # --- OIDC flow building blocks ---

    def start_flow(self, return_to: str) -> tuple[FlowState, str]:
        """Returns (flow_state, authorize_url). Caller stashes flow_state in a cookie."""
        verifier = secrets.token_urlsafe(64)
        challenge = _pkce_s256(verifier)
        fs = FlowState(
            state=secrets.token_urlsafe(24),
            nonce=secrets.token_urlsafe(24),
            code_verifier=verifier,
            return_to=_safe_return(return_to),
        )
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope="openid profile email",
            code_challenge_method="S256",
        )
        authorize_url, _ = client.create_authorization_url(
            self.meta.authorization_endpoint,
            state=fs.state,
            nonce=fs.nonce,
            code_challenge=challenge,
        )
        return fs, authorize_url

    async def complete_flow(self, fs: FlowState, query: dict[str, str]) -> Session:
        if query.get("state") != fs.state:
            raise ValueError("state mismatch")
        code = query.get("code")
        if not code:
            raise ValueError("missing code")

        async with AsyncOAuth2Client(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope="openid profile email",
        ) as client:
            token = await client.fetch_token(
                self.meta.token_endpoint,
                code=code,
                code_verifier=fs.code_verifier,
                grant_type="authorization_code",
            )

        id_token_raw = token.get("id_token")
        if not id_token_raw:
            raise ValueError("no id_token in response")

        try:
            claims = jwt.decode(
                id_token_raw,
                self.meta.jwks,
                claims_options={
                    "iss": {"essential": True, "value": self.meta.issuer},
                    "aud": {"essential": True, "value": self.client_id},
                    "nonce": {"essential": True, "value": fs.nonce},
                },
            )
            claims.validate()
        except JoseError as e:
            raise ValueError(f"id_token validation failed: {e}") from e

        sess = Session(
            id=secrets.token_urlsafe(32),
            sub=str(claims["sub"]),
            email=str(claims.get("email", "")),
            name=str(claims.get("name") or claims.get("preferred_username") or ""),
            id_token=id_token_raw,
            access_token=str(token["access_token"]),
            refresh_token=token.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + SESSION_TTL,
        )
        self.put_session(sess)
        return sess


# --- helpers ---


def _pkce_s256(verifier: str) -> str:
    import hashlib

    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _safe_return(p: str | None) -> str:
    """Only allow same-origin paths; falls back to /."""
    if not p or not p.startswith("/") or p.startswith("//"):
        return "/"
    return p
