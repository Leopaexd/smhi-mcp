#!/usr/bin/env python3
"""
SMHI Weather Forecast MCP Server
Provides weather forecast data from SMHI (Swedish Meteorological and Hydrological Institute)
for daily planning context in Stockholm area.
"""

import httpx
from datetime import datetime
from typing import Literal, Optional
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field
from fastmcp import FastMCP
from loguru import logger

# Configure logger with enhanced settings
logger.remove()  # Remove default handler
logger.add(
    "logs/smhi_weather_mcp.log",
    rotation="1 week",
    retention="1 month",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    backtrace=True,
    diagnose=True
)
logger.add(
    "logs/smhi_weather_mcp_debug.log",
    rotation="1 day",
    retention="1 week",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    backtrace=True,
    diagnose=True
)

logger.info("SMHI Weather MCP Server preparing...")

# Default coordinates for Stockholm (Södermalm)
DEFAULT_LAT = 59.32
DEFAULT_LON = 18.04

# Stockholm timezone
STOCKHOLM_TZ = ZoneInfo("Europe/Stockholm")

# SMHI API base URL pattern
SMHI_API_BASE = "https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point"

# Weather symbol meanings (SMHI Wsymb2)
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
    27: "Heavy snowfall"
}


# Structured data models
class HourlyForecast(BaseModel):
    """Hourly weather forecast data"""
    time: str = Field(description="ISO 8601 timestamp in Stockholm local time")
    temperature: float = Field(description="Temperature in Celsius")
    wind_speed: float = Field(description="Wind speed in m/s")
    wind_direction: Optional[int] = Field(default=None, description="Wind direction in degrees")
    wind_gust: Optional[float] = Field(default=None, description="Wind gust speed in m/s")
    precipitation_type: int = Field(description="0=none, 1=snow, 2=snow/rain, 3=rain, 4=drizzle, 5=freezing rain, 6=freezing drizzle")
    precipitation_amount: float = Field(description="Precipitation amount in mm/h")
    humidity: Optional[int] = Field(default=None, description="Relative humidity in percent")
    visibility: Optional[float] = Field(default=None, description="Visibility in km")
    pressure: Optional[float] = Field(default=None, description="Air pressure in hPa")
    cloud_cover: Optional[int] = Field(default=None, description="Total cloud cover in octas (0-8)")
    thunder_probability: Optional[int] = Field(default=None, description="Thunderstorm probability in percent")
    weather_symbol: Optional[int] = Field(default=None, description="SMHI weather symbol (1-27)")
    weather_symbol_meaning: Optional[str] = Field(default=None, description="Human-readable meaning of weather symbol")


