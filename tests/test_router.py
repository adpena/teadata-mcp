"""Unit tests for the MCP query router."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

from teadata_mcp.config import ServerConfig
from teadata_mcp.data_engine_provider import DataEngineProvider
from teadata_mcp.query_models import QueryResultStatus
from teadata_mcp.router import QueryRouter


@dataclass
class _FakeDistrict:
    name: str
    district_number: str
    rating: Optional[str] = None
    overall_rating_2025: Optional[str] = None
    enrollment: Optional[int] = None
    boundary: Optional[dict] = None


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
    coords: tuple[float, float] = (30.0, -97.0)


def _provider_with(fake_engine: MagicMock) -> DataEngineProvider:
    config = ServerConfig(engine_factory=lambda: fake_engine)
    return DataEngineProvider(config)


@patch("teadata_mcp.router.find_district")
def test_get_district_returns_summary_when_match_found(mock_find):
    district = _FakeDistrict(name="Aldine ISD", district_number="101902", rating="A")
    mock_find.return_value = district

    provider = _provider_with(MagicMock())
    router = QueryRouter(provider)

    result = router.get_district("Aldine ISD")

    assert result.status is QueryResultStatus.OK
    assert result.payload["name"] == "Aldine ISD"
    assert result.payload["district_number"] == "101902"


@patch("teadata_mcp.router.find_district")
def test_get_district_declines_when_no_match(mock_find):
    mock_find.return_value = None
    provider = _provider_with(MagicMock())
    router = QueryRouter(provider)

    result = router.get_district("Unknown ISD")

    assert result.status is QueryResultStatus.UNKNOWN
    assert "refrains from guessing" in result.message


def test_get_district_requires_identifier():
    provider = _provider_with(MagicMock())
    router = QueryRouter(provider)

    result = router.get_district("   ")

    assert result.status is QueryResultStatus.UNKNOWN
    assert "Please supply a district" in result.message


@patch("teadata_mcp.router.iter_campuses")
@patch("teadata_mcp.router.build_summary")
def test_search_campuses_filters_results(mock_build, mock_iter):
    c1 = _FakeCampus(name="Alpha Elementary", campus_number="1", district_number="D1")
    c2 = _FakeCampus(
        name="Beta High", campus_number="2", district_number="D1", is_charter=True
    )

    mock_iter.return_value = [c1, c2]

    # Mock build_summary to return objects with attributes we check
    s1 = MagicMock()
    s1.name_lower = "alpha elementary"
    s1.campus_number_lower = "1"
    s1.district_name_lower = "d1"
    s1.charter = False
    s1.is_private = False
    s1.to_dict.return_value = {"name": "Alpha Elementary"}

    s2 = MagicMock()
    s2.name_lower = "beta high"
    s2.campus_number_lower = "2"
    s2.district_name_lower = "d1"
    s2.charter = True
    s2.is_private = False
    s2.to_dict.return_value = {"name": "Beta High"}

    mock_build.side_effect = [s1, s2, s1, s2]  # for multiple calls

    provider = _provider_with(MagicMock())
    router = QueryRouter(provider)

    # Test search by name
    res1 = router.search_campuses(query="Alpha")
    assert len(res1.payload["results"]) == 1
    assert res1.payload["results"][0]["name"] == "Alpha Elementary"
    assert res1.payload["completeness"]["returned_count"] == 1
    assert res1.payload["table"]["columns"]
    assert res1.payload["exports"]["csv"]["resource_uri"].startswith(
        "teadata://export/"
    )

    # Test filter by charter
    res2 = router.search_campuses(query="", status="charter")
    assert len(res2.payload["results"]) == 1
    assert res2.payload["results"][0]["name"] == "Beta High"


@patch("teadata_mcp.router.find_campus")
@patch("teadata_mcp.router.build_summary")
def test_get_campus_detail_returns_data(mock_build, mock_find):
    c1 = _FakeCampus(name="Alpha", campus_number="1", district_number="D1")
    mock_find.return_value = c1

    s1 = MagicMock()
    s1.name = "Alpha"
    s1.campus_number = "1"
    s1.to_dict.return_value = {"name": "Alpha", "number": "1"}
    mock_build.return_value = s1

    provider = _provider_with(MagicMock())
    router = QueryRouter(provider)

    result = router.get_campus_detail("1")

    assert result.status is QueryResultStatus.OK
    assert result.payload["name"] == "Alpha"


@patch("teadata_mcp.router.find_district")
def test_get_district_detail_returns_data(mock_find):
    d1 = _FakeDistrict(name="D1", district_number="101")
    mock_find.return_value = d1

    engine = MagicMock()
    # Mock campuses_in to return empty list
    engine.campuses_in.return_value = []

    provider = _provider_with(engine)
    router = QueryRouter(provider)

    result = router.get_district_detail("101")

    assert result.status is QueryResultStatus.OK
    assert result.payload["name"] == "D1"
    assert "campuses" in result.payload


@patch("teadata_mcp.router.extract_coordinates")
@patch("teadata_mcp.router.find_campus")
@patch("teadata_mcp.router.build_summary")
def test_get_nearby_campuses_by_id(mock_build, mock_find, mock_extract):
    engine = MagicMock()
    c1 = _FakeCampus(name="Center", campus_number="1", district_number="D1")
    c2 = _FakeCampus(name="Nearby", campus_number="2", district_number="D1")

    mock_find.return_value = c1
    mock_extract.side_effect = [(30.0, -97.0), (30.05, -97.05)]  # center, nearby

    engine.radius_campuses.return_value = [c2]

    s2 = MagicMock()
    s2.to_dict.return_value = {"name": "Nearby"}
    mock_build.return_value = s2

    provider = _provider_with(engine)
    router = QueryRouter(provider)

    result = router.get_nearby_campuses(identifier="1", radius_miles=5)

    assert result.status is QueryResultStatus.OK
    assert len(result.payload["results"]) == 1
    assert result.payload["results"][0]["name"] == "Nearby"
    # Ensure radius_campuses called with correct coords (lon, lat based on convention)
    engine.radius_campuses.assert_called_with(-97.0, 30.0, 5)


def test_get_nearby_campuses_requires_location():
    provider = _provider_with(MagicMock())
    router = QueryRouter(provider)

    result = router.get_nearby_campuses(radius_miles=5)
    assert result.status is QueryResultStatus.ERROR
    assert "Could not determine location" in result.message


@patch("teadata_mcp.router.find_campus")
@patch("teadata_mcp.router.collect_demographic_stats")
@patch("teadata_mcp.router.collect_staff_and_teacher_stats")
@patch("teadata_mcp.router.build_summary")
def test_compare_campuses_returns_data(mock_build, mock_staff, mock_demo, mock_find):
    c1 = _FakeCampus(name="C1", campus_number="1", district_number="D1")
    c2 = _FakeCampus(name="C2", campus_number="2", district_number="D1")

    mock_find.side_effect = [c1, c2]

    s1 = MagicMock()
    s1.to_dict.return_value = {
        "name": "C1",
        "campus_number": "1",
        "rating": "A",
        "enrollment": 500,
    }
    s2 = MagicMock()
    s2.to_dict.return_value = {
        "name": "C2",
        "campus_number": "2",
        "rating": "B",
        "enrollment": 600,
    }
    mock_build.side_effect = [s1, s2]

    mock_staff.return_value = {"avg_teacher_salary": 50000}
    mock_demo.return_value = {"programs_percent": {"econ_disadv": 50.0}}

    provider = _provider_with(MagicMock())
    router = QueryRouter(provider)

    result = router.compare_campuses(["1", "2"])

    assert result.status is QueryResultStatus.OK
    assert len(result.payload["comparison"]) == 2
    assert result.payload["comparison"][0]["name"] == "C1"
    assert result.payload["comparison"][1]["name"] == "C2"


@patch("teadata_mcp.router.find_district")
def test_find_campuses_in_district_boundary_filters(mock_find):
    boundary = [
        (-98.0, 30.0),
        (-98.0, 31.0),
        (-97.0, 31.0),
        (-97.0, 30.0),
        (-98.0, 30.0),
    ]
    district = _FakeDistrict(
        name="Austin ISD", district_number="227901", boundary=boundary
    )
    mock_find.return_value = district

    inside_charter = _FakeCampus(
        name="IDEA North",
        campus_number="1",
        district_number="D1",
        is_charter=True,
        coords=(-97.5, 30.5),
    )
    inside_charter.meta = {
        "overall_rating_2025": "A",
        "campus_2025_staff_teacher_student_ratio": 15.2,
    }
    other_charter = _FakeCampus(
        name="KIPP Central",
        campus_number="2",
        district_number="D1",
        is_charter=True,
        coords=(-96.0, 30.5),
    )

    engine = MagicMock()
    engine.charter_campuses_within.return_value = [inside_charter, other_charter]
    provider = _provider_with(engine)
    router = QueryRouter(provider)

    result = router.find_campuses_in_district_boundary(
        district_identifier="Austin ISD",
        campus_query="IDEA",
        status="charter",
        limit=10,
        response_profile="both",
        campus_meta_fields=["campus_2025_staff_teacher_student_ratio"],
        campus_list_format="full",
        include_total=True,
    )

    assert result.status is QueryResultStatus.OK
    assert result.payload["count"] == 1
    assert result.payload["campuses"][0]["name"] == "IDEA North"
    assert result.payload["campuses"][0]["overall_rating_2025"] == "A"
    assert (
        result.payload["campuses"][0]["meta"]["campus_2025_staff_teacher_student_ratio"]
        == 15.2
    )
    assert result.payload["district"]["geometry"] is None
    assert "boundary_reference" in result.payload["district"]
    assert result.payload["district"]["boundary_reference"]["download_url"]
    assert result.payload["pagination"]["cursor"] == 0
    assert result.payload["pagination"]["has_more"] is False
    assert result.payload["pagination"]["next_cursor"] is None
    assert result.payload["pagination"]["total_matches"] == 1
    assert result.payload["do_not_web_search"] is True
    assert result.payload["next_tool_call"] is None
    assert result.payload["completeness"]["returned_count"] == 1
    assert "geojson" in result.payload
    assert len(result.payload["geojson"]["features"]) == 1
    assert (
        result.payload["geojson"]["features"][0]["properties"]["meta"][
            "campus_2025_staff_teacher_student_ratio"
        ]
        == 15.2
    )
    assert result.payload["map_instructions"]
    engine.charter_campuses_within.assert_called_with(district)


@patch("teadata_mcp.router.find_district")
@patch.object(QueryRouter, "_payload_size")
def test_boundary_trimming_adds_response_trimmed(mock_payload_size, mock_find):
    boundary = [
        (-98.0, 30.0),
        (-98.0, 31.0),
        (-97.0, 31.0),
        (-97.0, 30.0),
        (-98.0, 30.0),
    ]
    district = _FakeDistrict(
        name="Austin ISD", district_number="227901", boundary=boundary
    )
    mock_find.return_value = district

    inside_charter = _FakeCampus(
        name="IDEA North",
        campus_number="1",
        district_number="D1",
        is_charter=True,
        coords=(-97.5, 30.5),
    )
    other_charter = _FakeCampus(
        name="KIPP Central",
        campus_number="2",
        district_number="D1",
        is_charter=True,
        coords=(-97.6, 30.6),
    )

    engine = MagicMock()
    engine.charter_campuses_within.return_value = [inside_charter, other_charter]
    provider = _provider_with(engine)
    router = QueryRouter(provider)

    def fake_payload_size(payload: dict) -> int:
        return 100 + len(payload.get("campuses", [])) * 100

    mock_payload_size.side_effect = fake_payload_size

    result = router.find_campuses_in_district_boundary(
        district_identifier="Austin ISD",
        status="charter",
        response_profile="list",
        campus_list_format="full",
        limit=10,
        max_response_bytes=250,
    )

    assert result.payload["count"] == 1
    assert result.payload["response_trimmed"]["applied"] is True
    assert any(
        "Results trimmed" in note
        for note in result.payload["response_trimmed"]["notes"]
    )
    assert result.payload["pagination"]["has_more"] is True
    assert result.payload["pagination"]["next_cursor"] == 1
