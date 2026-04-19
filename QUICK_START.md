# JogAir Temporal Routing - Quick Start Guide

## Installation

All dependencies are already in our project. Just run the code:

```bash
python main.py --info
```

## Data Sources

JogAir supports two data sources for air quality information:

### CSV Data (Historical)
- **Default mode**: Uses pre-downloaded CSV data
- **Data range**: March 9 - April 12, 2026
- **Advantages**: Fast, offline, predictable
- **Use case**: Development, testing, demos

### Live API Data (Real-time)
- **Live mode**: Fetches current data from Open-Meteo API
- **Data range**: Past 1 day + forecast 3 days
- **Advantages**: Real-time pollution data, always current
- **Use case**: Production, real user applications

## Usage Examples

### 1. Display Data Information
```bash
# CSV data (default)
python main.py --info

# Live data
python main.py --data-source live --info
```

### 2. Calculate Routes with CSV Data
```bash
python main.py --start 56.1552 10.2082 --end 56.1571 10.2112 --time "2026-03-15 14:30"
```

### 3. Calculate Routes with Live Data
```bash
python main.py --data-source live --start 56.1533 10.2144 --end 56.1365 10.2050 --time "2026-04-18 14:30"
```

**Parameters:**
- `--start LAT LON`: Starting coordinates (latitude, longitude)
- `--end LAT LON`: Ending coordinates
- `--time`: ISO 8601 datetime (optional, defaults to now)
- `--data-source`: 'csv' or 'live' (default: 'csv')

**Supported time formats:**
- `2026-03-15` (date only, midnight)
- `2026-03-15 14:30` (date and time)
- `2026-03-15T14:30:00` (ISO 8601)

### 4. Calculate Routes with Current Time
```bash
# CSV data
python main.py --start 56.1533 10.2144 --end 56.1365 10.2050

# Live data
python main.py --data-source live --start 56.1533 10.2144 --end 56.1365 10.2050
```

## Live Data Features

### Lazy Loading
- Data is only fetched when first requested
- Subsequent requests use cached data (valid for 1 hour)
- No unnecessary API calls

### Cache Status
When using `--info` with live data, you'll see:
```
Cache Valid:              True/False
Last Fetch:               2026-04-18T14:30:00
Cache Age:                45.2 minutes
Expires In:               14.8 minutes
```

### Error Handling
- If API is unavailable, falls back to default pollution value (1.0 µg/m³)
- Routes are still calculated with fallback values
- System remains functional even with network issues

## Output Interpretation

The output shows:

1. **Request/Matched Time:** The time you requested and the actual hourly record matched
2. **Pollution Level:** PM2.5 concentration (µg/m³) at matched time
3. **Data Source:** 'csv' or 'live_api' (or 'fallback' if API fails)
4. **Shortest Distance Route:** Direct route optimizing for distance
5. **Clean Air Route:** Route optimized to minimize pollution exposure
6. **Comparison:** Distance difference and interpretation

## Example Output

```
Pollution Level:      PM2.5 = 4.1 µg/m³

SHORTEST DISTANCE ROUTE
Description:  Shortest Distance (17 nodes, 458m)
Distance:     458 meters

CLEAN AIR ROUTE
Description:  Clean Air (16 nodes, 471m, pollution cost: 1144)
Distance:     471 meters

COMPARISON
Distance Difference:  +13m (+2.9%)
Note:                 Clean air route is slightly longer (prefer less-polluted streets)
```

## Available Data Range

- **Dates:** March 9, 2026 - April 12, 2026
- **Frequency:** Hourly (24 readings per day)
- **Total Records:** 840 observations
- **Pollutants:** PM2.5 and NO2

## Testing

Run all tests:
```bash
python -m pytest tests/ -v
```

Run specific test module:
```bash
python -m pytest tests/test_air_quality_loader.py -v
python -m pytest tests/test_routing_engine.py -v
python -m pytest tests/test_temporal_routing_integration.py -v
```

## Architecture Overview

```
main.py (CLI)
    ↓
TemporalRoutingOrchestrator
    ├─ AirQualityDataLoader (CSV → pollution lookup)
    ├─ Graph loading (Aarhus street network)
    └─ Routing engine (cost calculation & pathfinding)
```

## API Usage (Python Code)

```python
from datetime import datetime
from src.collectors.pipeline.temporal_routing_orchestrator import TemporalRoutingOrchestrator

# Initialize
orchestrator = TemporalRoutingOrchestrator()

# Calculate routes
result = orchestrator.calculate_temporal_routes(
    start_latitude=56.1552,
    start_longitude=10.2082,
    end_latitude=56.1571,
    end_longitude=10.2112,
    request_datetime=datetime(2026, 3, 15, 14, 30)
)

# Access results
print(f"Shortest distance: {result.shortest_distance_route.distance_m}m")
print(f"Clean air distance: {result.clean_air_route.distance_m}m")
print(f"Pollution level: {result.pollution_value} {result.pollution_unit}")
print(f"Matched time: {result.matched_datetime}")
```

## Design Highlights

- **Separation of Concerns:** Data loading, routing, and orchestration are independent modules
- **Testable:** 42 unit and integration tests covering all components
- **Extensible:** Easy to swap CSV for API, add new features, or integrate with UI
- **Efficient:** Graph and data loaded once; O(1) pollution lookups
- **Backward Compatible:** Existing routing code unchanged

## File Reference

| File | Purpose |
|------|---------|
| [main.py](main.py) | CLI entry point |
| [src/collectors/air_quality_loader.py](src/collectors/air_quality_loader.py) | Air quality data loading and lookup |
| [src/collectors/pipeline/temporal_routing_orchestrator.py](src/collectors/pipeline/temporal_routing_orchestrator.py) | Orchestration layer |
| [src/collectors/pipeline/daily/routing_engine.py](src/collectors/pipeline/daily/routing_engine.py) | Route calculation (modified) |
| [tests/](tests/) | Comprehensive test suite (42 tests) |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | Detailed implementation documentation |

## Next Steps

1. **Add UI Layer:** Integrate with Streamlit for interactive visualization
2. **Real-Time Data:** Hook up Open-Meteo API for live pollution updates
3. **Advanced Routes:** Compare multiple route options or use different cost functions
4. **Export:** Add GeoJSON/GPX export for navigation apps

## Support

For detailed architecture and implementation details, see [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md).

For code questions, check the docstrings in:
- `air_quality_loader.py` - Data loading logic
- `temporal_routing_orchestrator.py` - Orchestration
- `routing_engine.py` - Route calculation
