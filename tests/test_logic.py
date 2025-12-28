"""Unit tests for teadata_mcp.logic helper functions."""
from teadata_mcp.logic import (
    _rating_score_from_text,
    _format_distance_miles,
    canonical_campus_number,
    canonical_district_number,
    _looks_like_point,
    _looks_like_ring,
    CampusSummary,
)

def test_rating_score_from_text():
    assert _rating_score_from_text("A") == 90.0
    assert _rating_score_from_text("B") == 80.0
    assert _rating_score_from_text("C") == 70.0
    assert _rating_score_from_text("D") == 60.0
    assert _rating_score_from_text("F") == 50.0
    
    assert _rating_score_from_text("85") == 85.0
    assert _rating_score_from_text("92.5") == 92.5
    
    # Modifiers
    assert _rating_score_from_text("A+") == 93.0
    assert _rating_score_from_text("B-") == 77.0
    
    # Edge cases
    assert _rating_score_from_text(None) is None
    assert _rating_score_from_text("Not Rated") is None
    assert _rating_score_from_text("NR") is None
    assert _rating_score_from_text("") is None


def test_format_distance_miles():
    # Valid
    assert _format_distance_miles(30.0, -97.0, 30.1, -97.0) != ""
    distance = float(_format_distance_miles(30.0, -97.0, 30.1, -97.0))
    assert distance > 0
    
    # Invalid coordinates
    assert _format_distance_miles("invalid", -97.0, 30.0, -97.0) == ""
    assert _format_distance_miles(200.0, -97.0, 30.0, -97.0) == "" # Lat out of range
    
    # Same point
    assert _format_distance_miles(30.0, -97.0, 30.0, -97.0) == "0.0"


def test_canonical_campus_number():
    assert canonical_campus_number("123456789") == "123456789"
    assert canonical_campus_number("'123456789") == "123456789"
    assert canonical_campus_number(None) is None
    assert canonical_campus_number("  ") is None


def test_canonical_district_number():
    assert canonical_district_number("123456") == "123456"
    assert canonical_district_number("'123456") == "123456"
    assert canonical_district_number("123456'") == "123456"
    assert canonical_district_number(None) is None


def test_looks_like_point():
    assert _looks_like_point([1.0, 2.0]) is True
    assert _looks_like_point((1.0, 2.0)) is True
    assert _looks_like_point([1.0, 2.0, 3.0]) is True # 3D point? typically yes
    
    assert _looks_like_point([]) is False
    assert _looks_like_point([1.0]) is False
    assert _looks_like_point("not a list") is False
    assert _looks_like_point([None, 1.0]) is False


def test_looks_like_ring():
    ring = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]
    assert _looks_like_ring(ring) is True
    assert _looks_like_ring([]) is False
    assert _looks_like_ring([[0.0]]) is False # Points are invalid


def test_campus_summary_defaults():
    s = CampusSummary(
        campus_number="123",
        name="Test",
        district_name="D1",
        charter=False,
        is_private=False,
        enrollment=100,
        rating="A",
        grade_range="PK-5"
    )
    
    assert s.name_lower == "test"
    assert s.district_name_lower == "d1"
    assert s.charter_label == "ISD"
    
    s_charter = CampusSummary(
        campus_number="123",
        name="Test",
        district_name="D1",
        charter=True,
        is_private=False,
        enrollment=100,
        rating="A",
        grade_range="PK-5"
    )
    assert s_charter.charter_label == "Charter"
