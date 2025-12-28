"""Tests for transfer insight aggregation."""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from teadata_mcp.config import ServerConfig
from teadata_mcp.data_engine_provider import DataEngineProvider
from teadata_mcp.query_models import QueryResultStatus
from teadata_mcp.router import QueryRouter


@dataclass(frozen=True)
class _FakeCampus:
    name: str
    campus_number: str
    district_number: str = "D1"
    is_charter: bool = False
    is_private: bool = False
    rating: str = "B"


def _provider_with(fake_engine: object) -> DataEngineProvider:
    config = ServerConfig(engine_factory=lambda: fake_engine)
    return DataEngineProvider(config)


def test_transfer_insights_missing_method():
    engine = SimpleNamespace()
    router = QueryRouter(_provider_with(engine))

    result = router.get_transfer_insights()

    assert result.status is QueryResultStatus.UNKNOWN
    assert result.payload["available"] is False


@patch("teadata_mcp.router.haversine_miles", return_value=1.0)
@patch("teadata_mcp.router.extract_coordinates")
@patch("teadata_mcp.router.iter_campuses")
def test_transfer_insights_aggregates(mock_iter, mock_coords, _mock_distance):
    source1 = _FakeCampus(name="Source One", campus_number="S1", rating="B")
    source2 = _FakeCampus(name="Source Two", campus_number="S2", rating="C")
    dest1 = _FakeCampus(name="Dest Charter", campus_number="D1", rating="A", is_charter=True)
    dest2 = _FakeCampus(name="Dest Traditional", campus_number="D2", rating="C")
    dest3 = _FakeCampus(name="Dest Higher", campus_number="D3", rating="B")

    mock_iter.return_value = [source1, source2]
    coord_map = {
        source1: (30.0, -97.0),
        source2: (31.0, -98.0),
        dest1: (30.01, -97.01),
        dest2: (30.02, -97.02),
        dest3: (31.01, -98.01),
    }
    mock_coords.side_effect = lambda campus: coord_map[campus]

    engine = MagicMock()

    def transfers_out(campus):
        if campus is source1:
            return [(dest1, 12, False), (dest2, 8, False)]
        if campus is source2:
            return [(dest3, 20, False)]
        return []

    engine.transfers_out.side_effect = transfers_out

    router = QueryRouter(_provider_with(engine))
    result = router.get_transfer_insights(
        top_sources=2,
        top_destinations=2,
        min_transfer_count=10,
        neighborhood_radius_miles=2,
    )

    assert result.status is QueryResultStatus.OK
    payload = result.payload
    assert payload["summary"]["total_transfers"] == 40
    assert payload["charter_breakdown"]["charter_count"] == 12
    assert payload["rating_shift"]["higher_count"] == 32
    assert payload["rating_shift"]["lower_count"] == 8
    assert payload["distance"]["within_radius_percent"] == 100.0

    link_values = {link["value"] for link in payload["sankey"]["links"]}
    assert 8 not in link_values
    assert payload["map"]["flows"]


@patch("teadata_mcp.router.haversine_miles", return_value=1.0)
@patch("teadata_mcp.router.extract_coordinates", return_value=(30.0, -97.0))
@patch("teadata_mcp.router.iter_campuses")
def test_transfer_insights_caps_limits(mock_iter, _mock_coords, _mock_distance):
    source = _FakeCampus(name="Source", campus_number="S1", rating="B")
    dest = _FakeCampus(name="Dest", campus_number="D1", rating="A")
    mock_iter.return_value = [source]

    engine = MagicMock()
    engine.transfers_out.return_value = [(dest, 15, False)]

    router = QueryRouter(_provider_with(engine))
    result = router.get_transfer_insights(
        top_sources=1000,
        top_destinations=50,
        min_transfer_count=1,
    )

    payload = result.payload
    assert payload["sankey"]["source_limit"] == 200
    assert payload["sankey"]["destination_limit"] == 10
