#!/usr/bin/env python3
"""
SMHI Weather Forecast MCP Server
Provides weather forecast data from SMHI (Swedish Meteorological and Hydrological Institute)
for daily planning context in Stockholm area.
"""

import logging
import os
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from fastmcp import Context, FastMCP
from loguru import logger
from pydantic import BaseModel, Field

# MCP servers use stdio for JSON-RPC communication - NO console logging allowed!
# Remove all default handlers (loguru adds stderr by default)
logger.remove()

# Add ONLY file logging to avoid corrupting the MCP protocol
os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/smhi_weather_mcp.log",
    rotation="1 week",
    retention="1 month",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    backtrace=True,
    diagnose=True,
)
logger.add(
    "logs/smhi_weather_mcp_debug.log",
    rotation="1 day",
    retention="1 week",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    backtrace=True,
    diagnose=True,
)

# Enable FastMCP client logging to appear in server logs
to_client_logger = logging.getLogger("fastmcp.server.context.to_client")
to_client_logger.setLevel(logging.DEBUG)

logger.info("SMHI Weather MCP Server preparing...")

# Default coordinates for Stockholm (Södermalm)
DEFAULT_LAT = 59.32
DEFAULT_LON = 18.04

# Stockholm timezone
STOCKHOLM_TZ = ZoneInfo("Europe/Stockholm")

# SMHI API base URL pattern (SNOW1gv1; PMP3G v2 deprecated 2026-03-31)
SMHI_API_BASE = "https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1/geotype/point"

# Weather symbol meanings (SMHI symbol_code / Wsymb2-compatible 1–27)
WEATHER_SYMBOLS = {
    1: "Clear sky",
    2: "Nearly clear sky",
    3: "Variable cloudiness",
    4: "Halfclear sky",
    5: "Cloudy sky",
    6: "Overcast",
    7: "Fog",
    8: "Light rain showers",
    9: "Moderate rain showers",
    10: "Heavy rain showers",
    11: "Thunderstorm",
    12: "Light sleet showers",
    13: "Moderate sleet showers",
    14: "Heavy sleet showers",
    15: "Light snow showers",
    16: "Moderate snow showers",
    17: "Heavy snow showers",
    18: "Light rain",
    19: "Moderate rain",
    20: "Heavy rain",
    21: "Thunder",
    22: "Light sleet",
    23: "Moderate sleet",
    24: "Heavy sleet",
    25: "Light snowfall",
    26: "Moderate snowfall",
    27: "Heavy snowfall",
}

# predominant_precipitation_type_at_surface (SNOW1 / ECMWF-style 0–12)
# https://opendata.smhi.se/metfcst/snow1gv1/parameters
SNOW_PRECIP_LABELS: dict[int, str | None] = {
    0: None,
    1: "Rain",
    2: "Thunderstorm",
    3: "Other",
    4: "Mixed/ice",
    5: "Snow",
    6: "Other",
    7: "Mixture of rain and snow",
    8: "Ice pellets",
    9: "Graupel",
    10: "Hail",
    11: "Drizzle",
    12: "Other",
}

# Summary precipitation labels matched against planning tips (subset of SNOW_PRECIP_LABELS values)
PLANNING_ICY_LABELS = frozenset(
    {
        "Snow",
        "Mixture of rain and snow",
        "Mixed/ice",
        "Ice pellets",
        "Graupel",
        "Hail",
    }
)
PLANNING_RAIN_LABELS = frozenset({"Rain", "Drizzle"})


