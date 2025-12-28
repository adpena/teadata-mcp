"""Unit tests for the MCP router aggregation logic."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from teadata_mcp.config import ServerConfig
from teadata_mcp.data_engine_provider import DataEngineProvider
from teadata_mcp.query_models import QueryResultStatus
from teadata_mcp.router import QueryRouter

@dataclass
class _FakeCampus:
    name: str
    campus_number: str
    district_number: str
    is_charter: bool = False
    is_private: bool = False
    grade_range: str = "PK-5"
    enrollment: int = 100
    rating: str = "A"

def _provider_with(fake_engine: MagicMock) -> DataEngineProvider:
    config = ServerConfig(engine_factory=lambda: fake_engine)
    return DataEngineProvider(config)

@patch("teadata_mcp.router.find_district")
@patch("teadata_mcp.router.iter_campuses")
@patch("teadata_mcp.router.build_summary")
def test_get_campus_aggregates_stats(mock_build, mock_iter, mock_find_district):
    # Setup test data
    c1 = _FakeCampus(name="Charter A", campus_number="1", district_number="D1", is_charter=True, enrollment=100, rating="A")
    c2 = _FakeCampus(name="Charter B", campus_number="2", district_number="D1", is_charter=True, enrollment=200, rating="B")
    c3 = _FakeCampus(name="ISD C", campus_number="3", district_number="D2", is_charter=False, enrollment=300, rating="C")
    c4 = _FakeCampus(name="Private D", campus_number="4", district_number="D3", is_private=True, enrollment=50, rating="NR")

    mock_iter.return_value = [c1, c2, c3, c4]

    # Mock build_summary
    def _mock_summary(campus):
        m = MagicMock()
        m.name_lower = campus.name.lower()
        m.campus_number_lower = campus.campus_number
        m.district_name_lower = "d" + campus.district_number
        m.charter = campus.is_charter
        m.is_private = campus.is_private
        m.enrollment = campus.enrollment
        m.rating = campus.rating
        m.grade_range = campus.grade_range
        m.district_slug = campus.district_number # slug is D1, D2 etc in this fake setup
        return m
    
    mock_build.side_effect = _mock_summary

    # Mock find_district to return district objects with distinct enrollment
    # District D1 (Charter): Campuses have 100+200=300. District has 350.
    # District D2 (ISD): Campus has 300. District has 300.
    # District D3 (Private): Campus has 50. District has -1 (should be ignored).
    
    d1 = MagicMock()
    d1.enrollment = 350
    d2 = MagicMock()
    d2.enrollment = 300
    d3 = MagicMock()
    d3.enrollment = -1

    def _mock_find(engine, slug):
        if slug == "D1": return d1
        if slug == "D2": return d2
        if slug == "D3": return d3
        return None
    
    mock_find_district.side_effect = _mock_find

    provider = _provider_with(MagicMock())
    router = QueryRouter(provider)

    # 1. Test Aggregate All Charters
    result = router.get_campus_aggregates(status="charter")
    assert result.status is QueryResultStatus.OK
    payload = result.payload
    
    # Should match c1 and c2
    assert payload["total_campuses"] == 2
    # Enrollment should come from District D1 (350), not Sum(100, 200)
    assert payload["total_enrollment"] == 350
    # Average is still total / count ? The prompt didn't specify changing this, but mathematically:
    assert payload["average_enrollment"] == 175.0 # 350 / 2
    assert payload["rating_distribution"] == {"A": 1, "B": 1}
    # Scores: A=90, B=80 -> Avg = 85
    assert payload["average_rating_score"] == 85.0

    # 2. Test Aggregate All ISD
    result_isd = router.get_campus_aggregates(status="isd")
    assert result_isd.payload["total_campuses"] == 1  # c3 only
    assert result_isd.payload["total_enrollment"] == 300

    # 3. Test Aggregate Private (Negative Enrollment Drop)
    result_priv = router.get_campus_aggregates(status="private")
    assert result_priv.payload["total_campuses"] == 1  # c4 only
    # District D3 has -1 enrollment, should drop (add 0)
    assert result_priv.payload["total_enrollment"] == 0

    # 4. Test Aggregate with Rating Filter
    # Filter 'A' matches C1. C1 is in D1. D1 enrollment is 350.
    result_rating = router.get_campus_aggregates(rating="A")
    assert result_rating.payload["total_campuses"] == 1
    assert result_rating.payload["total_enrollment"] == 350

    # 5. Test Aggregate with Query
    result_query = router.get_campus_aggregates(query="Charter")
    assert result_query.payload["total_campuses"] == 2
