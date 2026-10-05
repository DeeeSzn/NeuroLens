"""Browser access boundary for a loopback-bound, single-user installation."""

import logging
from urllib.parse import urlsplit

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "backend"}
LOCAL_ORIGINS = {
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1", "[::1]")
    for port in (3000, 8000)
}


class LocalAccessMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope["headers"]
        }
        host = headers.get("host", "")
        try:
            parsed = urlsplit(f"http://{host}")
            parsed.port  # Validate the port even though host checks use the name.
            host_ok = (
                bool(host)
                and parsed.hostname in LOCAL_HOSTS
                and parsed.username is None
                and parsed.password is None
                and parsed.path == ""
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            host_ok = False
        origin = headers.get("origin")
        if (
            not host_ok
            or (origin is not None and origin not in LOCAL_ORIGINS)
            or headers.get("sec-fetch-site") == "cross-site"
        ):
            logger.warning("Rejected non-local request")
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                await PlainTextResponse(
                    "This instance only accepts local browser requests.", status_code=403
                )(scope, receive, send)
            return
        await self.app(scope, receive, send)