# Structured data models
class HourlyForecast(BaseModel):
    """Hourly weather forecast data"""

    time: str = Field(description="ISO 8601 timestamp in Stockholm local time")
    temperature: float = Field(description="Temperature in Celsius")
    wind_speed: float = Field(description="Wind speed in m/s")
    wind_direction: int | None = Field(default=None, description="Wind direction in degrees")
    wind_gust: float | None = Field(default=None, description="Wind gust speed in m/s")
    precipitation_type: int = Field(
        description=(
            "SNOW1 predominant_precipitation_type_at_surface (0–12): "
            "0 none, 1 rain, 2 thunderstorm, 4 mixed/ice, 5 snow, 7 rain+snow, "
            "8 ice pellets, 9 graupel, 10 hail, 11 drizzle (see SMHI SNOW1 docs)"
        )
    )
    precipitation_amount: float = Field(description="Precipitation amount in mm/h")
    humidity: int | None = Field(default=None, description="Relative humidity in percent")
    visibility: float | None = Field(default=None, description="Visibility in km")
    pressure: float | None = Field(default=None, description="Air pressure in hPa")
    cloud_cover: int | None = Field(default=None, description="Total cloud cover in octas (0-8)")
    thunder_probability: int | None = Field(default=None, description="Thunderstorm probability in percent")
    weather_symbol: int | None = Field(default=None, description="SMHI weather symbol (1-27)")
    weather_symbol_meaning: str | None = Field(default=None, description="Human-readable meaning of weather symbol")


class WeatherSummary(BaseModel):
    """Summary statistics for the forecast period"""

    min_temperature: float
    max_temperature: float
    avg_wind_speed: float
    max_wind_speed: float
    max_wind_gust: float | None = None
    precipitation_types: list[str]
    has_precipitation: bool


class WeatherForecast(BaseModel):
    """Complete weather forecast with structured data and formatted text"""

    current_time: str = Field(description="Current time when forecast was fetched (Stockholm local time)")
    location_lat: float = Field(description="Latitude of forecast location")
    location_lon: float = Field(description="Longitude of forecast location")
    forecast_updated: str = Field(description="When SMHI last updated the forecast (Stockholm local time)")
    forecast_hours: int = Field(description="Number of hours covered by forecast")
    hourly: list[HourlyForecast] = Field(description="Hourly forecast data")
    summary: WeatherSummary = Field(description="Summary statistics")
    planning_tips: list[str] = Field(description="Actionable planning tips")
    formatted_text: str = Field(description="Human-readable formatted forecast")


# Initialize FastMCP server
logger.info("SMHI Weather MCP Server initializing...")
mcp = FastMCP("SMHI Weather Forecast")
logger.info("SMHI Weather MCP Server initialized")


@mcp.tool()
async def get_weather_forecast(
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    forecast_hours: int = 24,
    detail_level: Literal["summary", "detailed", "full"] = "detailed",
    include_night: bool = False,
    ctx: Context | None = None,
) -> WeatherForecast:
    """
    Get weather forecast for a location in Sweden.

    Returns both structured data (all parameters preserved) and formatted text.
    The structured data includes all available weather parameters without information loss.
    By default, shows only daytime hours (08:00-23:59) for practical planning.

    Args:
        lat: Latitude (default: 59.32 for Stockholm, range: 55.0-70.0)
        lon: Longitude (default: 18.04 for Stockholm, range: 10.0-25.0)
        forecast_hours: Number of hours to forecast (default: 24, max: 120)
        detail_level: Level of detail in formatted text:
            - "summary": Just the summary and planning tips
            - "detailed": Daytime hours every 3 hours (default)
            - "full": All hours including nighttime
        include_night: Include nighttime hours (00:00-07:59) in output (default: False)
            Automatically enabled when detail_level is "full"

    Returns:
        WeatherForecast with structured data and formatted text
    """
    try:
        # Validate inputs
        logger.debug(
            "Validating inputs: lat={}, lon={}, hours={}, detail={}, include_night={}",
            lat,
            lon,
            forecast_hours,
            detail_level,
            include_night,
        )
        if ctx:
            await ctx.info("Fetching weather forecast")

        if not (55.0 <= lat <= 70.0):
            logger.error(f"Invalid latitude: {lat} (must be between 55.0 and 70.0)")
            raise ValueError("Latitude must be between 55.0 and 70.0 (Sweden region)")
        if not (10.0 <= lon <= 25.0):
            logger.error(f"Invalid longitude: {lon} (must be between 10.0 and 25.0)")
            raise ValueError("Longitude must be between 10.0 and 25.0 (Sweden region)")
        if not (1 <= forecast_hours <= 120):
            logger.error(f"Invalid forecast hours: {forecast_hours} (must be between 1 and 120)")
            raise ValueError("Forecast hours must be between 1 and 120")

        logger.info(
            "Fetching weather forecast for lat={}, lon={}, hours={}, detail={}, include_night={}",
            lat,
            lon,
            forecast_hours,
            detail_level,
            include_night,
        )

        # Full detail level automatically includes nighttime
        if detail_level == "full":
            include_night = True
            logger.debug("Detail level 'full' automatically enables include_night")

        # Fetch weather data
        logger.debug("Starting API request to SMHI")
        api_data = fetch_weather_forecast(lat, lon)
        logger.info(f"Successfully fetched API data with {len(api_data.get('timeSeries', []))} time series entries")

        # Parse and structure the data
        logger.debug("Parsing and structuring forecast data")
        forecast = parse_forecast_data(api_data, forecast_hours, detail_level, include_night)
        logger.info(f"Successfully created forecast with {len(forecast.hourly)} hourly entries")
        if ctx:
            await ctx.info("Weather forecast ready")
        return forecast

    except httpx.HTTPStatusError as e:
        error_msg = f"SMHI API error: {e.response.status_code} - {e.response.text}"
        logger.error(error_msg)
        if ctx:
            await ctx.error("Weather API returned error")
        raise RuntimeError(f"Error fetching weather forecast: {error_msg}") from e
    except Exception as e:
        logger.exception(f"Unexpected error fetching weather forecast: {e}")
        if ctx:
            await ctx.error("Unexpected error fetching weather data")
        raise


