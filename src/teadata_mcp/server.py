"""Entry points for running the TEA Data MCP server."""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from .config import ServerConfig
from .data_engine_provider import DataEngineProvider
from .query_models import QueryResult, QueryResultStatus
from .router import QueryRouter


async def build_app(config: ServerConfig):
    """Create the MCP application object.

    The function attempts to import :mod:`modelcontextprotocol` lazily.  Doing so
    avoids imposing the dependency on users who only want to exercise the unit
    tests or experiment with the router in isolation.
    """

    try:
        from modelcontextprotocol import server as mcp_server  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised manually
        raise RuntimeError(
            "modelcontextprotocol is not installed. Install it with "
            "`pip install modelcontextprotocol` to run the MCP server."
        ) from exc

    engine_provider = DataEngineProvider(config)
    router = QueryRouter(engine_provider)

    app = mcp_server.Server("teadata-mcp")

    @app.list_tools()
    async def list_tools() -> list[Dict[str, Any]]:  # pragma: no cover - thin wrapper
        return [
            {
                "name": "get_district",
                "description": "Look up a Texas school district by name or TEA identifier.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "identifier": {"type": "string"},
                    },
                    "required": ["identifier"],
                },
            }
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "get_district":
            result = router.get_district(arguments.get("identifier", ""))
        else:
            result = QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=f"Unknown tool '{name}'.",
            )
        return result.to_dict()

    return app


async def serve(config: ServerConfig) -> None:
    """Run the MCP server using stdin/stdout transport."""

    app = await build_app(config)

    try:
        from modelcontextprotocol.adapters.stdio import StdioServerTransport  # type: ignore
    except ImportError as exc:  # pragma: no cover - manual execution path
        raise RuntimeError(
            "modelcontextprotocol.adapters.stdio is not available. Install the full "
            "Model Context Protocol tooling to run the reference server."
        ) from exc

    transport = StdioServerTransport()
    await transport.serve(app)


def run() -> None:
    """Synchronously launch the server using :func:`asyncio.run`."""

    config = ServerConfig()
    asyncio.run(serve(config))
