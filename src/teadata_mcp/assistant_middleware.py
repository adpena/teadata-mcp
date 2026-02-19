from __future__ import annotations

import json

from starlette.types import ASGIApp, Receive, Scope, Send

from .assistant_auth import (
    AssistantAuthConfig,
    authenticate_from_headers,
    extract_header,
)


def _json_response(
    *, status: int, payload: dict
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"cache-control", b"no-store"),
    ]
    return status, headers, body


def _redirect_response(
    *, location: str
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    body = b""
    headers = [
        (b"location", location.encode("utf-8")),
        (b"content-length", b"0"),
        (b"cache-control", b"no-store"),
    ]
    return 302, headers, body


class AssistantAuthMiddleware:
    def __init__(self, app: ASGIApp, *, config: AssistantAuthConfig | None = None):
        self.app = app
        self.config = config or AssistantAuthConfig.from_env()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not self.config.enforce:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if (
            path == "/healthz"
            or path.startswith("/assets/")
            or path.startswith("/static/")
            or path.startswith("/favicon")
        ):
            await self.app(scope, receive, send)
            return

        headers: list[tuple[bytes, bytes]] = list(scope.get("headers", []))
        user = authenticate_from_headers(headers, config=self.config)
        if user is None:
            is_ui_route = not (
                path.startswith("/api/")
                or path.startswith("/mcp")
                or path.startswith("/sse")
                or path.startswith("/messages")
            )

            accept = (extract_header(headers, b"accept") or "").lower()
            wants_html = "text/html" in accept or accept in {"", "*/*"}

            if is_ui_route and wants_html:
                status, response_headers, body = _redirect_response(
                    location=self.config.launch_url
                )
            else:
                status, response_headers, body = _json_response(
                    status=401,
                    payload={"detail": "Unauthorized"},
                )

            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": response_headers,
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        scope.setdefault("state", {})["assistant_user"] = user
        await self.app(scope, receive, send)
