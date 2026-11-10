"""Minimal browser security headers for the public API and interactive docs."""
from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send


_ALWAYS_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
)
_HSTS_HEADER = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")


class SecurityHeadersMiddleware:
    """Pure ASGI middleware; preserves streaming and adds headers on error responses too."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = {
            name.lower(): value
            for name, value in scope.get("headers", [])
        }
        forwarded_proto = request_headers.get(b"x-forwarded-proto", b"")
        forwarded_proto = forwarded_proto.split(b",", 1)[0].strip().lower()
        is_https = scope.get("scheme") == "https" or forwarded_proto == b"https"
        configured_headers = _ALWAYS_HEADERS + ((_HSTS_HEADER,) if is_https else ())

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {name.lower() for name, _ in headers}
                for name, value in configured_headers:
                    if name not in existing:
                        headers.append((name, value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
