"""Unit tests for the negative value sanitization logic."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock
from typing import Optional, Any

from teadata_mcp.logic import (
    _sanitize_value,
    build_summary,
    collect_staff_and_teacher_stats,
    collect_class_size_stats,
    collect_demographic_stats,
)

def test_sanitize_value():
    assert _sanitize_value(100) == 100
    assert _sanitize_value(0) == 0
    assert _sanitize_value(None) is None
    assert _sanitize_value(-1) == "."
    assert _sanitize_value(-100.5) == "."
    assert _sanitize_value("100") == "100" # Should return value if it casts to float
    # Logic: try float(val). If < 0 return ".". If exception, return val.
    assert _sanitize_value("-5") == "."

    # Strings that are not numbers should pass through (e.g. names)
    assert _sanitize_value("Austin") == "Austin"

def test_build_summary_sanitizes_enrollment():
    c1 = MagicMock()
    c1.campus_number = "1"
    c1.name = "Positive"
    c1.enrollment = 100
    s1 = build_summary(c1)
    assert s1.enrollment == 100

    c2 = MagicMock()
    c2.campus_number = "2"
    c2.name = "Negative"
    c2.enrollment = -1
    s2 = build_summary(c2)
    assert s2.enrollment is None # build_summary casts result to int or None

def test_collect_stats_sanitizes_negatives():
    c = MagicMock()
    c.meta = {
        "campus_2025_staff_teacher_total_full_time_equiv_count": -1,
        "campus_2025_staff_teacher_student_ratio": 15.5,
        "campus_2025_staff_teacher_turnover_rate": -1,
        "campus_2025_class_size_kindergarten_avg_size": -1.0,
        "campus_2025_student_enrollment_african_american_percent": -1,
        "campus_2025_student_enrollment_white_percent": 25.0,
    }

    staff = collect_staff_and_teacher_stats(c)
    assert staff["total_teachers_fte"] == "."
    assert staff["student_teacher_ratio"] == 15.5
    assert staff["teacher_turnover_rate"] == "."

    classes = collect_class_size_stats(c)
    assert classes["elementary"]["kindergarten"] == "."

    demo = collect_demographic_stats(c)
    assert demo["ethnicity_percent"]["african_american"] == "."
    assert demo["ethnicity_percent"]["white"] == 25.0
