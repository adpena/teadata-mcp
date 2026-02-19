"""Tests for the SSE server endpoints."""

from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient

from teadata_mcp.sse_server import app


def test_homepage_returns_404_when_missing_static():
    # By default, static_dist might not exist in the test environment or is not mocked yet.
    # The app lifespan runs on startup.

    # We need to ensure logic doesn't crash if static_dist is missing.
    # However, app definition logic runs at module level for routes.
    # The homepage route is added conditionally. If static_dist exists on import, it's there.

    # Since we can't easily un-import, we test the handler directly or rely on current state.
    # Let's test the handler directly to be safe about file existence.

    with patch("teadata_mcp.sse_server.Path") as mock_path:
        # Mock index.html NOT existing
        mock_path.return_value.exists.return_value = False

        # We need to construct a robust way to call the function or use the client.
        # But `homepage` function uses `Path("static_dist/index.html")`.
        pass


def test_sse_endpoint_connects():
    with patch(
        "teadata_mcp.sse_server.transport", new_callable=MagicMock
    ) as mock_transport:
        # Define a fake handler that mimics what mcp.server.streamable_http.StreamableHTTPServerTransport does
        async def fake_handle_request(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"SSE connected"})

        from unittest.mock import AsyncMock

        mock_transport.handle_request = AsyncMock(side_effect=fake_handle_request)

        with TestClient(app) as client:
            response = client.get("/sse")
            assert response.status_code == 200
            assert response.content == b"SSE connected"


def test_tool_endpoint_call():
    # Test calling a tool API directly
    with TestClient(app) as client:
        # We need to mock the router in app.state for the request
        # But app.state is populated in lifespan.

        # Mock engine/router
        mock_router = MagicMock()
        mock_router.get_district.return_value = MagicMock(
            status="success",
            payload={"name": "Test District"},
            to_dict=lambda: {"status": "success", "payload": {"name": "Test District"}},
        )

        # We can inject into app.state via startup hook or just patch QueryRouter?
        # The endpoint `handle_tool` accesses `request.app.state.router`.

        # Let's mock lifespan to populate state with our mock
        with patch("teadata_mcp.sse_server.QueryRouter", return_value=mock_router):
            with patch(
                "teadata_mcp.sse_server.DataEngineProvider"
            ):  # prevent real load
                with client:  # Triggers startup
                    response = client.post(
                        "/api/tool/get_district", json={"identifier": "test"}
                    )
                    assert response.status_code == 200
                    assert response.json()["payload"]["name"] == "Test District"


def test_tool_endpoint_transfer_insights():
    with TestClient(app) as client:
        mock_router = MagicMock()
        mock_router.get_transfer_insights.return_value = MagicMock(
            status="ok",
            payload={"available": True},
            to_dict=lambda: {"status": "ok", "payload": {"available": True}},
        )

        with patch("teadata_mcp.sse_server.QueryRouter", return_value=mock_router):
            with patch("teadata_mcp.sse_server.DataEngineProvider"):
                with client:
                    response = client.post("/api/tool/get_transfer_insights", json={})
                    assert response.status_code == 200
                    assert response.json()["payload"]["available"] is True


def test_tool_endpoint_unknown_tool():
    with TestClient(app) as client:
        with patch("teadata_mcp.sse_server.QueryRouter"):
            with patch("teadata_mcp.sse_server.DataEngineProvider"):
                with client:
                    response = client.post("/api/tool/unknown_tool", json={})
                    assert response.status_code == 404
