"""Lazy loading helpers for :class:`teadata.DataEngine`.

The provider encapsulates the slightly involved bootstrap logic required to
obtain a ready-to-use ``DataEngine``.  Keeping it in a dedicated module helps
LLMs reason about where the heavy lifting happens and makes the logic easy to
unit test without touching the real dataset.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .config import ServerConfig


class DataEngineLoadError(RuntimeError):
    """Raised when the data engine could not be instantiated."""


@dataclass(slots=True)
class DataEngineProvider:
    """Load and cache a :class:`teadata.DataEngine` instance on demand.

    Parameters
    ----------
    config:
        A :class:`~teadata_mcp.config.ServerConfig` instance describing how the
        engine should be created.  The provider does not modify the object so it
        can be shared across multiple components safely.
    """

    config: ServerConfig
    _engine: Optional[Any] = None
    _load_error: Optional[Exception] = None

    def ensure_loaded(self) -> Any:
        """Return a fully initialised :class:`teadata.DataEngine` instance.

        The loader favours explicit configuration supplied through
        :attr:`ServerConfig.engine_factory`.  When no factory is provided it will
        attempt to import :mod:`teadata` lazily so that importing the scaffolding
        does not immediately require optional dependencies.

        Raises
        ------
        DataEngineLoadError
            If the engine failed to load earlier or if the import machinery is
            unavailable in the current environment.
        """

        if self._engine is not None:
            return self._engine
        if self._load_error is not None:
            raise DataEngineLoadError("Data engine failed to load") from self._load_error

        try:
            engine = self._build_engine()
        except Exception as exc:  # pragma: no cover - defensive logging branch
            self._load_error = exc
            raise DataEngineLoadError("Unable to initialise the TEA Data engine") from exc

        self._engine = engine
        return engine

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_engine(self) -> Any:
        """Create a :class:`teadata.DataEngine` using the configured strategy."""

        if self.config.engine_factory is not None:
            return self.config.engine_factory()

        try:
            from teadata import DataEngine  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised in manual runs
            raise DataEngineLoadError(
                "teadata is not installed. Install the library or provide "
                "ServerConfig.engine_factory."
            ) from exc

        snapshot_path = self.config.resolve_snapshot_path()
        if snapshot_path is not None:
            return DataEngine(snapshot=str(snapshot_path))
        if self.config.load_snapshot:
            return DataEngine.from_snapshot(search=self.config.snapshot_search)
        return DataEngine()
