from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from teadata_mcp.assistant_auth import verify_assistant_sso_token


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _make_token(secret: str, payload: dict) -> str:
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    payload_b64 = _b64url_encode(payload_bytes)
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{payload_b64}.{signature_b64}"


def test_verify_assistant_sso_token_accepts_valid_token():
    secret = "super-secret"
    now = int(time.time())
    payload = {
        "v": 1,
        "sub": 123,
        "username": "alex",
        "org_id": None,
        "iat": now,
        "exp": now + 60,
    }
    token = _make_token(secret, payload)

    verified = verify_assistant_sso_token(token, secret=secret)

    assert verified is not None
    assert verified["sub"] == 123
    assert verified["username"] == "alex"


def test_verify_assistant_sso_token_rejects_bad_signature():
    secret = "super-secret"
    now = int(time.time())
    payload = {
        "v": 1,
        "sub": 123,
        "username": "alex",
        "iat": now,
        "exp": now + 60,
    }
    token = _make_token(secret, payload) + "corrupted"

    assert verify_assistant_sso_token(token, secret=secret) is None


def test_verify_assistant_sso_token_rejects_expired_token():
    secret = "super-secret"
    now = int(time.time())
    payload = {
        "v": 1,
        "sub": 123,
        "username": "alex",
        "iat": now - 120,
        "exp": now - 120,
    }
    token = _make_token(secret, payload)

    assert verify_assistant_sso_token(token, secret=secret) is None