def fetch_weather_forecast(lat: float, lon: float) -> dict:
    """Fetch weather forecast from SMHI API"""
    logger.debug(f"Fetching weather forecast for coordinates: lat={lat}, lon={lon}")

    # Round coordinates to 6 decimals as SMHI expects
    lat = round(lat, 6)
    lon = round(lon, 6)
    logger.debug(f"Rounded coordinates: lat={lat}, lon={lon}")

    # Construct API URL
    url = f"{SMHI_API_BASE}/lon/{lon}/lat/{lat}/data.json"
    logger.debug(f"API URL: {url}")

    try:
        with httpx.Client(timeout=30.0) as client:
            logger.debug("Making HTTP request to SMHI API")
            response = client.get(url)
            logger.debug(f"Received response with status code: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Successfully parsed JSON response with {len(data.get('timeSeries', []))} entries")

        return data
    except httpx.TimeoutException:
        logger.error("Timeout while fetching weather data from SMHI API")
        raise
    except httpx.RequestError as e:
        logger.error(f"Request error while fetching weather data: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while fetching weather data: {e}")
        raise


def _iso_z_to_stockholm(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(STOCKHOLM_TZ)


def _resolve_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(STOCKHOLM_TZ)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(STOCKHOLM_TZ)


def _forecast_package_updated_at(data: dict) -> datetime:
    package_raw = data.get("createdTime") or data.get("referenceTime")
    if not package_raw:
        raise ValueError("SNOW1 response missing createdTime and referenceTime")
    return _iso_z_to_stockholm(package_raw)


def _geometry_point_lat_lon(data: dict) -> tuple[float, float]:
    geom = data.get("geometry") or {}
    coords = geom.get("coordinates")
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        raise ValueError("Invalid or missing geometry coordinates")
    lon, lat = float(coords[0]), float(coords[1])
    return lat, lon


def _hourly_forecast_from_entry(entry: dict, valid_time: datetime) -> HourlyForecast:
    d = entry.get("data") or {}
    sym = d.get("symbol_code")
    weather_symbol = int(sym) if sym is not None else None
    weather_symbol_meaning = WEATHER_SYMBOLS.get(weather_symbol) if weather_symbol is not None else None
    ptype = int(d.get("predominant_precipitation_type_at_surface") or 0)
    pmean = float(d.get("precipitation_amount_mean") or 0.0)
    gust = d.get("wind_speed_of_gust")
    wdir = d.get("wind_from_direction")
    rh = d.get("relative_humidity")
    vis = d.get("visibility_in_air")
    msl = d.get("air_pressure_at_mean_sea_level")
    tcc = d.get("cloud_area_fraction")
    tstm = d.get("thunderstorm_probability")

    return HourlyForecast(
        time=valid_time.isoformat(),
        temperature=float(d.get("air_temperature") or 0.0),
        wind_speed=float(d.get("wind_speed") or 0.0),
        wind_direction=int(wdir) if wdir is not None else None,
        wind_gust=float(gust) if gust is not None else None,
        precipitation_type=ptype,
        precipitation_amount=pmean,
        humidity=int(rh) if rh is not None else None,
        visibility=float(vis) if vis is not None else None,
        pressure=float(msl) if msl is not None else None,
        cloud_cover=int(tcc) if tcc is not None else None,
        thunder_probability=int(tstm) if tstm is not None else None,
        weather_symbol=weather_symbol,
        weather_symbol_meaning=weather_symbol_meaning,
    )


def _weather_summary_from_hourly(hourly_forecasts: list[HourlyForecast]) -> WeatherSummary:
    temps = [h.temperature for h in hourly_forecasts]
    winds = [h.wind_speed for h in hourly_forecasts]
    gusts = [h.wind_gust for h in hourly_forecasts if h.wind_gust is not None]
    precip_codes = [h.precipitation_type for h in hourly_forecasts]

    labels = [SNOW_PRECIP_LABELS.get(p) for p in precip_codes if p > 0]
    unique_precip = list(dict.fromkeys([lb for lb in labels if lb is not None and lb != "Other"]))

    return WeatherSummary(
        min_temperature=min(temps),
        max_temperature=max(temps),
        avg_wind_speed=sum(winds) / len(winds),
        max_wind_speed=max(winds),
        max_wind_gust=max(gusts) if gusts else None,
        precipitation_types=unique_precip,
        has_precipitation=any(p > 0 for p in precip_codes),
    )


def parse_forecast_data(
    data: dict,
    hours: int,
    detail_level: str,
    include_night: bool,
    now: datetime | None = None,
) -> WeatherForecast:
    """Parse SNOW1gv1 point JSON into structured forecast."""
    logger.debug(f"Parsing forecast data: hours={hours}, detail_level={detail_level}, include_night={include_night}")

    now = _resolve_now(now)
    updated_at = _forecast_package_updated_at(data)
    location_lat, location_lon = _geometry_point_lat_lon(data)
    logger.debug(f"Location coordinates: lat={location_lat}, lon={location_lon}")

    time_series = data.get("timeSeries") or []
    logger.debug(f"Processing {len(time_series)} time series entries")

    hourly_forecasts: list[HourlyForecast] = []
    filtered_count = 0

    for entry in time_series:
        if "time" not in entry:
            filtered_count += 1
            continue
        valid_time = _iso_z_to_stockholm(entry["time"])
        hours_from_now = (valid_time - now).total_seconds() / 3600
        if not (0 <= hours_from_now <= hours):
            filtered_count += 1
            continue

        logger.debug(f"Processing forecast for {valid_time} (hours from now: {hours_from_now:.1f})")
        hourly_forecasts.append(_hourly_forecast_from_entry(entry, valid_time))

    logger.info(f"Filtered {filtered_count} entries outside time range, kept {len(hourly_forecasts)} entries")

    if not hourly_forecasts:
        logger.error("No forecast data available for the requested time period")
        raise ValueError("No forecast data available for the requested time period")

    logger.debug("Calculating summary statistics")
    summary = _weather_summary_from_hourly(hourly_forecasts)

    logger.debug(
        f"Summary: temp range {summary.min_temperature:.1f}-{summary.max_temperature:.1f}°C, "
        f"wind {summary.avg_wind_speed:.1f}-{summary.max_wind_speed:.1f} m/s, "
        f"precipitation: {summary.precipitation_types}"
    )

    logger.debug("Generating planning tips")
    tips = generate_planning_tips(hourly_forecasts, summary)
    logger.debug(f"Generated {len(tips)} planning tips")

    logger.debug("Generating formatted text output")
    formatted_text = format_for_humans(
        now,
        location_lat,
        location_lon,
        updated_at,
        hours,
        hourly_forecasts,
        summary,
        tips,
        detail_level,
        include_night,
    )

    logger.info(
        f"Successfully created complete forecast with {len(hourly_forecasts)} hourly entries "
        f"and {len(tips)} planning tips"
    )

    return WeatherForecast(
        current_time=now.isoformat(),
        location_lat=location_lat,
        location_lon=location_lon,
        forecast_updated=updated_at.isoformat(),
        forecast_hours=hours,
        hourly=hourly_forecasts,
        summary=summary,
        planning_tips=tips,
        formatted_text=formatted_text,
    )


def generate_planning_tips(forecasts: list[HourlyForecast], summary: WeatherSummary) -> list[str]:
    """Generate actionable planning tips based on forecast"""
    logger.debug("Generating planning tips based on forecast data")
    tips = []

    # Temperature tips
    if summary.max_temperature < 0:
        tips.append("❄️ Below freezing all day - dress warmly, icy conditions likely")
        logger.debug("Added freezing temperature tip")
    elif summary.min_temperature < 5:
        tips.append("🧥 Cold temperatures - bring warm layers")
        logger.debug("Added cold temperature tip")
    elif summary.max_temperature > 20:
        tips.append("☀️ Warm day - good for outdoor activities")
        logger.debug("Added warm temperature tip")

    if summary.has_precipitation:
        if summary.precipitation_types and any(t in PLANNING_ICY_LABELS for t in summary.precipitation_types):
            tips.append("🌨️ Snow or freezing conditions expected - allow extra commute time")
            logger.debug("Added snow/freezing precipitation tip")
        elif summary.precipitation_types and any(t in PLANNING_RAIN_LABELS for t in summary.precipitation_types):
            tips.append("☔ Rain expected - bring umbrella, consider indoor activities")
            logger.debug("Added rain precipitation tip")

    # Wind tips
    if summary.max_wind_gust and summary.max_wind_gust > 15:
        tips.append(f"💨 Strong wind gusts up to {summary.max_wind_gust:.1f} m/s - biking may be challenging")
        logger.debug(f"Added strong wind gust tip (gusts: {summary.max_wind_gust:.1f} m/s)")
    elif summary.max_wind_speed > 10:
        tips.append("💨 Strong winds - biking may be challenging")
        logger.debug(f"Added strong wind tip (max: {summary.max_wind_speed:.1f} m/s)")

    # Visibility tips
    low_vis = [f for f in forecasts if f.visibility and f.visibility < 1.0]
    if low_vis:
        tips.append("🌫️ Poor visibility expected - drive carefully")
        logger.debug(f"Added poor visibility tip ({len(low_vis)} hours with <1km visibility)")

    # Thunder tips
    thunder_risk = [f for f in forecasts if f.thunder_probability and f.thunder_probability > 30]
    if thunder_risk:
        tips.append("⚡ Thunderstorm risk - avoid outdoor activities during peak hours")
        logger.debug(f"Added thunderstorm risk tip ({len(thunder_risk)} hours with >30% probability)")

    if not tips:
        tips.append("✅ Good weather conditions for normal activities")
        logger.debug("Added default good weather tip")

    logger.debug(f"Generated {len(tips)} planning tips total")
    return tips


def format_for_humans(
    now: datetime,
    lat: float,
    lon: float,
    updated_at: datetime,
    hours: int,
    forecasts: list[HourlyForecast],
    summary: WeatherSummary,
    tips: list[str],
    detail_level: str,
    include_night: bool,
) -> str:
    """Format forecast as human-readable text"""
    output = []
    output.append("# 🌤️ Weather Forecast for Planning\n")
    output.append(f"**Current time:** {now.strftime('%Y-%m-%d %H:%M')}")
    output.append(f"**Location:** Lat {lat:.2f}, Lon {lon:.2f}")
    output.append(f"**Forecast updated:** {updated_at.strftime('%Y-%m-%d %H:%M')}")
    output.append(f"**Showing:** Next {hours} hours\n")

    # Summary section
    output.append("## Today's Summary")
    output.append(f"- **Temperature range:** {summary.min_temperature:.1f}°C to {summary.max_temperature:.1f}°C")

    if summary.precipitation_types:
        output.append(f"- **Precipitation:** {', '.join(summary.precipitation_types)}")
    else:
        output.append("- **Precipitation:** None expected")

    wind_info = f"- **Wind:** {summary.avg_wind_speed:.1f} m/s average, up to {summary.max_wind_speed:.1f} m/s"
    if summary.max_wind_gust:
        wind_info += f" (gusts: {summary.max_wind_gust:.1f} m/s)"
    output.append(wind_info)
    output.append("")

    # Detailed forecast (if not summary-only)
    if detail_level != "summary":
        output.append("## Detailed Forecast")

        step = 1 if detail_level == "full" else 3
        for i, fc in enumerate(forecasts):
            valid_time = datetime.fromisoformat(fc.time)
            hour = valid_time.hour

            # Skip nighttime hours unless requested (00:00-07:59)
            is_nighttime = hour < 8
            if is_nighttime and not include_night:
                continue

            if i % step == 0:
                time_str = valid_time.strftime("%H:%M")

                line_parts = [f"**{time_str}** - {fc.temperature:.1f}°C"]

                # Precipitation
                precip_str = format_precipitation(
                    fc.precipitation_type,
                    fc.precipitation_amount,
                )
                if precip_str:
                    line_parts.append(precip_str)

                # Wind
                wind_str = f"Wind {fc.wind_speed:.1f} m/s"
                if fc.wind_gust and fc.wind_gust > fc.wind_speed + 2:
                    wind_str += f" (gusts {fc.wind_gust:.1f})"
                line_parts.append(wind_str)

                # Additional details for full mode
                if detail_level == "full":
                    if fc.humidity:
                        line_parts.append(f"Humidity {fc.humidity}%")
                    if fc.visibility:
                        line_parts.append(f"Vis {fc.visibility:.1f}km")
                    if fc.weather_symbol_meaning:
                        line_parts.append(f"({fc.weather_symbol_meaning})")

                output.append(", ".join(line_parts))

    # Planning tips
    output.append("\n## Planning Tips")
    for tip in tips:
        output.append(f"- {tip}")

    return "\n".join(output)


def format_precipitation(precipitation_type: int, amount: float) -> str:
    """Format precipitation using SNOW1 predominant type codes (0–12)."""
    if precipitation_type == 0:
        return ""

    label = SNOW_PRECIP_LABELS.get(precipitation_type)
    precip_type = label if label not in (None, "Other") else "Precipitation"
    if amount > 0:
        return f"{precip_type} ({amount:.1f} mm/h)"
    return precip_type


if __name__ == "__main__":
    logger.info("Starting SMHI Weather MCP Server")
    logger.info(f"Default coordinates: lat={DEFAULT_LAT}, lon={DEFAULT_LON}")
    logger.info(f"Stockholm timezone: {STOCKHOLM_TZ}")

    # Decide transport based on environment (Cloud vs local)
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "http":
        port = int(os.getenv("PORT", "8000"))
        logger.info(f"Running server with HTTP transport on port {port} for cloud deployment")
        try:
            mcp.run(transport="http", host="0.0.0.0", port=port)
        except Exception as e:
            logger.exception(f"Server error: {e}")
            raise
    else:
        logger.info("Running server with stdio transport for local development / Cursor")
        try:
            mcp.run(transport="stdio")
        except KeyboardInterrupt:
            logger.info("Server stopped by user (Ctrl+C)")
        except Exception as e:
            logger.exception(f"Server error: {e}")
            raise
