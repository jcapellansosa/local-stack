"""App configuration, loaded from environment variables.

Pydantic-settings reads env vars into a typed Settings object and raises a
clear error if any required value is missing. One instance is constructed
at startup and injected via FastAPI's dependency system.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Where the server listens. Defaults match the Dockerfile EXPOSE.
    host: str = "0.0.0.0"
    port: int = 8080

    # Postgres connection string. asyncpg-style (postgresql://...).
    database_url: str

    # Public-facing base URL. Used to construct the OIDC redirect URI.
    # Example: http://taskboard.local
    public_base_url: str = Field(..., description="No trailing slash")

    # Keycloak.
    oidc_issuer: str  # e.g. http://keycloak/realms/taskboard
    oidc_client_id: str = "taskboard"

    # Cookie security. For the plain-http minikube demo we have to turn off
    # the Secure flag, otherwise the browser drops the session cookie.
    cookie_insecure: bool = False

    @property
    def oidc_redirect_uri(self) -> str:
        return f"{self.public_base_url.rstrip('/')}/auth/callback"


@lru_cache  # Settings is read once per process.
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
