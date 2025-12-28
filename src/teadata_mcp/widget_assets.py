"""Widget asset helpers for Apps SDK UI rendering."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

BOUNDARY_TEMPLATE_URI = "ui://widget/teadata-boundary.html"
EXPLORER_TEMPLATE_URI = "ui://widget/teadata-explorer.html"
WIDGET_MIME_TYPE = "text/html+skybridge"
BOUNDARY_TITLE = "TEA Boundary Viewer"
BOUNDARY_DESCRIPTION = "Interactive map + table for campus boundary results."
EXPLORER_TITLE = "TEA Data Explorer"
EXPLORER_DESCRIPTION = "Search, compare, and inspect campus + district details."

_ASSETS_DIR = Path(__file__).resolve().parent / "widget_assets"


@lru_cache(maxsize=None)
def load_boundary_widget_html() -> str:
    html_path = _ASSETS_DIR / "teadata-boundary.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")

    raise FileNotFoundError(
        f"Boundary widget HTML not found at {html_path}. "
        "Ensure widget assets are present in src/teadata_mcp/widget_assets."
    )


@lru_cache(maxsize=None)
def load_explorer_widget_html() -> str:
    html_path = _ASSETS_DIR / "teadata-explorer.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")

    raise FileNotFoundError(
        f"Explorer widget HTML not found at {html_path}. "
        "Ensure widget assets are present in src/teadata_mcp/widget_assets."
    )


def boundary_widget_meta(
    *,
    invoking: Optional[str] = None,
    invoked: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "openai/outputTemplate": BOUNDARY_TEMPLATE_URI,
        "openai/widgetAccessible": True,
    }
    if invoking:
        meta["openai/toolInvocation/invoking"] = invoking
    if invoked:
        meta["openai/toolInvocation/invoked"] = invoked
    if session_id:
        meta["openai/widgetSessionId"] = session_id
    return meta


def explorer_widget_meta(
    *,
    invoking: Optional[str] = None,
    invoked: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "openai/outputTemplate": EXPLORER_TEMPLATE_URI,
        "openai/widgetAccessible": True,
    }
    if invoking:
        meta["openai/toolInvocation/invoking"] = invoking
    if invoked:
        meta["openai/toolInvocation/invoked"] = invoked
    if session_id:
        meta["openai/widgetSessionId"] = session_id
    return meta
