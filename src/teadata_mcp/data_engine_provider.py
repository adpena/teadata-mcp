"""Lazy loading helpers for :class:`teadata.DataEngine`.

The provider encapsulates the slightly involved bootstrap logic required to
obtain a ready-to-use ``DataEngine``.  Keeping it in a dedicated module helps
LLMs reason about where the heavy lifting happens and makes the logic easy to
unit test without touching the real dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import logging
import threading
import time
from typing import Any, Optional

from .config import ServerConfig

logger = logging.getLogger(__name__)


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
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False
    )

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
            raise DataEngineLoadError(
                "Data engine failed to load"
            ) from self._load_error

        with self._lock:
            if self._engine is not None:
                return self._engine
            if self._load_error is not None:
                raise DataEngineLoadError(
                    "Data engine failed to load"
                ) from self._load_error

            started = time.perf_counter()
            snapshot_path = None
            try:
                resolved = self.config.resolve_snapshot_path()
                snapshot_path = str(resolved) if resolved is not None else None
            except Exception:
                snapshot_path = None

            try:
                engine = self._build_engine()
            except Exception as exc:  # pragma: no cover - defensive logging branch
                self._load_error = exc
                logger.exception(
                    "Data engine failed to initialise",
                    extra={
                        "snapshot_path": snapshot_path,
                        "load_snapshot": self.config.load_snapshot,
                        "snapshot_search": self.config.snapshot_search,
                        "engine_eager_indexing": self.config.engine_eager_indexing,
                        "engine_tuning": self.config.engine_tuning,
                    },
                )
                raise DataEngineLoadError(
                    "Unable to initialise the TEA Data engine"
                ) from exc

            duration_ms = (time.perf_counter() - started) * 1000
            self._engine = engine
            logger.info(
                "Data engine initialised",
                extra={
                    "ms": round(duration_ms, 1),
                    "snapshot_path": snapshot_path,
                    "load_snapshot": self.config.load_snapshot,
                    "snapshot_search": self.config.snapshot_search,
                    "engine_eager_indexing": self.config.engine_eager_indexing,
                    "engine_tuning": self.config.engine_tuning,
                },
            )
            return engine

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_engine(self) -> Any:
        """Create a :class:`teadata.DataEngine` using the configured strategy."""

        if self.config.engine_factory is not None:
            engine = self.config.engine_factory()
            return self._tune_engine(engine)

        try:
            from teadata import DataEngine  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised in manual runs
            raise DataEngineLoadError(
                "teadata is not installed. Run `uv sync` to install dependencies."
            ) from exc

        def _is_lfs_pointer_error(exc: BaseException) -> bool:
            message = str(exc).lower()
            return "git-lfs pointer" in message or "lfs pointer" in message

        def _empty_engine_fallback() -> Any:
            # Some teadata releases ship a snapshot placeholder (git-lfs pointer). When that
            # happens, treat it as "no snapshot available" so the server can still start.
            try:
                return DataEngine.from_snapshot(
                    search=False,
                    **self._snapshot_kwargs(DataEngine),
                )
            except Exception:
                return DataEngine(**self._init_kwargs(DataEngine))

        snapshot_path = self.config.resolve_snapshot_path()
        if snapshot_path is not None:
            try:
                engine = DataEngine(
                    snapshot=str(snapshot_path), **self._init_kwargs(DataEngine)
                )
            except Exception as exc:
                if _is_lfs_pointer_error(exc):
                    logger.warning(
                        "Snapshot is a git-lfs pointer; starting with an empty engine. "
                        "Set TEADATA_SNAPSHOT_URL or TEADATA_SNAPSHOT to a real snapshot to enable data.",
                        extra={"snapshot_path": str(snapshot_path)},
                    )
                    engine = _empty_engine_fallback()
                else:
                    raise
            return self._tune_engine(engine)
        if self.config.load_snapshot:
            try:
                engine = DataEngine.from_snapshot(
                    search=self.config.snapshot_search,
                    **self._snapshot_kwargs(DataEngine),
                )
            except Exception as exc:
                if _is_lfs_pointer_error(exc):
                    logger.warning(
                        "Snapshot discovery resolved to a git-lfs pointer; starting with an empty engine. "
                        "Set TEADATA_SNAPSHOT_URL to a real snapshot asset URL to enable data.",
                        extra={"snapshot_search": self.config.snapshot_search},
                    )
                    engine = _empty_engine_fallback()
                else:
                    raise
            return self._tune_engine(engine)
        engine = DataEngine(**self._init_kwargs(DataEngine))
        return self._tune_engine(engine)

    def _init_kwargs(self, engine_type: Any) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.config.engine_eager_indexing:
            eager_kwarg = self._first_supported_kwarg(
                engine_type,
                ("eager_indexes", "eager_indexing", "eager_index", "eager"),
            )
            if eager_kwarg:
                kwargs[eager_kwarg] = True
        return kwargs

    def _snapshot_kwargs(self, engine_type: Any) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.config.engine_eager_indexing:
            eager_kwarg = self._first_supported_kwarg(
                getattr(engine_type, "from_snapshot", engine_type),
                ("eager_indexes", "eager_indexing", "eager_index", "eager"),
            )
            if eager_kwarg:
                kwargs[eager_kwarg] = True
        return kwargs

    @staticmethod
    def _first_supported_kwarg(
        callable_obj: Any, names: tuple[str, ...]
    ) -> Optional[str]:
        for name in names:
            if DataEngineProvider._supports_kwarg(callable_obj, name):
                return name
        return None

    @staticmethod
    def _supports_kwarg(callable_obj: Any, name: str) -> bool:
        try:
            sig = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            return False
        for param in sig.parameters.values():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                return True
        return name in sig.parameters

    @staticmethod
    def _callable_accepts_no_args(callable_obj: Any) -> bool:
        try:
            sig = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            return False
        for param in sig.parameters.values():
            if (
                param.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
                and param.default is inspect._empty
            ):
                return False
        return True

    def _tune_engine(self, engine: Any) -> Any:
        if not engine:
            return engine

        if self.config.engine_eager_indexing and hasattr(engine, "eager_indexing"):
            attr = getattr(engine, "eager_indexing", None)
            if callable(attr):
                if self._callable_accepts_no_args(attr):
                    try:
                        attr()
                    except Exception:
                        pass
            else:
                try:
                    setattr(engine, "eager_indexing", True)
                except Exception:
                    pass

        if not self.config.engine_tuning:
            return engine

        for method_name in self.config.engine_tuning_methods:
            method = getattr(engine, method_name, None)
            if not callable(method):
                continue
            if not self._callable_accepts_no_args(method):
                continue
            try:
                method()
            except Exception:
                continue

        return engine