class WeatherSummary(BaseModel):
    """Summary statistics for the forecast period"""
    min_temperature: float
    max_temperature: float
    avg_wind_speed: float
    max_wind_speed: float
    max_wind_gust: Optional[float] = None
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
def get_weather_forecast(
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    forecast_hours: int = 24,
    detail_level: Literal["summary", "detailed", "full"] = "detailed",
    include_night: bool = False
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
        logger.debug(f"Validating inputs: lat={lat}, lon={lon}, hours={forecast_hours}, detail={detail_level}, include_night={include_night}")
        
        if not (55.0 <= lat <= 70.0):
            logger.error(f"Invalid latitude: {lat} (must be between 55.0 and 70.0)")
            raise ValueError("Latitude must be between 55.0 and 70.0 (Sweden region)")
        if not (10.0 <= lon <= 25.0):
            logger.error(f"Invalid longitude: {lon} (must be between 10.0 and 25.0)")
            raise ValueError("Longitude must be between 10.0 and 25.0 (Sweden region)")
        if not (1 <= forecast_hours <= 120):
            logger.error(f"Invalid forecast hours: {forecast_hours} (must be between 1 and 120)")
            raise ValueError("Forecast hours must be between 1 and 120")
        
        logger.info(f"Fetching weather forecast for lat={lat}, lon={lon}, hours={forecast_hours}, detail={detail_level}, include_night={include_night}")
        
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
        
        return forecast
        
    except httpx.HTTPStatusError as e:
        error_msg = f"SMHI API error: {e.response.status_code} - {e.response.text}"
        logger.error(error_msg)
        raise RuntimeError(f"Error fetching weather forecast: {error_msg}")
    except Exception as e:
        logger.exception(f"Unexpected error fetching weather forecast: {e}")
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


def parse_forecast_data(data: dict, hours: int, detail_level: str, include_night: bool) -> WeatherForecast:
    """Parse API data into structured forecast"""
    logger.debug(f"Parsing forecast data: hours={hours}, detail_level={detail_level}, include_night={include_night}")
    
    # Parse timestamps and convert to Stockholm time
    ref_time = datetime.fromisoformat(data["referenceTime"].replace("Z", "+00:00")).astimezone(STOCKHOLM_TZ)
    approved_time = datetime.fromisoformat(data["approvedTime"].replace("Z", "+00:00")).astimezone(STOCKHOLM_TZ)
    now = datetime.now(STOCKHOLM_TZ)
    
    logger.debug(f"Reference time: {ref_time}, Approved time: {approved_time}, Current time: {now}")
    
    # Get location coordinates (GeoJSON format: [[lon, lat]])
    coords = data['geometry']['coordinates'][0]
    location_lon, location_lat = coords[0], coords[1]
    logger.debug(f"Location coordinates: lat={location_lat}, lon={location_lon}")
    
    # Filter time series to requested hours
    time_series = data["timeSeries"]
    logger.debug(f"Processing {len(time_series)} time series entries")
    
    hourly_forecasts = []
    filtered_count = 0
    
    for forecast in time_series:
        valid_time = datetime.fromisoformat(forecast["validTime"].replace("Z", "+00:00")).astimezone(STOCKHOLM_TZ)
        hours_from_now = (valid_time - now).total_seconds() / 3600
        
        if 0 <= hours_from_now <= hours:
            # Extract parameters
            params = {p["name"]: p for p in forecast["parameters"]}
            logger.debug(f"Processing forecast for {valid_time} (hours from now: {hours_from_now:.1f})")
            
            # Get weather symbol and its meaning
            weather_symbol = params.get("Wsymb2", {}).get("values", [None])[0]
            weather_symbol_meaning = WEATHER_SYMBOLS.get(weather_symbol) if weather_symbol else None
            
            hourly = HourlyForecast(
                time=valid_time.isoformat(),
                temperature=params.get("t", {}).get("values", [0])[0],
                wind_speed=params.get("ws", {}).get("values", [0])[0],
                wind_direction=params.get("wd", {}).get("values", [None])[0],
                wind_gust=params.get("gust", {}).get("values", [None])[0],
                precipitation_type=params.get("pcat", {}).get("values", [0])[0],
                precipitation_amount=params.get("pmean", {}).get("values", [0])[0],
                humidity=params.get("r", {}).get("values", [None])[0],
                visibility=params.get("vis", {}).get("values", [None])[0],
                pressure=params.get("msl", {}).get("values", [None])[0],
                cloud_cover=params.get("tcc_mean", {}).get("values", [None])[0],
                thunder_probability=params.get("tstm", {}).get("values", [None])[0],
                weather_symbol=weather_symbol,
                weather_symbol_meaning=weather_symbol_meaning
            )
            hourly_forecasts.append(hourly)
        else:
            filtered_count += 1
    
    logger.info(f"Filtered {filtered_count} entries outside time range, kept {len(hourly_forecasts)} entries")
    
    if not hourly_forecasts:
        logger.error("No forecast data available for the requested time period")
        raise ValueError("No forecast data available for the requested time period")
    
    # Calculate summary statistics
    logger.debug("Calculating summary statistics")
    temps = [h.temperature for h in hourly_forecasts]
    winds = [h.wind_speed for h in hourly_forecasts]
    gusts = [h.wind_gust for h in hourly_forecasts if h.wind_gust is not None]
    precip_types = [h.precipitation_type for h in hourly_forecasts]
    
    precip_type_names = {
        0: None, 1: "Snow", 2: "Snow/Rain mix", 3: "Rain",
        4: "Drizzle", 5: "Freezing rain", 6: "Freezing drizzle"
    }
    unique_precip = list(dict.fromkeys([precip_type_names[p] for p in precip_types if p > 0]))
    
    summary = WeatherSummary(
        min_temperature=min(temps),
        max_temperature=max(temps),
        avg_wind_speed=sum(winds) / len(winds),
        max_wind_speed=max(winds),
        max_wind_gust=max(gusts) if gusts else None,
        precipitation_types=unique_precip,
        has_precipitation=any(p > 0 for p in precip_types)
    )
    
    logger.debug(f"Summary: temp range {summary.min_temperature:.1f}-{summary.max_temperature:.1f}°C, "
                f"wind {summary.avg_wind_speed:.1f}-{summary.max_wind_speed:.1f} m/s, "
                f"precipitation: {summary.precipitation_types}")
    
    # Generate planning tips
    logger.debug("Generating planning tips")
    tips = generate_planning_tips(hourly_forecasts, summary)
    logger.debug(f"Generated {len(tips)} planning tips")
    
    # Generate formatted text
    logger.debug("Generating formatted text output")
    formatted_text = format_for_humans(
        now, location_lat, location_lon, approved_time, hours,
        hourly_forecasts, summary, tips, detail_level, include_night
    )
    
    logger.info(f"Successfully created complete forecast with {len(hourly_forecasts)} hourly entries and {len(tips)} planning tips")
    
    return WeatherForecast(
        current_time=now.isoformat(),
        location_lat=location_lat,
        location_lon=location_lon,
        forecast_updated=approved_time.isoformat(),
        forecast_hours=hours,
        hourly=hourly_forecasts,
        summary=summary,
        planning_tips=tips,
        formatted_text=formatted_text
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
    
    # Precipitation tips
    if summary.has_precipitation:
        if any(t in summary.precipitation_types for t in ["Snow", "Snow/Rain mix", "Freezing rain", "Freezing drizzle"]):
            tips.append("🌨️ Snow or freezing conditions expected - allow extra commute time")
            logger.debug("Added snow/freezing precipitation tip")
        elif any(t in summary.precipitation_types for t in ["Rain", "Drizzle"]):
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
    approved_time: datetime,
    hours: int,
    forecasts: list[HourlyForecast],
    summary: WeatherSummary,
    tips: list[str],
    detail_level: str,
    include_night: bool
) -> str:
    """Format forecast as human-readable text"""
    output = []
    output.append("# 🌤️ Weather Forecast for Planning\n")
    output.append(f"**Current time:** {now.strftime('%Y-%m-%d %H:%M')}")
    output.append(f"**Location:** Lat {lat:.2f}, Lon {lon:.2f}")
    output.append(f"**Forecast updated:** {approved_time.strftime('%Y-%m-%d %H:%M')}")
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
                precip_str = format_precipitation(fc.precipitation_type, fc.precipitation_amount)
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


def format_precipitation(pcat: int, amount: float) -> str:
    """Format precipitation information"""
    precip_names = {
        0: None, 1: "Snow", 2: "Snow/Rain", 3: "Rain",
        4: "Drizzle", 5: "Freezing rain", 6: "Freezing drizzle"
    }
    
    if pcat == 0:
        return ""
    
    precip_type = precip_names.get(pcat, "Precipitation")
    if amount > 0:
        return f"{precip_type} ({amount:.1f} mm/h)"
    return precip_type


if __name__ == "__main__":
    logger.info("Starting SMHI Weather MCP Server")
    logger.info(f"Default coordinates: lat={DEFAULT_LAT}, lon={DEFAULT_LON}")
    logger.info(f"Stockholm timezone: {STOCKHOLM_TZ}")
    logger.info("Running server with stdio transport for Cursor integration")
    
    try:
        # Run the server with stdio transport for Cursor integration
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user (Ctrl+C)")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        raise
