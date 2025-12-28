"""Configuration helpers for the TEA Data MCP server.

The configuration layer is intentionally explicit so that automated clients
(such as LLMs) can inspect each field and reason about what values are
required to stand up a server instance.  Every field is documented with the
assumptions made during scaffolding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Callable, Optional


@dataclass(slots=True)
class ServerConfig:
    """Runtime configuration for the MCP server.

    Attributes
    ----------
    load_snapshot : bool
        When ``True`` the server attempts to resolve a pre-built TEA Data
        snapshot using :meth:`teadata.DataEngine.from_snapshot`.  The option
        exists because the snapshot can be large; disabling it keeps the
        scaffolding lightweight during unit tests.
    snapshot_search : bool
        Mirrors the ``search`` keyword argument accepted by
        :meth:`teadata.DataEngine.from_snapshot`.  The default mimics the
        documented quick-start behaviour of the library so the server works
        out-of-the-box on developer machines where the package is already
        installed.
    snapshot_path : Optional[Path]
        Optional explicit path to a snapshot file.  When provided it takes
        precedence over ``snapshot_search``.
    engine_factory : Optional[Callable[[], object]]
        Allows injection of a custom factory that returns a configured
        :class:`teadata.DataEngine` instance.  This is primarily useful for
        tests where loading the real engine would be too expensive or
        unnecessary.
    max_response_bytes : Optional[int]
        Soft cap on response payload size for list-heavy tools. Defaults to the
        ``TEADATA_MAX_RESPONSE_BYTES`` environment variable when set, otherwise
        falls back to 24000 bytes. Set to 0 to disable trimming.
    engine_eager_indexing : bool
        Enable eager indexing if the underlying DataEngine supports it.
    engine_tuning : bool
        Attempt to call optional DataEngine warm-up/indexing hooks when present.
    engine_tuning_methods : tuple[str, ...]
        Ordered list of engine methods to invoke during warm-up when available.
    """

    load_snapshot: bool = True
    snapshot_search: bool = True
    snapshot_path: Optional[Path] = None
    engine_factory: Optional[Callable[[], object]] = field(default=None, repr=False)
    max_response_bytes: Optional[int] = None
    engine_eager_indexing: bool = True
    engine_tuning: bool = True
    engine_tuning_methods: tuple[str, ...] = (
        "enable_cache",
        "build_indexes",
        "build_index",
        "preload_indexes",
        "warm",
        "warm_cache",
        "prepare",
        "preload",
    )

    def __post_init__(self) -> None:
        """Populate the snapshot path from ``TEADATA_SNAPSHOT`` when unset."""

        if self.snapshot_path is None:
            env_path = os.getenv("TEADATA_SNAPSHOT")
            if env_path:
                self.snapshot_path = Path(env_path)

        if self.max_response_bytes is None:
            env_value = os.getenv("TEADATA_MAX_RESPONSE_BYTES")
            parsed_value: Optional[int] = None
            if env_value:
                try:
                    parsed_value = int(env_value)
                except ValueError:
                    parsed_value = None
            if parsed_value is None:
                parsed_value = 24000
            self.max_response_bytes = parsed_value

        env_eager = os.getenv("TEADATA_EAGER_INDEXING")
        if env_eager is not None:
            self.engine_eager_indexing = env_eager.strip().lower() in {"1", "true", "yes", "on"}

        env_tuning = os.getenv("TEADATA_ENGINE_TUNING")
        if env_tuning is not None:
            self.engine_tuning = env_tuning.strip().lower() in {"1", "true", "yes", "on"}

        env_methods = os.getenv("TEADATA_ENGINE_TUNING_METHODS")
        if env_methods:
            methods = [item.strip() for item in env_methods.split(",") if item.strip()]
            if methods:
                self.engine_tuning_methods = tuple(methods)

    def resolve_snapshot_path(self) -> Optional[Path]:
        """Return a snapshot path when explicitly configured.

        The helper provides a single, obvious place for LLMs to check when they
        need to reason about file system requirements.  Returning ``None``
        indicates that the default ``DataEngine`` discovery mechanism should be
        used instead.
        """

        if not self.load_snapshot:
            return None
        if self.snapshot_path is None:
            return None
        return Path(self.snapshot_path).expanduser().resolve()
