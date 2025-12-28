"""Business logic for processing TEA data, ported from teadata-app."""
from __future__ import annotations

import re
import math
from dataclasses import dataclass
from typing import Optional, Iterable, Any

# teadata imports
from teadata.classes import haversine_miles, coerce_grade_spans
from teadata.geometry import point_xy, district_centroid_xy


@dataclass
class CampusSummary:
    campus_number: str
    name: str
    district_name: str
    charter: bool
    is_private: bool
    enrollment: Optional[int]
    rating: Optional[str]
    grade_range: str
    district_slug: str = ""
    name_lower: str = ""
    campus_number_lower: str = ""
    district_name_lower: str = ""
    charter_label_lower: str = ""

    def __post_init__(self):
        if not self.name_lower:
            self.name_lower = self.name.lower()
        if not self.campus_number_lower:
            self.campus_number_lower = self.campus_number.lower()
        if not self.district_name_lower:
            self.district_name_lower = self.district_name.lower()
        if not self.charter_label_lower:
            self.charter_label_lower = self.charter_label.lower()

    def to_dict(self) -> dict[str, object]:
        """Returns a JSON-serializable dictionary representing the summary."""
        return {
            "campus_number": self.campus_number,
            "name": self.name,
            "district_name": self.district_name,
            "charter": self.charter,
            "charter_label": self.charter_label,
            "is_private": self.is_private,
            "enrollment": self.enrollment,
            "rating": self.rating,
            "grade_range": self.grade_range,
            "district_slug": self.district_slug,
        }

    @property
    def charter_label(self) -> str:
        if self.is_private:
            return "Private"
        return "Charter" if self.charter else "ISD"


