"""Top-level package for the TEA Data MCP server scaffolding.

The module exposes convenience imports so that users and LLMs can quickly
understand the layout of the project without having to traverse the entire
package tree.  Only the light-weight components are imported here to keep
module import times predictable inside model-context hosts.
"""

from .config import ServerConfig
from .data_engine_provider import DataEngineProvider
from .query_models import QueryResult, QueryResultStatus
from .router import QueryRouter

__all__ = [
    "ServerConfig",
    "DataEngineProvider",
    "QueryResult",
    "QueryResultStatus",
    "QueryRouter",
]
