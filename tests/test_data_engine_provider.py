"""Tests for :mod:`teadata_mcp.data_engine_provider`."""
from __future__ import annotations

import pytest

from teadata_mcp.config import ServerConfig
from teadata_mcp.data_engine_provider import DataEngineLoadError, DataEngineProvider


def test_engine_factory_is_used_when_provided():
    instance = object()
    config = ServerConfig(engine_factory=lambda: instance)
    provider = DataEngineProvider(config)

    assert provider.ensure_loaded() is instance
    # A second call should return the cached instance.
    assert provider.ensure_loaded() is instance


def test_engine_failure_is_cached():
    config = ServerConfig(engine_factory=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    provider = DataEngineProvider(config)

    with pytest.raises(DataEngineLoadError):
        provider.ensure_loaded()

    # Subsequent calls raise the cached error immediately.
    with pytest.raises(DataEngineLoadError):
        provider.ensure_loaded()
