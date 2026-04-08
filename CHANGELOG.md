# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-08

### Changed
- **Breaking:** Forecast data source migrated from deprecated PMP3G v2 to **SNOW1gv1** (`snow1g/version/1`). PMP3G is scheduled for shutdown on **2026-03-31** per [SMHI](https://www.smhi.se/data/om-smhis-data/uppdateringar-oppna-data/uppdateringar-i-smhis-oppna-data/2025-09-12-nya-apier-for-meteorologiska-prognoser-och-analyser).
- **`precipitation_type`** on hourly forecasts now uses SNOW1 `predominant_precipitation_type_at_surface` codes (**0–12**, ECMWF-style), not legacy PMP3 `pcat` (0–6). See [SNOW1 parameters](https://opendata.smhi.se/metfcst/snow1gv1/parameters).
- **`forecast_updated`** is derived from API `createdTime` (fallback `referenceTime`), replacing the removed `approvedTime` field.

### Added
- `tzdata` dependency for reliable IANA time zones on Windows.
- Dev dependencies: `pytest`, `ruff`, `ty`; tests under `tests/` with SNOW1 fixture JSON.

## [1.0.0] - 2025-10-05

### Added
- Initial release of SMHI Weather MCP Server
- Single tool `get_weather_forecast` with comprehensive weather data
- Structured Pydantic models for all weather parameters
- Stockholm local time (CEST/CET) for all timestamps
- 27 SMHI weather symbols with human-readable meanings
- 14 parameters per hour: temperature, wind (speed/direction/gusts), precipitation, humidity, visibility, pressure, cloud cover, thunder probability, weather symbol
- Daytime focus: filters nighttime hours (00:00-07:59) by default
- Three detail levels: summary, detailed, full
- Optional nighttime inclusion parameter
- Planning-focused tips based on weather conditions
- FastMCP integration for easy MCP server deployment
- Comprehensive logging with rotation
- MIT License
- Full documentation and examples

### Features
- No information loss - all API data preserved in structured format
- Human-readable formatted text output
- Support for any location in Sweden (lat: 55-70°, lon: 10-25°)
- Default coordinates for Stockholm/Södermalm
- Error handling and validation
- SMHI data attribution (CC-BY 4.0)