def canonical_campus_number(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.lstrip("'")


def canonical_district_number(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.replace("'", "")


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
        return ""
    return str(value)


def campus_district_name(campus) -> str:
    district = getattr(campus, "district", None)
    if district is not None:
        name = getattr(district, "name", None)
        if name:
            return str(name)
    meta_name = getattr(campus, "meta", {}).get("district_name")
    if meta_name:
        return str(meta_name)
    return ""


def _sanitize_value(value: Any) -> Any:
    """Return "." if value is negative (masked data), otherwise return value."""
    if value is None:
        return None
    try:
        num = float(value)
        if math.isnan(num):
            return None
        if num < 0:
            return "."
    except (ValueError, TypeError):
        pass
    return value


def build_summary(campus) -> CampusSummary:
    district_number = getattr(campus, "district_number", None)
    if not district_number:
        district = getattr(campus, "district", None)
        if district is not None:
            district_number = getattr(district, "district_number", None)
    if not district_number:
        meta = getattr(campus, "meta", {}) or {}
        district_number = meta.get("district_number")
    district_slug = canonical_district_number(district_number)

    enrollment = getattr(campus, "enrollment", None)
    # Sanitize enrollment (negative means masked)
    enrollment = _sanitize_value(enrollment)
    if enrollment is not None:
        try:
            enrollment = int(enrollment)
        except (ValueError, TypeError):
            enrollment = None

    return CampusSummary(
        campus_number=canonical_campus_number(getattr(campus, "campus_number", None))
        or "",
        name=clean_text(getattr(campus, "name", "")),
        district_name=clean_text(campus_district_name(campus)),
        charter=bool(getattr(campus, "is_charter", False)),
        is_private=bool(getattr(campus, "is_private", False)),
        enrollment=enrollment,
        rating=getattr(campus, "rating", None)
        or getattr(campus, "meta", {}).get("overall_rating_2025"),
        grade_range=clean_text(getattr(campus, "grade_range", "")),
        district_slug=district_slug or "",
    )


def iter_campuses(repo) -> Iterable:
    campuses_view = getattr(repo, "campuses", None)
    if campuses_view is None:
        return []
    values = getattr(campuses_view, "values", None)
    if callable(values):
        try:
            return values()
        except TypeError: 
            pass
    return campuses_view


def _rating_score_from_text(value: object) -> Optional[float]:
    text = clean_text(value)
    if not text:
        return None
    normalized = text.strip()
    if not normalized:
        return None
    if "not rated" in normalized.lower():
        return None

    _LETTER_GRADE_TO_SCORE = {
        "A": 90.0,
        "B": 80.0,
        "C": 70.0,
        "D": 60.0,
        "F": 50.0,
    }

    numeric_matches = re.findall(r"(\d{1,3}(?:\.\d+)?)", normalized)
    for match in numeric_matches:
        try:
            score = float(match)
        except ValueError:
            continue
        if 0.0 <= score <= 110.0:
            return score

    letter_match = re.search(r"\b([ABCDF][+-]?)(?:\b|$)", normalized.upper())
    if letter_match:
        grade = letter_match.group(1)
        base_score = _LETTER_GRADE_TO_SCORE.get(grade[0])
        if base_score is None:
            return None
        if len(grade) > 1:
            modifier = grade[1]
            if modifier == "+":
                base_score += 3.0
            elif modifier == "-":
                base_score -= 3.0
        return base_score

    return None


def _format_distance_miles(
    origin_lat: object,
    origin_lon: object,
    dest_lat: object,
    dest_lon: object,
) -> str:
    try:
        origin_lat_f = float(origin_lat)
        origin_lon_f = float(origin_lon)
        dest_lat_f = float(dest_lat)
        dest_lon_f = float(dest_lon)
    except (TypeError, ValueError):
        return ""

    if not (
        -90.0 <= origin_lat_f <= 90.0
        and -180.0 <= origin_lon_f <= 180.0
        and -90.0 <= dest_lat_f <= 90.0
        and -180.0 <= dest_lon_f <= 180.0
    ):
        return ""

    try:
        distance = haversine_miles(origin_lon_f, origin_lat_f, dest_lon_f, dest_lat_f)
    except Exception:
        return ""

    if distance is None:
        return ""

    try:
        return f"{float(distance):.1f}"
    except (TypeError, ValueError):
        return ""


def collect_staff_and_teacher_stats(campus) -> dict[str, Any]:
    meta = getattr(campus, "meta", {}) or {}
    stats = {}

    # Total Teachers
    key = "campus_2025_staff_teacher_total_full_time_equiv_count"
    stats["total_teachers_fte"] = _sanitize_value(meta.get(key))

    # Student-Teacher Ratio
    key = "campus_2025_staff_teacher_student_ratio"
    stats["student_teacher_ratio"] = _sanitize_value(meta.get(key))

    # Average Salary
    key = "campus_2025_staff_teacher_total_base_salary_average"
    stats["avg_teacher_salary"] = _sanitize_value(meta.get(key))

    # Average Experience
    key = "campus_2025_staff_teacher_experience_average"
    stats["avg_teacher_experience_years"] = _sanitize_value(meta.get(key))

    # Teacher Turnover Rate (best-effort key lookup)
    turnover_keys = (
        "campus_2025_staff_teacher_turnover_rate",
        "campus_2025_staff_teacher_turnover_pct",
        "campus_2025_staff_teacher_turnover_percent",
        "campus_2025_teacher_turnover_rate",
        "campus_2025_teacher_turnover_pct",
        "campus_2025_staff_turnover_rate",
        "campus_2025_staff_turnover_pct",
        "campus_2024_staff_teacher_turnover_rate",
        "campus_2024_teacher_turnover_rate",
    )
    turnover_value = None
    for key in turnover_keys:
        if key in meta and meta.get(key) is not None:
            turnover_value = meta.get(key)
            break
    if turnover_value is None:
        for key, value in meta.items():
            key_text = str(key).lower()
            if "turnover" in key_text and ("teacher" in key_text or "staff_teacher" in key_text):
                turnover_value = value
                if turnover_value is not None:
                    break
    stats["teacher_turnover_rate"] = _sanitize_value(turnover_value)

    return stats


def collect_class_size_stats(campus) -> dict[str, Any]:
    meta = getattr(campus, "meta", {}) or {}
    return {
        "elementary": {
            "kindergarten": _sanitize_value(meta.get("campus_2025_class_size_kindergarten_avg_size")),
            "grade_1": _sanitize_value(meta.get("campus_2025_class_size_grade_1_avg_size")),
            "grade_2": _sanitize_value(meta.get("campus_2025_class_size_grade_2_avg_size")),
            "grade_3": _sanitize_value(meta.get("campus_2025_class_size_grade_3_avg_size")),
            "grade_4": _sanitize_value(meta.get("campus_2025_class_size_grade_4_avg_size")),
            "grade_5": _sanitize_value(meta.get("campus_2025_class_size_grade_5_avg_size")),
            "grade_6": _sanitize_value(meta.get("campus_2025_class_size_grade_6_avg_size")),
        },
        "secondary": {
            "english": _sanitize_value(meta.get("campus_2025_class_size_sec_english_avg_size")),
            "math": _sanitize_value(meta.get("campus_2025_class_size_sec_math_avg_size")),
            "science": _sanitize_value(meta.get("campus_2025_class_size_sec_sci_avg_size")),
            "social_studies": _sanitize_value(meta.get("campus_2025_class_size_sec_soc_stud_avg_size")),
        }
    }


def collect_demographic_stats(campus) -> dict[str, Any]:
    meta = getattr(campus, "meta", {}) or {}
    return {
        "ethnicity_percent": {
            "african_american": _sanitize_value(meta.get("campus_2025_student_enrollment_african_american_percent")),
            "hispanic": _sanitize_value(meta.get("campus_2025_student_enrollment_hispanic_percent")),
            "white": _sanitize_value(meta.get("campus_2025_student_enrollment_white_percent")),
            "asian": _sanitize_value(meta.get("campus_2025_student_enrollment_asian_percent")),
            "pacific_islander": _sanitize_value(meta.get("campus_2025_student_enrollment_pacific_islander_percent")),
            "two_or_more": _sanitize_value(meta.get("campus_2025_student_enrollment_two_or_more_races_percent")),
        },
        "programs_percent": {
            "special_ed": _sanitize_value(meta.get("campus_2025_student_enrollment_special_ed_percent")),
            "econ_disadv": _sanitize_value(meta.get("campus_2025_student_enrollment_economically_disadvantaged_percent")),
            "emergent_bilingual": _sanitize_value(meta.get("campus_2025_student_enrollment_english_learner_percent")),
            "immigrant": _sanitize_value(meta.get("campus_2025_student_enrollment_immigrant_percent")),
        }
    }


def find_campus(repo, campus_number_slug: str):
    canonical = canonical_campus_number(campus_number_slug)
    if not canonical:
        return None

    query_candidates = {canonical}
    if not canonical.startswith("'"):
        query_candidates.add(f"'{canonical}")

    for candidate in query_candidates:
        try:
            result = (repo >> ("campus", candidate)).first()
        except Exception:
            continue
        if result is not None:
            return result
    return None


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _looks_like_point(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and _is_number(value[0])
        and _is_number(value[1])
    )


def _looks_like_ring(value: Any) -> bool:
    if not isinstance(value, (list, tuple)) or not value:
        return False
    return all(_looks_like_point(point) for point in value)


def _close_ring(coords: list[list[float]]) -> list[list[float]]:
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def _geometry_to_geojson(value: Any) -> Optional[dict]:
    if value is None:
        return None
    if isinstance(value, dict):
        if value.get("type") == "Feature" and isinstance(value.get("geometry"), dict):
            return value["geometry"]
        if "type" in value and ("coordinates" in value or "geometries" in value):
            return value
    geo_interface = getattr(value, "__geo_interface__", None)
    if isinstance(geo_interface, dict):
        if geo_interface.get("type") == "Feature" and isinstance(
            geo_interface.get("geometry"), dict
        ):
            return geo_interface["geometry"]
        if "type" in geo_interface and (
            "coordinates" in geo_interface or "geometries" in geo_interface
        ):
            return geo_interface
    if _looks_like_point(value):
        return {"type": "Point", "coordinates": [float(value[0]), float(value[1])]}
    if _looks_like_ring(value):
        coords = _close_ring([[float(pt[0]), float(pt[1])] for pt in value])
        return {"type": "Polygon", "coordinates": [coords]}
    return None


def _point_xy_from_entity(entity: Any) -> tuple[Optional[float], Optional[float], Optional[str]]:
    for attr in ("point", "location", "coords"):
        if hasattr(entity, attr):
            try:
                value = getattr(entity, attr)
            except Exception:
                continue
            xy = point_xy(value)
            if xy is not None:
                return xy[0], xy[1], attr
    return None, None, None


def extract_location(entity: Any) -> tuple[Optional[float], Optional[float], Optional[str]]:
    lon, lat, source = _point_xy_from_entity(entity)
    if lon is not None and lat is not None:
        return lat, lon, source
    centroid = district_centroid_xy(entity)
    if centroid is not None:
        return float(centroid[1]), float(centroid[0]), "district_centroid"
    return None, None, None


def extract_coordinates(entity: Any) -> tuple[Optional[float], Optional[float]]:
    """Extract latitude and longitude from an entity object."""
    lat, lon, _source = extract_location(entity)
    return lat, lon


def extract_geometry(entity: Any) -> tuple[Optional[dict], Optional[str]]:
    for attr in ("polygon", "boundary", "point", "location", "coords"):
        if hasattr(entity, attr):
            try:
                value = getattr(entity, attr)
            except Exception:
                continue
            geo = _geometry_to_geojson(value)
            if geo is not None:
                return geo, attr
    geo = _geometry_to_geojson(entity)
    if geo is not None:
        return geo, "__geo_interface__"
    return None, None


def extract_overall_rating_2025(entity: Any) -> Optional[object]:
    meta = getattr(entity, "meta", {}) or {}
    direct = getattr(entity, "overall_rating_2025", None)
    if direct not in (None, ""):
        return direct
    meta_value = meta.get("overall_rating_2025")
    if meta_value not in (None, ""):
        return meta_value
    fallback = getattr(entity, "overall_rating", None)
    if fallback not in (None, ""):
        return fallback
    meta_fallback = meta.get("overall_rating")
    if meta_fallback not in (None, ""):
        return meta_fallback
    return None


def extract_meta_fields(entity: Any, fields: Optional[list[str]]) -> dict[str, Any]:
    if not fields:
        return {}
    meta = getattr(entity, "meta", {}) or {}
    out: dict[str, Any] = {}
    for raw in fields:
        if raw is None:
            continue
        key = str(raw).strip()
        if not key:
            continue
        if key.startswith("meta."):
            lookup = key[5:]
            output_key = lookup
        else:
            lookup = key
            output_key = key
        value = meta.get(lookup)
        if value is None:
            value = getattr(entity, lookup, None)
        if value is not None:
            out[output_key] = value
    return out


def find_district(repo, district_number_slug: str):
    canonical = canonical_district_number(district_number_slug)
    if not canonical:
        # Fallback search by name if slug is likely a name
        return (repo >> ("district", district_number_slug)).first()

    query_candidates = {canonical}
    if not canonical.startswith("'"):
        query_candidates.add(f"'{canonical}")

    for candidate in query_candidates:
        try:
            result = (repo >> ("district", candidate)).first()
        except Exception:
            continue
        if result is not None:
            return result
    return None
