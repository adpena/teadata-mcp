from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def verify_assistant_sso_token(
    token: str,
    *,
    secret: str,
    clock_skew_seconds: int = 60,
) -> dict[str, Any] | None:
    try:
        payload_b64, signature_b64 = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    expected_signature_b64 = _b64url_encode(expected_signature)
    if not hmac.compare_digest(expected_signature_b64, signature_b64):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (json.JSONDecodeError, ValueError):
        return None

    now = int(time.time())
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < now - clock_skew_seconds:
        return None

    iat = payload.get("iat")
    if isinstance(iat, int) and iat > now + clock_skew_seconds:
        return None

    sub = payload.get("sub")
    if not isinstance(sub, int):
        return None

    version = payload.get("v")
    if version not in (None, 1):
        return None

    return payload


def parse_cookie_header(raw_cookie: str) -> dict[str, str]:
    cookie = SimpleCookie()
    cookie.load(raw_cookie)
    return {key: morsel.value for key, morsel in cookie.items()}


def extract_header(
    headers: list[tuple[bytes, bytes]],
    name: bytes,
) -> str | None:
    name_lower = name.lower()
    for key, value in headers:
        if key.lower() == name_lower:
            return value.decode("latin-1")
    return None


def extract_bearer_token(headers: list[tuple[bytes, bytes]]) -> str | None:
    auth_header = extract_header(headers, b"authorization")
    if not auth_header:
        return None
    prefix = "bearer "
    if auth_header.lower().startswith(prefix):
        return auth_header[len(prefix) :].strip()
    return None


def extract_cookie_token(
    headers: list[tuple[bytes, bytes]],
    *,
    cookie_name: str,
) -> str | None:
    raw_cookie = extract_header(headers, b"cookie")
    if not raw_cookie:
        return None
    cookies = parse_cookie_header(raw_cookie)
    token = cookies.get(cookie_name)
    if token:
        return token
    return None


@dataclass(frozen=True)
class AssistantAuthConfig:
    enforce: bool
    cookie_name: str
    secret: str | None
    launch_url: str
    clock_skew_seconds: int

    @classmethod
    def from_env(cls) -> "AssistantAuthConfig":
        secret = os.getenv("TEADATA_ASSISTANT_SSO_SECRET")
        enforce_env = os.getenv("TEADATA_ASSISTANT_ENFORCE_SSO")
        if enforce_env is None:
            enforce = bool(secret)
        else:
            enforce = enforce_env.lower() in {"1", "true", "t", "yes", "y"}

        return cls(
            enforce=enforce,
            cookie_name=os.getenv("TEADATA_ASSISTANT_COOKIE_NAME", "teadata_assistant_sso"),
            secret=secret,
            launch_url=os.getenv(
                "TEADATA_ASSISTANT_LAUNCH_URL",
                "https://dataforpubliceducation.com/assistant/launch/",
            ),
            clock_skew_seconds=int(os.getenv("TEADATA_ASSISTANT_SSO_SKEW_SECONDS", "60")),
        )


def authenticate_from_headers(
    headers: list[tuple[bytes, bytes]],
    *,
    config: AssistantAuthConfig,
) -> dict[str, Any] | None:
    if not config.enforce:
        return None

    if not config.secret:
        return None

    token = extract_bearer_token(headers)
    if not token:
        token = extract_cookie_token(headers, cookie_name=config.cookie_name)
    if not token:
        return None

    return verify_assistant_sso_token(
        token,
        secret=config.secret,
        clock_skew_seconds=config.clock_skew_seconds,
    )
