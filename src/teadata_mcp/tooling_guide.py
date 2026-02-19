"""Centralized prompt-to-tool guidance for MCP clients.

Update the TOOLING_GUIDE list when new prompt patterns show up in logs.
Keep entries short and action-oriented so models can match them quickly.
"""

from __future__ import annotations

from typing import Any, Dict, List


TOOLING_GUIDE: List[Dict[str, Any]] = [
    {
        "pattern": "Find campuses within <district> boundaries (map)",
        "intent": "map_within_boundary",
        "tool": "map_campuses_within_district",
        "recommended_args": {
            "district_identifier": "<district name or number>",
            "status": "all",
            "boundary_delivery": "reference",
            "response_profile": "map",
            "campus_list_format": "id_name",
        },
        "notes": [
            "Use boundary_reference.download_url to fetch district GeoJSON (no web search).",
            "Use payload.geojson.features for campus markers.",
            "Add campus_meta_fields to include extra metrics for styling.",
            "If pagination.next_cursor is present, call again with cursor=next_cursor.",
            "campus_list_format id_name returns campus_number + name; use campus_number with get_campus_detail.",
            "If next_tool_call is present, follow it for the next page.",
            "If completeness.needs_follow_up is true, follow next_tool_call before finalizing results.",
        ],
    },
    {
        "pattern": "Find charter campuses within <district> boundaries (map)",
        "intent": "map_within_boundary_charter",
        "tool": "map_charter_campuses_within_district",
        "recommended_args": {
            "district_identifier": "<district name or number>",
            "campus_query": "<optional network filter e.g., IDEA>",
            "boundary_delivery": "reference",
            "response_profile": "map",
            "campus_list_format": "id_name",
        },
        "notes": [
            "Markers can be styled by properties.charter and properties.overall_rating_2025.",
            "Add campus_meta_fields if you need additional attributes for styling.",
            "Use boundary_reference.download_url for district boundaries (no web search).",
            "If pagination.next_cursor is present, call again with cursor=next_cursor.",
            "campus_list_format id_name returns campus_number + name; use campus_number with get_campus_detail.",
            "If next_tool_call is present, follow it for the next page.",
            "If completeness.needs_follow_up is true, follow next_tool_call before finalizing results.",
        ],
    },
    {
        "pattern": "List charter campuses within <district> boundaries (table, no map)",
        "intent": "list_within_boundary_charter",
        "tool": "find_charter_campuses_within_district",
        "recommended_args": {
            "district_identifier": "<district name or number>",
            "campus_query": "<optional network filter e.g., IDEA>",
            "boundary_delivery": "reference",
            "response_profile": "list",
            "campus_list_format": "full",
            "include_total": True,
        },
        "notes": [
            "Use campus_list_format='full' to include overall_rating_2025 in the list.",
            "If pagination.next_cursor or next_tool_call is present, call again with cursor=next_cursor.",
            "If response_trimmed.applied is true, follow next_tool_call or raise max_response_bytes.",
            "Set include_total=true to show total_matches and progress.",
            "Use payload.table and payload.exports for deterministic tables and CSV/JSON exports.",
        ],
    },
    {
        "pattern": "Get district boundary geometry",
        "intent": "district_geometry",
        "tool": "get_entity_geometry",
        "recommended_args": {
            "entity_type": "district",
            "identifier": "<district name or number>",
        },
        "notes": [
            "Use geometry_fields to inspect available attributes.",
        ],
    },
    {
        "pattern": "Check available data fields / What metrics do you have?",
        "intent": "inspect_data_fields",
        "tool": "get_data_fields",
        "recommended_args": {
            "entity_type": "campus",
            "identifier": "<campus name or number>",
        },
        "notes": [
            "Returns a list of all available keys in the database.",
            "Use this BEFORE searching the web for specific metrics like test scores or finance.",
        ],
    },
    {
        "pattern": "Inspect campus or district fields / request specific metrics",
        "intent": "inspect_fields",
        "tool": "get_campus_detail",
        "recommended_args": {
            "identifier": "<campus name or number>",
            "meta_fields": [
                "overall_rating_2025",
                "campus_2025_staff_teacher_student_ratio",
            ],
        },
        "notes": [
            "Full meta blobs are intentionally omitted; request only the keys you need.",
            "If a key is missing, it will be absent from meta; retry with different keys.",
            "For district-wide lists, use get_district_detail with campus_meta_fields.",
        ],
    },
    {
        "pattern": "Search campuses by name or district",
        "intent": "campus_search",
        "tool": "search_campuses",
        "recommended_args": {
            "query": "<campus or district name>",
            "status": "all",
            "limit": 20,
        },
        "notes": [
            "Use pagination.next_cursor or next_tool_call when more results are available.",
            "Set include_total=true if you need total_matches.",
            "If completeness.needs_follow_up is true, follow next_tool_call before finalizing results.",
            "Use payload.table and payload.exports for deterministic tables and CSV/JSON exports.",
        ],
    },
    {
        "pattern": "Campus profile or detailed stats",
        "intent": "campus_detail",
        "tool": "get_campus_detail",
        "recommended_args": {
            "identifier": "<campus name or number>",
        },
    },
    {
        "pattern": "Compare two or more campuses",
        "intent": "campus_compare",
        "tool": "compare_campuses",
        "recommended_args": {
            "identifiers": ["<campus number 1>", "<campus number 2>"],
        },
    },
    {
        "pattern": "Find campuses near coordinates or a campus",
        "intent": "nearby_campuses",
        "tool": "get_nearby_campuses",
        "recommended_args": {
            "identifier": "<campus name or number>",
            "radius_miles": 5.0,
        },
        "notes": [
            "Use pagination.next_cursor or next_tool_call when more nearby results are available.",
            "Set include_total=true if you need total_matches.",
            "If completeness.needs_follow_up is true, follow next_tool_call before finalizing results.",
            "Use payload.table and payload.exports for deterministic tables and CSV/JSON exports.",
        ],
    },
    {
        "pattern": "Transfer flows / school choice / where students transfer",
        "intent": "transfer_insights",
        "tool": "get_transfer_insights",
        "recommended_args": {
            "district_identifier": "<optional district name or number>",
            "campus_query": "<optional campus filter>",
            "top_sources": 20,
            "top_destinations": 3,
            "min_transfer_count": 10,
            "neighborhood_radius_miles": 5.0,
        },
        "notes": [
            "Returns Sankey-ready nodes/links plus map flows for primary destinations.",
            "Includes charter vs traditional shares, rating shift counts, and distance patterns.",
            "Use district_identifier to keep payloads focused and faster.",
        ],
    },
]


def get_tooling_guide(topic: str | None = None) -> Dict[str, Any]:
    """Return the tooling guide; optionally filter by a topic substring."""
    topic_norm = (topic or "").strip().lower()
    if not topic_norm:
        items = TOOLING_GUIDE
    else:
        items = [
            entry
            for entry in TOOLING_GUIDE
            if topic_norm in entry.get("pattern", "").lower()
            or topic_norm in entry.get("intent", "").lower()
            or topic_norm in entry.get("tool", "").lower()
        ]
    return {
        "version": 1,
        "scope": "prompt_to_tool",
        "entries": items,
        "update_instructions": "Edit src/teadata_mcp/tooling_guide.py to add new patterns.",
    }
