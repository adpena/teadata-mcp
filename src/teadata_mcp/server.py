"Entry points for running the TEA Data MCP server."
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import importlib.util
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, Iterable, TextIO

from .config import ServerConfig
from .data_engine_provider import DataEngineProvider
from .logging_config import configure_logging
from .logging_utils import new_invocation_id, summarize_arguments, summarize_payload
from .perf import finish_perf_timer, start_perf_timer
from .query_models import QueryResult, QueryResultStatus
from .router import QueryRouter
from .export_store import is_export_uri, read_export
from .widget_assets import (
    BOUNDARY_DESCRIPTION,
    BOUNDARY_TEMPLATE_URI,
    BOUNDARY_TITLE,
    EXPLORER_DESCRIPTION,
    EXPLORER_TEMPLATE_URI,
    EXPLORER_TITLE,
    WIDGET_MIME_TYPE,
    boundary_widget_meta,
    explorer_widget_meta,
    load_boundary_widget_html,
    load_explorer_widget_html,
)


async def build_app(
    config: ServerConfig, engine_provider: DataEngineProvider | None = None
):
    """Create the MCP application object."""

    try:
        from mcp.server import Server
        from mcp.server.lowlevel.helper_types import ReadResourceContents
        import mcp.types as types
    except ImportError as exc:
        raise RuntimeError(
            "mcp is not installed or cannot be imported. Install "
            "it with `uv add modelcontextprotocol`."
        ) from exc

    engine_provider = engine_provider or DataEngineProvider(config)
    router = QueryRouter(engine_provider)
    max_bytes_default = (
        config.max_response_bytes if config.max_response_bytes is not None else 24000
    )

    app = Server("teadata-mcp")
    boundary_tools = {
        "find_campuses_in_district_boundary",
        "find_charter_campuses_within_district",
        "map_campuses_within_district",
        "map_charter_campuses_within_district",
    }
    explorer_tools = {
        "search_campuses",
        "get_campus_detail",
        "get_district_detail",
        "compare_campuses",
        "get_nearby_campuses",
        "get_district",
        "get_campus_aggregates",
        "get_transfer_insights",
    }
    charter_tools = {
        "find_charter_campuses_within_district",
        "map_charter_campuses_within_district",
    }
    read_only_annotations = types.ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        openWorldHint=False,
        idempotentHint=True,
    )

    def invocation_strings(tool_name: str, arguments: Dict[str, Any]) -> tuple[str, str]:
        district = arguments.get("district_identifier") or arguments.get("identifier")
        if tool_name in boundary_tools:
            label = f"{district} boundaries" if district else "district boundaries"
            return (f"Finding campuses within {label}.", "Boundary results ready.")
        if tool_name == "search_campuses":
            return ("Searching campuses.", "Campus search ready.")
        if tool_name == "get_campus_aggregates":
            return ("Calculating aggregates.", "Aggregates ready.")
        if tool_name == "get_staffing_dashboard":
            return ("Collecting staffing metrics.", "Staffing metrics ready.")
        if tool_name == "get_district":
            return ("Fetching district details.", "District details ready.")
        if tool_name == "get_data_fields":
            return ("Inspecting available fields.", "Field list ready.")
        if tool_name == "get_campus_detail":
            return ("Fetching campus profile.", "Campus details ready.")
        if tool_name == "get_district_detail":
            return ("Fetching district summary.", "District summary ready.")
        if tool_name == "get_nearby_campuses":
            return ("Finding nearby campuses.", "Nearby campuses ready.")
        if tool_name == "compare_campuses":
            return ("Comparing campuses.", "Comparison ready.")
        if tool_name == "get_transfer_insights":
            return ("Analyzing transfer flows.", "Transfer insights ready.")
        if tool_name == "get_entity_geometry":
            return ("Loading geometry.", "Geometry ready.")
        if tool_name == "get_tooling_guide":
            return ("Loading tooling guide.", "Tooling guide ready.")
        return ("Running tool.", "Tool complete.")

    def widget_session_id(tool_name: str, arguments: Dict[str, Any]) -> str:
        status = arguments.get("status")
        if tool_name in charter_tools:
            status = "charter"
        identifiers = arguments.get("identifiers") if tool_name == "compare_campuses" else None
        payload = json.dumps(
            {
                "tool": tool_name,
                "district_identifier": arguments.get("district_identifier", ""),
                "campus_query": arguments.get("campus_query", ""),
                "status": status or "all",
                "response_profile": arguments.get("response_profile", "map"),
                "campus_list_format": arguments.get("campus_list_format", "id_name"),
                "identifier": arguments.get("identifier", ""),
                "query": arguments.get("query", ""),
                "radius_miles": arguments.get("radius_miles", ""),
                "top_sources": arguments.get("top_sources", ""),
                "top_destinations": arguments.get("top_destinations", ""),
                "min_transfer_count": arguments.get("min_transfer_count", ""),
                "neighborhood_radius_miles": arguments.get(
                    "neighborhood_radius_miles", ""
                ),
                "identifiers": sorted(identifiers) if identifiers else [],
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def build_call_meta(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        invoking, invoked = invocation_strings(tool_name, arguments)
        if tool_name in boundary_tools:
            return boundary_widget_meta(
                invoking=invoking,
                invoked=invoked,
                session_id=widget_session_id(tool_name, arguments),
            )
        if tool_name in explorer_tools:
            return explorer_widget_meta(
                invoking=invoking,
                invoked=invoked,
                session_id=widget_session_id(tool_name, arguments),
            )
        return {
            "openai/toolInvocation/invoking": invoking,
            "openai/toolInvocation/invoked": invoked,
        }

    def build_call_result(
        tool_name: str, arguments: Dict[str, Any], result: QueryResult
    ) -> types.CallToolResult:
        structured = result.to_dict()
        structured["tool"] = tool_name
        structured["arguments"] = arguments
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=result.message)],
            structuredContent=structured,
            meta=build_call_meta(tool_name, arguments),
            isError=result.status == QueryResultStatus.ERROR,
        )

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="get_district",
                description=(
                    "Look up a Texas school district by TEA number or name (wildcards like "
                    "'ALDINE*' or 'AUSTIN%' are supported). Use this to anchor district-level "
                    "questions or to supply identifiers for detail, boundary, or campus list queries. "
                    "Optionally request specific meta_fields for additional metrics. "
                    "DO NOT search the web for basic district info; this tool provides it locally. "
                    "Example: \"Find Austin ISD\" or \"Get district 227901\"."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "identifier": {"type": "string", "description": "District name or number"},
                        "meta_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of district meta keys to return (e.g., overall_rating_2025).",
                        },
                    },
                    "required": ["identifier"],
                },
                annotations=read_only_annotations,
                _meta=explorer_widget_meta(),
            ),
            types.Tool(
                name="get_data_fields",
                description=(
                    "Inspect available data fields (metrics) for a campus or district. Use this tool "
                    "to discover what specific data points are available in the local database before "
                    "searching the web. It returns a list of keys (e.g., 'campus_2025_sat_average') "
                    "that can be requested via meta_fields in other tools."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "enum": ["campus", "district"],
                            "description": "Entity type to inspect.",
                        },
                        "identifier": {
                            "type": "string",
                            "description": "Campus or district name/number.",
                        },
                    },
                    "required": ["entity_type", "identifier"],
                },
                annotations=read_only_annotations,
            ),
            types.Tool(
                name="search_campuses",
                description=(
                    "Search campuses by name/number/district with filters for status (all/charter/isd/private), "
                    "rating (A-F, NR), and grade_level (Elementary/Middle/High). Examples: query 'IDEA', 'KIPP', or 'Austin ISD' "
                    "to fetch identifiers before detail/compare/map calls. This tool returns basic info; "
                    "use get_campus_detail for full stats. Results paginate with cursor/next_cursor; "
                    "set include_total=true to receive total_matches. You can request meta_fields "
                    "to pull specific metrics without returning full meta blobs. Responses include "
                    "payload.table and payload.exports for deterministic tables and CSV/JSON export; "
                    "if payload.completeness.needs_follow_up or pagination.has_more is true, follow "
                    "next_tool_call before finalizing."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search text (name, number, district)"},
                        "status": {"type": "string", "enum": ["all", "charter", "isd", "private"], "default": "all"},
                        "rating": {"type": "string", "description": "Filter by rating (A, B, C, D, F, NR) or 'all'"},
                        "grade_level": {"type": "string", "description": "Filter by grade level (Elementary, Middle, High) or 'all'"},
                        "limit": {"type": "integer", "default": 20},
                        "meta_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of campus meta keys to include per result.",
                        },
                        "cursor": {
                            "type": "integer",
                            "default": 0,
                            "description": "Pagination cursor (number of matched campuses to skip).",
                        },
                        "include_total": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include total_matches for pagination awareness.",
                        },
                    },
                },
                annotations=read_only_annotations,
                _meta=explorer_widget_meta(),
            ),
            types.Tool(
                name="get_campus_aggregates",
                description=(
                    "Compute aggregate statistics (total enrollment, rating distribution, etc.) "
                    "for campuses matching specific filters. Use this for questions like "
                    "\"Total enrollment of all charter schools\" or \"How many A-rated campuses are there?\". "
                    "Supports the same filters as search_campuses (query, status, rating, grade_level)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search text (name, number, district)"},
                        "status": {"type": "string", "enum": ["all", "charter", "isd", "private"], "default": "all"},
                        "rating": {"type": "string", "description": "Filter by rating (A, B, C, D, F, NR) or 'all'"},
                        "grade_level": {"type": "string", "description": "Filter by grade level (Elementary, Middle, High) or 'all'"},
                    },
                },
                annotations=read_only_annotations,
                _meta=explorer_widget_meta(),
            ),
            types.Tool(
                name="get_staffing_dashboard",
                description=(
                    "Return campus-level staffing metrics for dashboard analysis, including "
                    "teacher experience, turnover rate, student-teacher ratio, enrollment, ratings, "
                    "and coordinates for mapping. Use this to compare staffing differences between "
                    "charter and traditional campuses without web search."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
                annotations=read_only_annotations,
            ),
            types.Tool(
                name="get_campus_detail",
                description=(
                    "Return a campus profile with rich data: Staffing, Class Sizes, Demographics, "
                    "Transfers Out, Location, and Ratings. DO NOT search the web for these metrics; "
                    "they are provided locally. Use `get_data_fields` to discover other available metrics "
                    "(e.g., test scores) if needed. Example: \"Show details for campus 227901001\"."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "identifier": {"type": "string", "description": "Campus name or number"},
                        "meta_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of campus meta keys to include under meta.",
                        },
                    },
                    "required": ["identifier"],
                },
                annotations=read_only_annotations,
                _meta=explorer_widget_meta(),
            ),
            types.Tool(
                name="get_transfer_insights",
                description=(
                    "Analyze outbound student transfer flows across campuses. Returns Sankey nodes/links, "
                    "map-ready flow lines, charter vs traditional shares, rating shifts, and distance "
                    "patterns. Optionally scope to a district or campus query. "
                    "Use this for transfer dynamics, school choice patterns, or charter share questions."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "district_identifier": {
                            "type": "string",
                            "description": "Optional district name or number to scope transfers.",
                        },
                        "campus_query": {
                            "type": "string",
                            "description": "Optional campus name/number filter within the scope.",
                        },
                        "top_sources": {
                            "type": "integer",
                            "default": 20,
                            "description": "Number of high-transfer source campuses to include.",
                        },
                        "top_destinations": {
                            "type": "integer",
                            "default": 3,
                            "description": "Max destinations per source for Sankey links.",
                        },
                        "min_transfer_count": {
                            "type": "integer",
                            "default": 10,
                            "description": "Minimum transfer count to include in flow links.",
                        },
                        "neighborhood_radius_miles": {
                            "type": "number",
                            "default": 5.0,
                            "description": "Radius threshold for neighborhood retention stats.",
                        },
                    },
                },
                annotations=read_only_annotations,
                _meta=explorer_widget_meta(),
            ),
            types.Tool(
                name="get_district_detail",
                description=(
                    "Return district summary plus its campuses (useful for 'show all campuses in "
                    "Houston ISD' style prompts). Includes district-wide stats. DO NOT search the web "
                    "for this info; it is provided locally. Results paginate with cursor/next_cursor "
                    "and can include total_matches when include_total=true. You can request meta_fields "
                    "for the district or campus_meta_fields for each campus. Responses include payload.table "
                    "and payload.exports for deterministic tables and CSV/JSON export; if "
                    "payload.completeness.needs_follow_up or pagination.has_more is true, follow "
                    "next_tool_call before finalizing. Example: \"List campuses in Austin ISD\"."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "identifier": {"type": "string", "description": "District name or number"},
                        "meta_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of district meta keys to include under meta.",
                        },
                        "campus_meta_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of campus meta keys to include for each campus.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 200,
                            "description": "Max campuses to return per page (set to 0 for all).",
                        },
                        "cursor": {
                            "type": "integer",
                            "default": 0,
                            "description": "Pagination cursor (number of matched campuses to skip).",
                        },
                        "include_total": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include total_matches for pagination awareness.",
                        },
                    },
                    "required": ["identifier"],
                },
                annotations=read_only_annotations,
                _meta=explorer_widget_meta(),
            ),
            types.Tool(
                name="get_nearby_campuses",
                description=(
                    "Find campuses within a radius (miles) of a campus or coordinates; returns "
                    "distance_miles plus charter/private flags so you can filter. Example: coords "
                    "(-95.36, 29.83) with radius 10 to find nearby charters; filter results by "
                    "charter/is_private in the response. Results paginate with cursor/next_cursor "
                    "and can include total_matches when include_total=true. Responses include payload.table "
                    "and payload.exports for deterministic tables and CSV/JSON export; if "
                    "payload.completeness.needs_follow_up or pagination.has_more is true, follow "
                    "next_tool_call before finalizing."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "identifier": {"type": "string", "description": "Target campus name or number to search around."},
                        "latitude": {"type": "number", "description": "Latitude (required if identifier not provided)."},
                        "longitude": {"type": "number", "description": "Longitude (required if identifier not provided)."},
                        "radius_miles": {"type": "number", "default": 5.0, "description": "Search radius in miles."},
                        "limit": {"type": "integer", "default": 50, "description": "Maximum number of results to return."},
                        "cursor": {
                            "type": "integer",
                            "default": 0,
                            "description": "Pagination cursor (number of matched campuses to skip).",
                        },
                        "include_total": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include total_matches for pagination awareness.",
                        },
                    },
                },
                annotations=read_only_annotations,
                _meta=explorer_widget_meta(),
            ),
            types.Tool(
                name="compare_campuses",
                description=(
                    "Compare 2+ campuses side-by-side on rating, enrollment, staffing, and "
                    "demographics. Use for benchmarking or 'compare these campuses' prompts after "
                    "collecting campus identifiers via search. Optionally include meta_fields for "
                    "extra comparison dimensions. Responses include payload.table and payload.exports "
                    "for deterministic tables and CSV/JSON export."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "identifiers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of campus names or numbers to compare."
                        },
                        "meta_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of campus meta keys to include under meta.",
                        },
                    },
                    "required": ["identifiers"],
                },
                annotations=read_only_annotations,
                _meta=explorer_widget_meta(),
            ),
            types.Tool(
                name="get_entity_geometry",
                description=(
                    "Fetch campus or district geometry/location data from the local teadata snapshot, "
                    "including geometry_fields to show which attributes are available. Use this for "
                    "map/boundary questions or to confirm geometry before drawing. Example: "
                    "\"What geometry fields does Austin ISD expose?\""
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "enum": ["campus", "district"],
                            "description": "Entity type to inspect.",
                        },
                        "identifier": {
                            "type": "string",
                            "description": "Campus or district name/number.",
                        },
                    },
                    "required": ["entity_type", "identifier"],
                },
                annotations=read_only_annotations,
            ),
            types.Tool(
                name="get_tooling_guide",
                description=(
                    "Return a prompt-to-tool guide with recommended tool calls for common intents. "
                    "Use this when the user asks for a map, boundary, comparison, or spatial query "
                    "and you want the canonical tool choice."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Optional filter (e.g., 'map', 'charter', 'boundary').",
                        },
                    },
                },
                annotations=read_only_annotations,
            ),
            types.Tool(
                name="find_campuses_in_district_boundary",
                description=(
                    "Spatial containment query using teadata boundary methods; returns GeoJSON "
                    "(district polygon + campus points) with overall_rating_2025 in properties. "
                    "Use for 'within Austin ISD boundaries' or 'show on a map' prompts; apply "
                    "status or campus_query filters (e.g., IDEA, KIPP). Default boundary_delivery "
                    "is 'reference' to avoid huge payloads; this returns a Census TIGERweb "
                    "download_url so ChatGPT can fetch the boundary directly. response_profile controls "
                    "payload size: 'map' returns GeoJSON only, 'list' returns campus list only, "
                    "'both' returns both. campus_list_format controls list compactness (id/id_name/full). "
                    "Responses paginate via cursor/next_cursor to avoid truncation; set include_total=true "
                    "to return total_matches. Responses include payload.table and payload.exports for "
                    "deterministic tables and CSV/JSON export when lists are returned; if "
                    "payload.completeness.needs_follow_up or pagination.has_more is true, follow "
                    "next_tool_call before finalizing. "
                    "Use campus_meta_fields to include specific meta keys without dumping full meta. "
                    "Example: \"Find campuses within Austin ISD boundaries\"."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "district_identifier": {
                            "type": "string",
                            "description": "District name or number used to locate boundaries.",
                        },
                        "campus_query": {
                            "type": "string",
                            "description": "Optional filter against campus name/number/district/charter label (e.g., IDEA).",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["all", "charter", "isd", "private"],
                            "default": "all",
                        },
                        "limit": {"type": "integer", "default": 100},
                        "include_campus_geometry": {"type": "boolean", "default": False},
                        "include_geojson": {"type": "boolean", "default": True},
                        "boundary_delivery": {
                            "type": "string",
                            "enum": ["reference", "inline", "none"],
                            "default": "reference",
                            "description": "Use 'reference' to return a Census TIGERweb download URL; 'inline' returns full boundary GeoJSON (may be large).",
                        },
                        "response_profile": {
                            "type": "string",
                            "enum": ["map", "list", "both"],
                            "default": "map",
                            "description": "Choose 'map' for GeoJSON points, 'list' for campuses only, 'both' for both.",
                        },
                        "campus_meta_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of campus meta keys to include under campuses[].meta and geojson.properties.meta.",
                        },
                        "campus_list_format": {
                            "type": "string",
                            "enum": ["full", "id", "id_name"],
                            "default": "id_name",
                            "description": "Choose list output: full summaries, campus_number only, or campus_number + name.",
                        },
                        "include_total": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include total_matches for pagination awareness.",
                        },
                        "cursor": {
                            "type": "integer",
                            "default": 0,
                            "description": "Pagination cursor (number of matched campuses to skip). Use pagination.next_cursor from prior response.",
                        },
                        "max_response_bytes": {
                            "type": "integer",
                            "default": max_bytes_default,
                            "description": "Soft cap on response size in bytes. Set to 0 to disable trimming.",
                        },
                    },
                    "required": ["district_identifier"],
                },
                annotations=read_only_annotations,
                _meta=boundary_widget_meta(),
            ),
            types.Tool(
                name="find_charter_campuses_within_district",
                description=(
                    "Shortcut for charter-only campuses within a district boundary; "
                    "returns GeoJSON for interactive maps. Example: district_identifier "
                    "'Austin ISD' with campus_query 'IDEA'. Default boundary_delivery "
                    "is 'reference' to avoid huge payloads; this returns a Census TIGERweb "
                    "download_url so ChatGPT can fetch the boundary directly. response_profile "
                    "controls payload size ('map', 'list', 'both'). campus_list_format controls "
                    "how list outputs are compacted. Responses paginate via cursor/next_cursor. "
                    "When lists are returned, payload.table and payload.exports provide deterministic "
                    "tables and CSV/JSON export; if payload.completeness.needs_follow_up is true, "
                    "follow next_tool_call before finalizing."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "district_identifier": {
                            "type": "string",
                            "description": "District name or number used to locate boundaries.",
                        },
                        "campus_query": {
                            "type": "string",
                            "description": "Optional filter against campus name/number/district/charter label (e.g., IDEA).",
                        },
                        "limit": {"type": "integer", "default": 100},
                        "include_campus_geometry": {"type": "boolean", "default": False},
                        "include_geojson": {"type": "boolean", "default": True},
                        "boundary_delivery": {
                            "type": "string",
                            "enum": ["reference", "inline", "none"],
                            "default": "reference",
                            "description": "Use 'reference' to return a Census TIGERweb download URL; 'inline' returns full boundary GeoJSON (may be large).",
                        },
                        "response_profile": {
                            "type": "string",
                            "enum": ["map", "list", "both"],
                            "default": "map",
                            "description": "Choose 'map' for GeoJSON points, 'list' for campuses only, 'both' for both.",
                        },
                        "campus_meta_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of campus meta keys to include under campuses[].meta and geojson.properties.meta.",
                        },
                        "campus_list_format": {
                            "type": "string",
                            "enum": ["full", "id", "id_name"],
                            "default": "id_name",
                            "description": "Choose list output: full summaries, campus_number only, or campus_number + name.",
                        },
                        "include_total": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include total_matches for pagination awareness.",
                        },
                        "cursor": {
                            "type": "integer",
                            "default": 0,
                            "description": "Pagination cursor (number of matched campuses to skip). Use pagination.next_cursor from prior response.",
                        },
                        "max_response_bytes": {
                            "type": "integer",
                            "default": max_bytes_default,
                            "description": "Soft cap on response size in bytes. Set to 0 to disable trimming.",
                        },
                    },
                    "required": ["district_identifier"],
                },
                annotations=read_only_annotations,
                _meta=boundary_widget_meta(),
            ),
            types.Tool(
                name="map_campuses_within_district",
                description=(
                    "Map-focused alias for within-boundary queries. Use this when the user asks to "
                    "show campuses on an interactive map; supports status filters (charter/isd/private). "
                    "Returns campus points plus a boundary_reference download_url. response_profile "
                    "defaults to 'map' for compact GeoJSON-only responses. campus_list_format controls "
                    "how list outputs are compacted. Responses paginate via cursor/next_cursor. When "
                    "lists are returned, payload.table and payload.exports provide deterministic tables "
                    "and CSV/JSON export; if payload.completeness.needs_follow_up is true, follow "
                    "next_tool_call before finalizing. Example: \"Show campuses within Austin ISD on a map\"."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "district_identifier": {
                            "type": "string",
                            "description": "District name or number used to locate boundaries.",
                        },
                        "campus_query": {
                            "type": "string",
                            "description": "Optional filter against campus name/number/district/charter label (e.g., IDEA).",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["all", "charter", "isd", "private"],
                            "default": "all",
                        },
                        "limit": {"type": "integer", "default": 100},
                        "include_campus_geometry": {"type": "boolean", "default": False},
                        "include_geojson": {"type": "boolean", "default": True},
                        "boundary_delivery": {
                            "type": "string",
                            "enum": ["reference", "inline", "none"],
                            "default": "reference",
                            "description": "Use 'reference' to return a Census TIGERweb download URL; 'inline' returns full boundary GeoJSON (may be large).",
                        },
                        "response_profile": {
                            "type": "string",
                            "enum": ["map", "list", "both"],
                            "default": "map",
                            "description": "Choose 'map' for GeoJSON points, 'list' for campuses only, 'both' for both.",
                        },
                        "campus_meta_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of campus meta keys to include under campuses[].meta and geojson.properties.meta.",
                        },
                        "campus_list_format": {
                            "type": "string",
                            "enum": ["full", "id", "id_name"],
                            "default": "id_name",
                            "description": "Choose list output: full summaries, campus_number only, or campus_number + name.",
                        },
                        "include_total": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include total_matches for pagination awareness.",
                        },
                        "cursor": {
                            "type": "integer",
                            "default": 0,
                            "description": "Pagination cursor (number of matched campuses to skip). Use pagination.next_cursor from prior response.",
                        },
                        "max_response_bytes": {
                            "type": "integer",
                            "default": max_bytes_default,
                            "description": "Soft cap on response size in bytes. Set to 0 to disable trimming.",
                        },
                    },
                    "required": ["district_identifier"],
                },
                annotations=read_only_annotations,
                _meta=boundary_widget_meta(),
            ),
            types.Tool(
                name="map_charter_campuses_within_district",
                description=(
                    "Map-focused alias for charter-only campuses within a district boundary. Use this "
                    "for prompts like \"Find all charter school campuses located within Austin ISD's "
                    "boundaries and show them on an interactive map\". response_profile defaults to "
                    "'map' for compact GeoJSON-only responses. campus_list_format controls how list "
                    "outputs are compacted. Responses paginate via cursor/next_cursor. When lists are "
                    "returned, payload.table and payload.exports provide deterministic tables and "
                    "CSV/JSON export; if payload.completeness.needs_follow_up is true, follow "
                    "next_tool_call before finalizing."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "district_identifier": {
                            "type": "string",
                            "description": "District name or number used to locate boundaries.",
                        },
                        "campus_query": {
                            "type": "string",
                            "description": "Optional filter against campus name/number/district/charter label (e.g., IDEA).",
                        },
                        "limit": {"type": "integer", "default": 100},
                        "include_campus_geometry": {"type": "boolean", "default": False},
                        "include_geojson": {"type": "boolean", "default": True},
                        "boundary_delivery": {
                            "type": "string",
                            "enum": ["reference", "inline", "none"],
                            "default": "reference",
                            "description": "Use 'reference' to return a Census TIGERweb download URL; 'inline' returns full boundary GeoJSON (may be large).",
                        },
                        "response_profile": {
                            "type": "string",
                            "enum": ["map", "list", "both"],
                            "default": "map",
                            "description": "Choose 'map' for GeoJSON points, 'list' for campuses only, 'both' for both.",
                        },
                        "campus_meta_fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of campus meta keys to include under campuses[].meta and geojson.properties.meta.",
                        },
                        "campus_list_format": {
                            "type": "string",
                            "enum": ["full", "id", "id_name"],
                            "default": "id_name",
                            "description": "Choose list output: full summaries, campus_number only, or campus_number + name.",
                        },
                        "include_total": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include total_matches for pagination awareness.",
                        },
                        "cursor": {
                            "type": "integer",
                            "default": 0,
                            "description": "Pagination cursor (number of matched campuses to skip). Use pagination.next_cursor from prior response.",
                        },
                        "max_response_bytes": {
                            "type": "integer",
                            "default": max_bytes_default,
                            "description": "Soft cap on response size in bytes. Set to 0 to disable trimming.",
                        },
                    },
                    "required": ["district_identifier"],
                },
                annotations=read_only_annotations,
                _meta=boundary_widget_meta(),
            ),
        ]

    @app.list_resources()
    async def list_resources() -> list[types.Resource]:
        return [
            types.Resource(
                name="teadata-boundary-widget",
                title=BOUNDARY_TITLE,
                uri=BOUNDARY_TEMPLATE_URI,
                description=BOUNDARY_DESCRIPTION,
                mimeType=WIDGET_MIME_TYPE,
                _meta=boundary_widget_meta(),
            ),
            types.Resource(
                name="teadata-explorer-widget",
                title=EXPLORER_TITLE,
                uri=EXPLORER_TEMPLATE_URI,
                description=EXPLORER_DESCRIPTION,
                mimeType=WIDGET_MIME_TYPE,
                _meta=explorer_widget_meta(),
            )
        ]

    @app.read_resource()
    async def read_resource(uri: str):
        resource = str(uri)
        if resource == BOUNDARY_TEMPLATE_URI:
            return [
                ReadResourceContents(
                    content=load_boundary_widget_html(),
                    mime_type=WIDGET_MIME_TYPE,
                )
            ]
        if resource == EXPLORER_TEMPLATE_URI:
            return [
                ReadResourceContents(
                    content=load_explorer_widget_html(),
                    mime_type=WIDGET_MIME_TYPE,
                )
            ]
        if is_export_uri(resource):
            entry = read_export(resource)
            if entry is None:
                return [
                    ReadResourceContents(
                        content="Export not found or expired.",
                        mime_type="text/plain",
                    )
                ]
            return [
                ReadResourceContents(
                    content=entry.content,
                    mime_type=entry.mime_type,
                )
            ]
        return [
            ReadResourceContents(
                content=f"Unknown resource: {uri}",
                mime_type="text/plain",
            )
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
        arguments = arguments or {}
        invocation_id = new_invocation_id()
        logger = logging.getLogger("teadata_mcp.tool")
        logger.info(
            "tool.start",
            extra={
                "invocation_id": invocation_id,
                "tool": name,
                "arguments": summarize_arguments(arguments),
            },
        )
        started = time.perf_counter()
        perf_timer = start_perf_timer(name, arguments, invocation_id=invocation_id)
        def dispatch_tool() -> QueryResult:
            if name == "get_district":
                return router.get_district(
                    arguments.get("identifier", ""),
                    meta_fields=arguments.get("meta_fields"),
                )
            if name == "get_data_fields":
                return router.get_data_fields(
                    entity_type=arguments.get("entity_type", ""),
                    identifier=arguments.get("identifier", ""),
                )
            if name == "search_campuses":
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
            if name == "get_campus_aggregates":
                return router.get_campus_aggregates(
                    query=arguments.get("query", ""),
                    status=arguments.get("status", "all"),
                    rating=arguments.get("rating", "all"),
                    grade_level=arguments.get("grade_level", "all"),
                )
            if name == "get_staffing_dashboard":
                return router.get_staffing_dashboard()
            if name == "get_campus_detail":
                return router.get_campus_detail(
                    arguments.get("identifier", ""),
                    meta_fields=arguments.get("meta_fields"),
                )
            if name == "get_transfer_insights":
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
            if name == "get_district_detail":
                return router.get_district_detail(
                    arguments.get("identifier", ""),
                    meta_fields=arguments.get("meta_fields"),
                    campus_meta_fields=arguments.get("campus_meta_fields"),
                    limit=arguments.get("limit", 200),
                    cursor=arguments.get("cursor"),
                    include_total=arguments.get("include_total", False),
                )
            if name == "get_nearby_campuses":
                return router.get_nearby_campuses(
                    identifier=arguments.get("identifier"),
                    latitude=arguments.get("latitude"),
                    longitude=arguments.get("longitude"),
                    radius_miles=arguments.get("radius_miles", 5.0),
                    limit=arguments.get("limit", 50),
                    cursor=arguments.get("cursor"),
                    include_total=arguments.get("include_total", False),
                )
            if name == "compare_campuses":
                return router.compare_campuses(
                    arguments.get("identifiers", []),
                    meta_fields=arguments.get("meta_fields"),
                )
            if name == "get_entity_geometry":
                return router.get_entity_geometry(
                    entity_type=arguments.get("entity_type", ""),
                    identifier=arguments.get("identifier", ""),
                )
            if name == "get_tooling_guide":
                return router.get_tooling_guide(arguments.get("topic", ""))
            if name == "find_campuses_in_district_boundary":
                return router.find_campuses_in_district_boundary(
                    district_identifier=arguments.get("district_identifier", ""),
                    campus_query=arguments.get("campus_query", ""),
                    status=arguments.get("status", "all"),
                    limit=arguments.get("limit", 100),
                    include_campus_geometry=arguments.get(
                        "include_campus_geometry", False
                    ),
                    include_geojson=arguments.get("include_geojson", True),
                    boundary_delivery=arguments.get("boundary_delivery", "reference"),
                    response_profile=arguments.get("response_profile", "map"),
                    campus_meta_fields=arguments.get("campus_meta_fields"),
                    campus_list_format=arguments.get("campus_list_format", "id_name"),
                    include_total=arguments.get("include_total", False),
                    cursor=arguments.get("cursor"),
                    max_response_bytes=arguments.get("max_response_bytes"),
                )
            if name == "find_charter_campuses_within_district":
                return router.find_campuses_in_district_boundary(
                    district_identifier=arguments.get("district_identifier", ""),
                    campus_query=arguments.get("campus_query", ""),
                    status="charter",
                    limit=arguments.get("limit", 100),
                    include_campus_geometry=arguments.get(
                        "include_campus_geometry", False
                    ),
                    include_geojson=arguments.get("include_geojson", True),
                    boundary_delivery=arguments.get("boundary_delivery", "reference"),
                    response_profile=arguments.get("response_profile", "map"),
                    campus_meta_fields=arguments.get("campus_meta_fields"),
                    campus_list_format=arguments.get("campus_list_format", "id_name"),
                    include_total=arguments.get("include_total", False),
                    cursor=arguments.get("cursor"),
                    max_response_bytes=arguments.get("max_response_bytes"),
                )
            if name == "map_campuses_within_district":
                return router.find_campuses_in_district_boundary(
                    district_identifier=arguments.get("district_identifier", ""),
                    campus_query=arguments.get("campus_query", ""),
                    status=arguments.get("status", "all"),
                    limit=arguments.get("limit", 100),
                    include_campus_geometry=arguments.get(
                        "include_campus_geometry", False
                    ),
                    include_geojson=arguments.get("include_geojson", True),
                    boundary_delivery=arguments.get("boundary_delivery", "reference"),
                    response_profile=arguments.get("response_profile", "map"),
                    campus_meta_fields=arguments.get("campus_meta_fields"),
                    campus_list_format=arguments.get("campus_list_format", "id_name"),
                    include_total=arguments.get("include_total", False),
                    cursor=arguments.get("cursor"),
                    max_response_bytes=arguments.get("max_response_bytes"),
                )
            if name == "map_charter_campuses_within_district":
                return router.find_campuses_in_district_boundary(
                    district_identifier=arguments.get("district_identifier", ""),
                    campus_query=arguments.get("campus_query", ""),
                    status="charter",
                    limit=arguments.get("limit", 100),
                    include_campus_geometry=arguments.get(
                        "include_campus_geometry", False
                    ),
                    include_geojson=arguments.get("include_geojson", True),
                    boundary_delivery=arguments.get("boundary_delivery", "reference"),
                    response_profile=arguments.get("response_profile", "map"),
                    campus_meta_fields=arguments.get("campus_meta_fields"),
                    campus_list_format=arguments.get("campus_list_format", "id_name"),
                    include_total=arguments.get("include_total", False),
                    cursor=arguments.get("cursor"),
                    max_response_bytes=arguments.get("max_response_bytes"),
                )
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=f"Unknown tool '{name}'.",
            )

        try:
            result = await asyncio.to_thread(dispatch_tool)
        except Exception:
            logger.exception(
                "tool.dispatch_failed",
                extra={"invocation_id": invocation_id, "tool": name},
            )
            result = QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Tool '{name}' failed unexpectedly.",
            )

        finish_perf_timer(
            perf_timer,
            payload=result.payload,
            status=result.status.value if hasattr(result.status, "value") else str(result.status),
        )
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "tool.end",
            extra={
                "invocation_id": invocation_id,
                "tool": name,
                "status": result.status.value
                if hasattr(result.status, "value")
                else str(result.status),
                "ms": round(duration_ms, 1),
                "payload": summarize_payload(result.payload),
            },
        )
        return build_call_result(name, arguments, result)

    return app


async def serve(config: ServerConfig) -> None:
    """Run the MCP server using stdin/stdout transport."""

    app = await build_app(config)

    try:
        from mcp.server.stdio import stdio_server
    except ImportError as exc:
        raise RuntimeError(
            "mcp.server.stdio is not available."
        ) from exc

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


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
        "mcp",
        stream=stream,
        missing_hint=[
            "Reinstall the package with `uv add modelcontextprotocol`.",
        ],
    ):
        ok = False

    if not _diagnose_dependency(
        "mcp.server.stdio",
        stream=stream,
        missing_hint=[
            "The stdio transport ships with the SDK.",
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

    configure_logging()

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
