"""Unit tests for the MCP query router.

The real ``teadata`` package is heavy and requires domain data.  The tests rely
on lightweight fakes that emulate just enough behaviour to verify the guard
rails baked into the scaffolding.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from teadata_mcp.config import ServerConfig
from teadata_mcp.data_engine_provider import DataEngineProvider
from teadata_mcp.query_models import QueryResultStatus
from teadata_mcp.router import QueryRouter


@dataclass
class _FakeDistrict:
    name: str
    district_number: str
    rating: Optional[str] = None


class _FakeEngine:
    def __init__(self, district: Optional[_FakeDistrict] = None):
        self._district = district

    def get_district(self, identifier: str):
        if self._district is None:
            return None
        if identifier.lower() not in {self._district.name.lower(), self._district.district_number}:
            return None
        return self._district


def _provider_with(fake_engine: _FakeEngine) -> DataEngineProvider:
    config = ServerConfig(engine_factory=lambda: fake_engine)
    return DataEngineProvider(config)


def test_get_district_returns_summary_when_match_found():
    district = _FakeDistrict(name="Aldine ISD", district_number="101902", rating="A")
    provider = _provider_with(_FakeEngine(district))
    router = QueryRouter(provider)

    result = router.get_district("Aldine ISD")

    assert result.status is QueryResultStatus.OK
    assert result.payload == {
        "name": "Aldine ISD",
        "district_number": "101902",
        "rating": "A",
    }


def test_get_district_declines_when_no_match():
    provider = _provider_with(_FakeEngine(None))
    router = QueryRouter(provider)

    result = router.get_district("Unknown ISD")

    assert result.status is QueryResultStatus.UNKNOWN
    assert "refrains from guessing" in result.message


def test_get_district_requires_identifier():
    provider = _provider_with(_FakeEngine(None))
    router = QueryRouter(provider)

    result = router.get_district("   ")

    assert result.status is QueryResultStatus.UNKNOWN
    assert "Please supply a district" in result.message
