import asyncio

from app.local_access import LocalAccessMiddleware


def _request(headers, app=None, path="/"):
    messages = []

    async def endpoint(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run((app or LocalAccessMiddleware(endpoint))(
        {
            "type": "http", "method": "GET", "path": path, "root_path": "",
            "query_string": b"", "http_version": "1.1", "scheme": "http",
            "server": ("localhost", 8000), "client": ("127.0.0.1", 12345),
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
        },
        receive, send,
    ))
    return messages[0]["status"]


def test_local_hosts_and_origins():
    for host in ("localhost:8000", "127.0.0.1:8000", "[::1]:8000", "backend:8000"):
        assert _request({"host": host}) == 204
        assert _request({"host": host, "origin": "http://localhost:3000"}) == 204


def test_rejects_rebinding_and_malformed_hosts():
    for host in ("evil.example", "localhost.evil.example", "user@localhost", "localhost/path", "[invalid", "localhost:bad", ""):
        assert _request({"host": host}) == 403


def test_rejects_foreign_origins_and_cross_site_requests():
    for origin in ("null", "https://evil.example", "http://localhost:9000"):
        assert _request({"host": "localhost:8000", "origin": origin}) == 403
    assert _request({"host": "localhost:8000", "sec-fetch-site": "cross-site"}) == 403


def test_boundary_wraps_all_application_surfaces():
    from app.main import app

    for path in (
        "/api/analyze", "/api/jobs", "/api/jobs/example/result",
        "/api/jobs/example/video", "/api/jobs/example/export/json",
        "/api/compare/a/b", "/static/atlas/hcp_atlas.json", "/docs", "/health",
    ):
        assert _request({"host": "evil.example"}, app, path) == 403
        assert _request(
            {"host": "localhost:8000", "origin": "https://evil.example"}, app, path
        ) == 403
    assert _request({"host": "localhost:8000"}, app, "/health") == 200
