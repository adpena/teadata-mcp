"""
Streamable HTTP Server Entry Point

This module provides the ASGI application for running the MCP server over Streamable HTTP.
It is the modern March 2025 standard for MCP.
"""

import os
import json
import uuid
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import time

from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.server.websocket import websocket_server
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response, FileResponse, JSONResponse
from starlette.routing import Route, Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import ServerConfig
from .logging_config import configure_logging
from .logging_utils import new_invocation_id, summarize_arguments, summarize_payload
from .server import build_app
from .perf import finish_perf_timer, start_perf_timer
from .router import QueryRouter
from .data_engine_provider import DataEngineProvider
from .assistant_auth import AssistantAuthConfig, authenticate_from_headers
from .assistant_middleware import AssistantAuthMiddleware

logger = logging.getLogger(__name__)

# Initialize the transport globally
transport = StreamableHTTPServerTransport(mcp_session_id=str(uuid.uuid4()))


# Setup rate limiter
def _rate_limit_key(request: Request) -> str:
    user = getattr(request.state, "assistant_user", None)
    sub = user.get("sub") if isinstance(user, dict) else None
    if isinstance(sub, int) and sub:
        return f"assistant:{sub}"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)


@asynccontextmanager
async def lifespan(app: Starlette):
    """
    Handles startup and shutdown of the MCP background processing task.
    """
    configure_logging()
    config = ServerConfig()
    engine_provider = DataEngineProvider(config)
    router = QueryRouter(engine_provider)
    app.state.config = config
    app.state.engine_provider = engine_provider
    app.state.router = router

    warm = os.getenv("TEADATA_WARM_ENGINE_ON_STARTUP", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if warm:
        logger.info("Warming data engine at startup")
        started = time.perf_counter()
        try:
            await asyncio.to_thread(engine_provider.ensure_loaded)
        except Exception:
            logger.exception("Data engine warm-up failed")
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info("Data engine warm-up complete", extra={"ms": round(duration_ms, 1)})

    mcp_app = await build_app(config, engine_provider=engine_provider)

    async def run_mcp_logic():
        try:
            async with transport.connect() as streams:
                await mcp_app.run(
                    streams[0], streams[1], mcp_app.create_initialization_options()
                )
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("MCP background task crashed")

    task = asyncio.create_task(run_mcp_logic())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def handle_mcp_request(scope, receive, send):
    """
    Raw ASGI handler for Streamable HTTP.
    """

    async def cloudflare_optimized_send(message):
        if message["type"] == "http.response.start":
            headers = list(message.get("headers", []))
            headers.append((b"x-accel-buffering", b"no"))
            headers.append((b"cache-control", b"no-cache"))
            message["headers"] = headers
        await send(message)

    # SHIM: The MCP Transport is very strict about headers.
    # We force them here to ensure compatibility with ChatGPT's connector probes.
    new_headers = []
    has_accept = False
    has_content_type = False

    for k, v in scope.get("headers", []):
        kl = k.lower()
        if kl == b"accept":
            # Force the specific combination the SDK looks for
            new_headers.append((k, b"application/json, text/event-stream"))
            has_accept = True
        elif kl == b"content-type":
            new_headers.append((k, b"application/json"))
            has_content_type = True
        else:
            new_headers.append((k, v))

    if not has_accept:
        new_headers.append((b"accept", b"application/json, text/event-stream"))
    if not has_content_type:
        new_headers.append((b"content-type", b"application/json"))

    scope["headers"] = new_headers

    await transport.handle_request(scope, receive, cloudflare_optimized_send)


class MCPRequestHandler:
    async def __call__(self, scope, receive, send):
        await handle_mcp_request(scope, receive, send)


def _parse_offered_subprotocols(headers: list[tuple[bytes, bytes]]) -> set[str]:
    offered: set[str] = set()
    for k, v in headers:
        if k.lower() != b"sec-websocket-protocol":
            continue
        try:
            raw = v.decode("latin-1")
        except Exception:
            raw = ""
        for item in raw.split(","):
            token = item.strip()
            if token:
                offered.add(token)
    return offered


class MCPWebSocketHandler:
    async def __call__(self, scope, receive, send):
        headers: list[tuple[bytes, bytes]] = list(scope.get("headers", []))

        auth_config = AssistantAuthConfig.from_env()
        if auth_config.enforce:
            user = authenticate_from_headers(headers, config=auth_config)
            if user is None:
                # Deny quickly without starting the MCP runtime.
                # Some ASGI servers expect the connect event to be consumed first.
                try:
                    msg = await receive()
                    if msg.get("type") != "websocket.connect":
                        pass
                except Exception:
                    pass
                await send({"type": "websocket.close", "code": 4401, "reason": ""})
                return

        offered = _parse_offered_subprotocols(headers)
        allow_mcp_subprotocol = "mcp" in {p.lower() for p in offered} if offered else False

        async def send_with_subprotocol_shim(message):
            # The upstream transport always tries to accept with subprotocol="mcp".
            # Only echo it back if the client actually offered it.
            if message.get("type") == "websocket.accept" and not allow_mcp_subprotocol:
                message = dict(message)
                message.pop("subprotocol", None)
            await send(message)

        starlette_app = scope.get("app")
        config = (
            starlette_app.state.config
            if starlette_app is not None and hasattr(starlette_app.state, "config")
            else ServerConfig()
        )
        engine_provider = (
            starlette_app.state.engine_provider
            if starlette_app is not None and hasattr(starlette_app.state, "engine_provider")
            else None
        )

        client = scope.get("client")
        client_addr = f"{client[0]}:{client[1]}" if client else "unknown"
        logger.info("ws.connect", extra={"client": client_addr})

        mcp_app = await build_app(config, engine_provider=engine_provider)
        try:
            async with websocket_server(scope, receive, send_with_subprotocol_shim) as streams:
                await mcp_app.run(
                    streams[0], streams[1], mcp_app.create_initialization_options()
                )
        except Exception:
            # Disconnects may bubble up differently depending on server/runtime.
            logger.exception("ws.session_failed", extra={"client": client_addr})
            raise
        finally:
            logger.info("ws.disconnect", extra={"client": client_addr})


@limiter.limit("100/minute")
async def handle_tool(request: Request):
    tool_name = request.path_params["tool_name"]
    try:
        arguments = await request.json()
    except Exception:
        arguments = {}

    router = (
        request.app.state.router
        if hasattr(request.app, "state") and hasattr(request.app.state, "router")
        else QueryRouter(DataEngineProvider(ServerConfig()))
    )
    invocation_id = new_invocation_id()
    tool_logger = logging.getLogger("teadata_mcp.tool")
    tool_logger.info(
        "tool.start",
        extra={
            "invocation_id": invocation_id,
            "tool": tool_name,
            "arguments": summarize_arguments(arguments),
            "path": str(request.url.path),
        },
    )
    started = time.perf_counter()
    perf_timer = start_perf_timer(tool_name, arguments, invocation_id=invocation_id)

    def dispatch_tool():
        if tool_name == "get_district":
            return router.get_district(
                arguments.get("identifier", ""),
                meta_fields=arguments.get("meta_fields"),
            )
        if tool_name == "search_campuses":
            return router.search_campuses(
                query=arguments.get("query", ""),
                status=arguments.get("status", "all"),
                rating=arguments.get("rating", "all"),
                grade_level=arguments.get("grade_level", "all"),
                limit=arguments.get("limit", 20),
                meta_fields=arguments.get("meta_fields"),
                cursor=arguments.get("cursor"),
                include_total=arguments.get("include_total", False),
            )
        if tool_name == "get_campus_detail":
            return router.get_campus_detail(
                arguments.get("identifier", ""),
                meta_fields=arguments.get("meta_fields"),
            )
        if tool_name == "get_transfer_insights":
            return router.get_transfer_insights(
                district_identifier=arguments.get("district_identifier"),
                campus_query=arguments.get("campus_query", ""),
                top_sources=arguments.get("top_sources", 20),
                top_destinations=arguments.get("top_destinations", 3),
                min_transfer_count=arguments.get("min_transfer_count", 10),
                neighborhood_radius_miles=arguments.get(
                    "neighborhood_radius_miles", 5.0
                ),
            )
        if tool_name == "get_staffing_dashboard":
            return router.get_staffing_dashboard()
        if tool_name == "get_district_detail":
            return router.get_district_detail(
                arguments.get("identifier", ""),
                meta_fields=arguments.get("meta_fields"),
                campus_meta_fields=arguments.get("campus_meta_fields"),
                limit=arguments.get("limit", 200),
                cursor=arguments.get("cursor"),
                include_total=arguments.get("include_total", False),
            )
        if tool_name == "get_nearby_campuses":
            return router.get_nearby_campuses(
                identifier=arguments.get("identifier"),
                latitude=arguments.get("latitude"),
                longitude=arguments.get("longitude"),
                radius_miles=arguments.get("radius_miles", 5.0),
                limit=arguments.get("limit", 50),
                cursor=arguments.get("cursor"),
                include_total=arguments.get("include_total", False),
            )
        if tool_name == "compare_campuses":
            return router.compare_campuses(
                arguments.get("identifiers", []),
                meta_fields=arguments.get("meta_fields"),
            )
        if tool_name == "get_entity_geometry":
            return router.get_entity_geometry(
                entity_type=arguments.get("entity_type", ""),
                identifier=arguments.get("identifier", ""),
            )
        if tool_name == "get_tooling_guide":
            return router.get_tooling_guide(arguments.get("topic", ""))
        if tool_name == "find_campuses_in_district_boundary":
            return router.find_campuses_in_district_boundary(
                district_identifier=arguments.get("district_identifier", ""),
                campus_query=arguments.get("campus_query", ""),
                status=arguments.get("status", "all"),
                limit=arguments.get("limit", 100),
                include_campus_geometry=arguments.get("include_campus_geometry", False),
                include_geojson=arguments.get("include_geojson", True),
                boundary_delivery=arguments.get("boundary_delivery", "reference"),
                response_profile=arguments.get("response_profile", "map"),
                campus_meta_fields=arguments.get("campus_meta_fields"),
                campus_list_format=arguments.get("campus_list_format", "id_name"),
                include_total=arguments.get("include_total", False),
                cursor=arguments.get("cursor"),
                max_response_bytes=arguments.get("max_response_bytes"),
            )
        if tool_name == "find_charter_campuses_within_district":
            return router.find_campuses_in_district_boundary(
                district_identifier=arguments.get("district_identifier", ""),
                campus_query=arguments.get("campus_query", ""),
                status="charter",
                limit=arguments.get("limit", 100),
                include_campus_geometry=arguments.get("include_campus_geometry", False),
                include_geojson=arguments.get("include_geojson", True),
                boundary_delivery=arguments.get("boundary_delivery", "reference"),
                response_profile=arguments.get("response_profile", "map"),
                campus_meta_fields=arguments.get("campus_meta_fields"),
                campus_list_format=arguments.get("campus_list_format", "id_name"),
                include_total=arguments.get("include_total", False),
                cursor=arguments.get("cursor"),
                max_response_bytes=arguments.get("max_response_bytes"),
            )
        if tool_name == "map_campuses_within_district":
            return router.find_campuses_in_district_boundary(
                district_identifier=arguments.get("district_identifier", ""),
                campus_query=arguments.get("campus_query", ""),
                status=arguments.get("status", "all"),
                limit=arguments.get("limit", 100),
                include_campus_geometry=arguments.get("include_campus_geometry", False),
                include_geojson=arguments.get("include_geojson", True),
                boundary_delivery=arguments.get("boundary_delivery", "reference"),
                response_profile=arguments.get("response_profile", "map"),
                campus_meta_fields=arguments.get("campus_meta_fields"),
                campus_list_format=arguments.get("campus_list_format", "id_name"),
                include_total=arguments.get("include_total", False),
                cursor=arguments.get("cursor"),
                max_response_bytes=arguments.get("max_response_bytes"),
            )
        if tool_name == "map_charter_campuses_within_district":
            return router.find_campuses_in_district_boundary(
                district_identifier=arguments.get("district_identifier", ""),
                campus_query=arguments.get("campus_query", ""),
                status="charter",
                limit=arguments.get("limit", 100),
                include_campus_geometry=arguments.get("include_campus_geometry", False),
                include_geojson=arguments.get("include_geojson", True),
                boundary_delivery=arguments.get("boundary_delivery", "reference"),
                response_profile=arguments.get("response_profile", "map"),
                campus_meta_fields=arguments.get("campus_meta_fields"),
                campus_list_format=arguments.get("campus_list_format", "id_name"),
                include_total=arguments.get("include_total", False),
                cursor=arguments.get("cursor"),
                max_response_bytes=arguments.get("max_response_bytes"),
            )
        return None

    try:
        result = await asyncio.to_thread(dispatch_tool)
    except Exception:
        tool_logger.exception(
            "tool.dispatch_failed",
            extra={"invocation_id": invocation_id, "tool": tool_name},
        )
        result = None

    if result is None:
        finish_perf_timer(perf_timer, payload=None, status="unknown")
        duration_ms = (time.perf_counter() - started) * 1000
        tool_logger.info(
            "tool.end",
            extra={
                "invocation_id": invocation_id,
                "tool": tool_name,
                "status": "unknown",
                "ms": round(duration_ms, 1),
            },
        )
        return Response(f"Unknown tool {tool_name}", status_code=404)

    finish_perf_timer(
        perf_timer,
        payload=result.payload,
        status=result.status.value
        if hasattr(result.status, "value")
        else str(result.status),
    )
    duration_ms = (time.perf_counter() - started) * 1000
    tool_logger.info(
        "tool.end",
        extra={
            "invocation_id": invocation_id,
            "tool": tool_name,
            "status": result.status.value
            if hasattr(result.status, "value")
            else str(result.status),
            "ms": round(duration_ms, 1),
            "payload": summarize_payload(result.payload),
        },
    )
    return Response(
        content=json.dumps(result.to_dict(), separators=(",", ":")),
        media_type="application/json",
    )


async def healthz(request: Request):
    return JSONResponse({"ok": True})


async def homepage(request):
    index_file = Path("static_dist/index.html")
    if not index_file.exists():
        return Response("index.html not found in static_dist/", status_code=404)
    return FileResponse(index_file)


# We use explicit Route objects with the ASGI app to ensure Starlette
# passes the correct methods (GET, POST, DELETE) through to handle_mcp_request.
_mcp_handler = MCPRequestHandler()
_ws_handler = MCPWebSocketHandler()
routes = [
    Route("/healthz", endpoint=healthz, methods=["GET"]),
    Route("/mcp", endpoint=_mcp_handler, methods=["GET", "POST", "DELETE"]),
    Route("/sse", endpoint=_mcp_handler, methods=["GET", "POST"]),
    Route("/messages", endpoint=_mcp_handler, methods=["POST"]),
    WebSocketRoute("/ws", endpoint=_ws_handler),
    Route("/api/tool/{tool_name}", endpoint=handle_tool, methods=["POST"]),
]

static_dir = Path("static_dist")
if static_dir.exists():
    routes.append(
        Mount("/assets", app=StaticFiles(directory="static_dist/assets"), name="assets")
    )
    routes.append(Route("/", endpoint=homepage))
    routes.append(Route("/{path:path}", endpoint=homepage))

app = Starlette(
    routes=routes,
    debug=os.getenv("TEADATA_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    or os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes", "on"},
    lifespan=lifespan,
    middleware=[Middleware(AssistantAuthMiddleware)],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
