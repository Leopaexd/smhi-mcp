# SMHI Weather Forecast MCP Server

An MCP (Model Context Protocol) server that provides weather forecasts from SMHI (Sveriges Meteorologiska och Hydrologiska Institut) for daily planning in Sweden.

## Overview

This server integrates Swedish weather forecasts directly into your AI assistant workflow, providing real-time weather data with Stockholm local time and human-readable weather descriptions.

## Features

- ✅ **Structured data output** - All weather parameters preserved in typed Pydantic models
- ✅ **Human-readable text** - Formatted markdown with emoji indicators
- ✅ **Stockholm local time** - All timestamps in CEST/CET (no UTC confusion!)
- ✅ **Weather symbol meanings** - Human-readable descriptions for all 27 SMHI weather symbols
- ✅ **No information loss** - 14 parameters per hour including weather symbol meanings
- ✅ **Daytime focus** - By default shows only waking hours (08:00-23:59) for practical planning
- ✅ **Optional nighttime** - Include night hours when needed or use "full" detail level
- ✅ **Flexible detail levels** - Choose between summary, detailed, or full output
- ✅ Planning-focused tips based on weather conditions

## Installation

### Using uv (recommended)

```bash
uv pip install fastmcp httpx pydantic loguru
```

### Using pip

```bash
pip install fastmcp httpx pydantic loguru
```

## Configuration

### As a Git Submodule (Recommended)

Add this repository as a submodule to your project:

```bash
git submodule add https://github.com/yourusername/smhi-weather-mcp.git
git submodule update --init --recursive
```

Then add to your MCP settings (e.g., `.cursor/mcp.json` for Cursor):

```json
{
  "mcpServers": {
    "smhi_weather": {
      "command": "uv",
      "args": ["run", "python", "smhi-weather-mcp/smhi_weather_mcp.py"],
      "enabled": true
    }
  }
}
```

### Standalone Installation

Or clone and run directly:

```bash
git clone https://github.com/yourusername/smhi-weather-mcp.git
cd smhi-weather-mcp
python smhi_weather_mcp.py
```

## Usage

The server provides a single tool: `get_weather_forecast`

### Parameters

- `lat` (float): Latitude (55.0-70.0, default: 59.32 for Stockholm/Södermalm)
- `lon` (float): Longitude (10.0-25.0, default: 18.04 for Stockholm/Södermalm)
- `forecast_hours` (int): Hours to forecast (1-120, default: 24)
- `detail_level` (str): Detail level for formatted text output
  - `"summary"`: Just summary stats and planning tips
  - `"detailed"`: Summary + daytime hours every 3 hours (default, 08:00-23:59)
  - `"full"`: Summary + all hours including nighttime + extra details
- `include_night` (bool): Include nighttime hours (00:00-07:59) in output (default: False)

### Example Queries

- "What's the weather like today? Should I bike to work?"
- "Check the weather forecast for planning my day"
- "Will it rain this afternoon during my planned break?"
- "What should I wear today based on the weather?"

### Example Output

```markdown
# 🌤️ Weather Forecast for Planning

**Current time:** 2025-10-05 09:15
**Location:** Lat 59.32, Lon 18.04
**Forecast updated:** 2025-10-05 08:00
**Showing:** Next 24 hours

## Today's Summary
- **Temperature range:** 8.5°C to 14.2°C
- **Precipitation:** Rain
- **Wind:** 4.2 m/s average, up to 6.8 m/s (gusts: 9.1 m/s)

## Detailed Forecast
**09:00** - 10.2°C, Rain (0.8 mm/h), Wind 4.5 m/s (gusts 7.2)
**12:00** - 12.8°C, Rain (1.2 mm/h), Wind 5.2 m/s (gusts 8.1)
**15:00** - 13.5°C, Drizzle, Wind 6.1 m/s
**18:00** - 11.0°C, Wind 4.8 m/s

## Planning Tips
- 🧥 Cold temperatures - bring warm layers
- ☔ Rain expected - bring umbrella, consider indoor activities
```

## Data Structure

The tool returns a `WeatherForecast` object with:

- **Structured data**: Complete hourly forecasts with 14 parameters per hour
- **Summary statistics**: Min/max temp, wind, precipitation types
- **Planning tips**: Actionable advice based on conditions
- **Formatted text**: Human-readable markdown output

Each hourly forecast includes:
- Temperature, wind (speed/direction/gusts)
- Precipitation (type/amount)
- Humidity, visibility, pressure
- Cloud cover, thunder probability
- Weather symbol and its meaning

## Weather Symbols

SMHI provides 27 weather symbols automatically decoded to human-readable descriptions:

| Symbol | Meaning |
|--------|---------|
| 1 | Clear sky |
| 2 | Nearly clear sky |
| 3 | Variable cloudiness |
| 4 | Halfclear sky |
| 5 | Cloudy sky |
| 6 | Overcast |
| 7 | Fog |
| 8-10 | Light/Moderate/Heavy rain showers |
| 11 | Thunderstorm |
| 12-14 | Light/Moderate/Heavy sleet showers |
| 15-17 | Light/Moderate/Heavy snow showers |
| 18-20 | Light/Moderate/Heavy rain |
| 21 | Thunder |
| 22-24 | Light/Moderate/Heavy sleet |
| 25-27 | Light/Moderate/Heavy snowfall |

## API Information

- **Data source**: SMHI PMP3G API
- **License**: Creative Commons Attribution 4.0
- **Rate limits**: None specified for open data
- **Documentation**: https://opendata.smhi.se/apidocs/
- **Coverage**: Sweden (lat: 55-70°, lon: 10-25°)

## Use Cases

### 🚴 Commute Planning
- Check if rain or snow is expected
- Wind conditions for biking
- Temperature for choosing clothing

### 🌳 Break Planning
- Best times for outdoor breaks
- When to avoid going outside
- Temperature considerations

### 📅 Activity Scheduling
- Reschedule outdoor meetings if bad weather expected
- Plan indoor vs outdoor tasks
- Adjust timing for better weather windows

### 🧥 Preparation
- What to wear today
- Whether to bring umbrella
- Extra commute time for icy conditions

## Logging

Logs are stored in `logs/smhi_weather_mcp.log` with:
- 1 week rotation
- 1 month retention
- INFO level and above

## Troubleshooting

### Server doesn't start
1. Check dependencies are installed
2. Check logs in `logs/smhi_weather_mcp.log`
3. Verify correct directory

### No data returned
1. Check coordinates are within Sweden (lat: 55-70, lon: 10-25)
2. SMHI API might be temporarily down
3. Check logs for specific errors

### Weather seems outdated
- SMHI updates forecasts every few hours
- Check "Forecast updated" timestamp
- Re-run the tool to fetch latest data

## Credits

- Weather data: [SMHI - Sveriges Meteorologiska och Hydrologiska Institut](https://www.smhi.se)
- License: Creative Commons Attribution 4.0 International
- Built with: [FastMCP](https://github.com/jlowin/fastmcp)

## License

MIT License

---

**Note:** SMHI data is used under CC-BY 4.0 license with proper attribution.
