"""Tests for SNOW1gv1 forecast parsing (deterministic via fixed *now*)."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from server import (
    STOCKHOLM_TZ,
    format_precipitation,
    parse_forecast_data,
)

FIXTURE = Path(__file__).parent / "fixtures" / "snow1_point_sample.json"


@pytest.fixture
def snow1_payload() -> dict:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def fixed_now_window_start() -> datetime:
    """Deterministic 'now' aligned with fixture time series for a 24h window."""
    return datetime(2026, 4, 8, 8, 0, 0, tzinfo=STOCKHOLM_TZ)


def test_parse_snow1_geometry_and_updated(snow1_payload: dict, fixed_now_window_start: datetime) -> None:
    """Point geometry is [lon, lat]; forecast_updated follows createdTime."""
    result = parse_forecast_data(
        snow1_payload, hours=24, detail_level="summary", include_night=True, now=fixed_now_window_start
    )
    assert result.location_lat == pytest.approx(59.309023)
    assert result.location_lon == pytest.approx(18.031205)
    assert "2026-04-08T08:31:37" in result.forecast_updated  # 06:31 UTC -> Stockholm


def test_parse_snow1_hourly_fields(snow1_payload: dict, fixed_now_window_start: datetime) -> None:
    result = parse_forecast_data(
        snow1_payload, hours=24, detail_level="summary", include_night=True, now=fixed_now_window_start
    )
    assert len(result.hourly) == 3
    h0 = result.hourly[0]
    assert h0.temperature == pytest.approx(3.6)
    assert h0.wind_speed == pytest.approx(4.4)
    assert h0.wind_direction == 351
    assert h0.wind_gust == pytest.approx(8.3)
    assert h0.precipitation_type == 0
    assert h0.precipitation_amount == pytest.approx(0.0)
    assert h0.humidity == 85
    assert h0.visibility == pytest.approx(14.9)
    assert h0.pressure == pytest.approx(1031.7)
    assert h0.cloud_cover == 8
    assert h0.thunder_probability == 0
    assert h0.weather_symbol == 4
    assert h0.weather_symbol_meaning == "Halfclear sky"

    h1 = result.hourly[1]
    assert h1.precipitation_type == 1  # Rain in SNOW1 table
    assert h1.thunder_probability == 40


def test_parse_snow1_summary_precipitation_types(snow1_payload: dict, fixed_now_window_start: datetime) -> None:
    result = parse_forecast_data(
        snow1_payload, hours=24, detail_level="summary", include_night=True, now=fixed_now_window_start
    )
    assert result.summary.has_precipitation is True
    assert "Rain" in result.summary.precipitation_types
    assert "Snow" in result.summary.precipitation_types


def test_parse_snow1_planning_tips_thunder_and_visibility(
    snow1_payload: dict, fixed_now_window_start: datetime
) -> None:
    result = parse_forecast_data(
        snow1_payload, hours=24, detail_level="summary", include_night=True, now=fixed_now_window_start
    )
    joined = " ".join(result.planning_tips)
    assert "Thunderstorm" in joined or "thunder" in joined.lower()
    assert "visibility" in joined.lower() or "Poor visibility" in joined


def test_format_precipitation_snow1_codes() -> None:
    assert format_precipitation(0, 0.0) == ""
    assert "Rain" in format_precipitation(1, 0.5)
    assert "Snow" in format_precipitation(5, 0.0)
    assert "Drizzle" in format_precipitation(11, 0.1)


def test_parse_empty_window_raises(snow1_payload: dict) -> None:
    """No time steps in range -> ValueError."""
    far_future = datetime(2027, 1, 1, 12, 0, 0, tzinfo=STOCKHOLM_TZ)
    with pytest.raises(ValueError, match="No forecast data"):
        parse_forecast_data(snow1_payload, hours=2, detail_level="summary", include_night=True, now=far_future)
