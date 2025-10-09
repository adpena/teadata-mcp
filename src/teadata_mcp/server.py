"""Entry points for running the TEA Data MCP server."""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import importlib.util
import os
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, TextIO

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
            "modelcontextprotocol is not installed or cannot be imported. Install "
            "it with `python -m pip install modelcontextprotocol` using the same "
            "interpreter you use to launch the server. If the module is still "
            "unavailable, install the upstream SDK directly from GitHub with "
            "`python -m pip install --upgrade 'modelcontextprotocol @ git+https://github.com/modelcontextprotocol/python-sdk.git'`."
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


def _format_check(prefix: str, message: str) -> str:
    return f"{prefix} {message}"


def _diagnose_dependency(
    module: str,
    *,
    stream: TextIO,
    missing_hint: Iterable[str] | None = None,
) -> bool:
    """Inspect a dependency and report whether it is importable."""

    spec = importlib.util.find_spec(module)
    if spec is None:
        hint = "\n".join(missing_hint or ())
        stream.write(
            _format_check(
                "✖",
                f"Could not locate '{module}' on sys.path."
                + (f"\n{hint}" if hint else ""),
            )
            + "\n",
        )
        return False

    try:
        version = importlib.metadata.version(module.split(".")[0])
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"

    location = spec.origin or getattr(spec.loader, "path", "unknown location")
    stream.write(
        _format_check(
            "✓",
            f"Found '{module}' (version {version}) at {location}",
        )
        + "\n",
    )
    return True


def diagnose_environment(stream: TextIO | None = None) -> bool:
    """Print diagnostics that help debug local environment issues."""

    stream = stream or sys.stdout
    ok = True

    if not _diagnose_dependency(
        "modelcontextprotocol",
        stream=stream,
        missing_hint=[
            "Reinstall the package with `python -m pip install -e '.[dev]'`",
            "or `uv pip install -e '.[dev]'` in the same environment.",
            "If the module is still missing, install the SDK from GitHub with",
            "`python -m pip install --upgrade 'modelcontextprotocol @ git+https://github.com/modelcontextprotocol/python-sdk.git'`.",
        ],
    ):
        ok = False

    if not _diagnose_dependency(
        "modelcontextprotocol.adapters.stdio",
        stream=stream,
        missing_hint=[
            "The stdio transport ships with the full SDK.",
            "Confirm that the same interpreter installs and runs the package.",
        ],
    ):
        ok = False

    snapshot = os.environ.get("TEADATA_SNAPSHOT")
    if snapshot:
        snapshot_path = Path(snapshot)
        if snapshot_path.exists():
            stream.write(
                _format_check(
                    "✓",
                    f"TEADATA_SNAPSHOT points to {snapshot_path.resolve()}",
                )
                + "\n",
            )
        else:
            stream.write(
                _format_check(
                    "✖",
                    f"TEADATA_SNAPSHOT points to missing path: {snapshot_path}",
                )
                + "\n",
            )
            ok = False
    else:
        stream.write(
            _format_check(
                "•",
                "TEADATA_SNAPSHOT is not set; default snapshot search will be used.",
            )
            + "\n",
        )

    return ok


def run(argv: list[str] | None = None) -> None:
    """Synchronously launch the server or run diagnostics."""

    parser = argparse.ArgumentParser(description="TEA Data MCP server entry point")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Print environment diagnostics instead of launching the server.",
    )
    args = parser.parse_args(argv)

    if args.diagnose:
        success = diagnose_environment()
        raise SystemExit(0 if success else 1)

    config = ServerConfig()
    asyncio.run(serve(config))
