from starlette.testclient import TestClient

from teadata_mcp.sse_server import app


def test_ws_endpoint_accepts_mcp_subprotocol():
    with TestClient(app) as client:
        with client.websocket_connect("/ws", subprotocols=["mcp"]) as ws:
            # Starlette exposes the accepted subprotocol for the test session.
            assert ws.accepted_subprotocol == "mcp"


def test_ws_endpoint_accepts_without_subprotocol():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            assert ws.accepted_subprotocol in (None, "")

