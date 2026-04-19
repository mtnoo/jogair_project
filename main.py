"""
JogAir - Clean Air Route Planner

Entry point for the JogAir application. Provides CLI for calculating
routes that optimize for clean air quality at a specific time.
"""

import argparse
import logging
from datetime import datetime

from src.collectors.pipeline.temporal_routing_orchestrator import (
    TemporalRoutingOrchestrator,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_datetime(datetime_str: str) -> datetime:
    """
    Parse datetime string in ISO 8601 format.
    
    Supports formats:
    - 2026-03-15 14:30
    - 2026-03-15T14:30:00
    - 2026-03-15
    
    Args:
        datetime_str: DateTime string to parse
    
    Returns:
        datetime object
    
    Raises:
        ValueError: If format is invalid
    """
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(
        f"Invalid datetime format: '{datetime_str}'. "
        f"Supported formats: YYYY-MM-DD, YYYY-MM-DD HH:MM, YYYY-MM-DD HH:MM:SS"
    )


def format_route_output(route_comparison) -> str:
    """
    Format route comparison results for display.
    
    Args:
        route_comparison: RouteComparison object
    
    Returns:
        Formatted string for display
    """
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("TEMPORAL ROUTE COMPARISON")
    lines.append("=" * 80)
    
    lines.append(f"\nRequest Time:         {route_comparison.request_datetime.isoformat()}")
    if route_comparison.matched_datetime:
        lines.append(f"Matched Data Time:    {route_comparison.matched_datetime.isoformat()}")
    else:
        lines.append(f"Matched Data Time:    N/A (out of range)")
    
    if route_comparison.out_of_range:
        lines.append(f"⚠️  WARNING: Request time is outside data range. Using fallback pollution value.")
    else:
        time_delta_mins = route_comparison.time_delta_seconds / 60
        lines.append(f"Time Delta:           {time_delta_mins:.1f} minutes")
    
    lines.append(f"\nPollution Level:      PM2.5 = {route_comparison.pollution_value:.1f} {route_comparison.pollution_unit}")
    lines.append(f"Data Source:          {route_comparison.data_source}")
    
    if route_comparison.is_stale_data:
        lines.append("⚠️  WARNING: Using stale pollution data (no recent measurements available)")
    
    lines.append("\n" + "-" * 80)
    lines.append("SHORTEST DISTANCE ROUTE")
    lines.append("-" * 80)
    shortest = route_comparison.shortest_distance_route
    lines.append(f"Description:  {shortest.description}")
    lines.append(f"Distance:     {shortest.distance_m:.0f} meters")
    lines.append(f"Nodes:        {len(shortest.node_ids)}")
    
    lines.append("\n" + "-" * 80)
    lines.append("CLEAN AIR ROUTE")
    lines.append("-" * 80)
    clean = route_comparison.clean_air_route
    lines.append(f"Description:  {clean.description}")
    lines.append(f"Distance:     {clean.distance_m:.0f} meters")
    lines.append(f"Nodes:        {len(clean.node_ids)}")
    
    lines.append("\n" + "-" * 80)
    lines.append("COMPARISON")
    lines.append("-" * 80)
    
    distance_diff = clean.distance_m - shortest.distance_m
    if shortest.distance_m > 0:
        distance_diff_pct = (distance_diff / shortest.distance_m) * 100
        lines.append(f"Distance Difference:  {distance_diff:+.0f}m ({distance_diff_pct:+.1f}%)")
    else:
        lines.append(f"Distance Difference:  {distance_diff:.0f}m")
    
    # Calculate estimated pollution exposure (simplified as distance * pollution level)
    shortest_exposure = shortest.distance_m * route_comparison.pollution_value
    clean_exposure = clean.distance_m * route_comparison.pollution_value
    
    exposure_diff = clean_exposure - shortest_exposure
    if shortest_exposure > 0:
        exposure_diff_pct = (exposure_diff / shortest_exposure) * 100
        lines.append(f"Pollution Exposure:   {exposure_diff:+.0f} µg/m³-m ({exposure_diff_pct:+.1f}%)")
    
    if clean.distance_m > 0 and shortest.distance_m > 0:
        if abs(distance_diff) < 1:
            lines.append("Note:                 Routes are nearly identical at this pollution level")
        elif distance_diff > 0:
            lines.append(f"Note:                 Clean air route is slightly longer (prefer less-polluted streets)")
        else:
            lines.append(f"Note:                 Clean air route is shorter (less-polluted streets align with direct path)")
    
    lines.append("=" * 80 + "\n")
    
    return "\n".join(lines)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="JogAir: Clean Air Route Planner for Aarhus, Denmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --start 56.1552 10.2082 --end 56.1571 10.2112 --time "2026-03-15 14:30"
  python main.py --start 56.1552 10.2082 --end 56.1571 10.2112 --time 2026-03-15
  python main.py --info
        """
    )
    
    parser.add_argument(
        "--start",
        nargs=2,
        type=float,
        metavar=("LAT", "LON"),
        help="Starting location (latitude longitude)",
    )
    
    parser.add_argument(
        "--end",
        nargs=2,
        type=float,
        metavar=("LAT", "LON"),
        help="Ending location (latitude longitude)",
    )
    
    parser.add_argument(
        "--time",
        type=str,
        default=None,
        help="Request time (ISO 8601 format, e.g., '2026-03-15 14:30'). Defaults to now if not specified.",
    )
    
    parser.add_argument(
        "--info",
        action="store_true",
        help="Display information about loaded data and exit",
    )
    
    parser.add_argument(
        "--data-source",
        choices=["csv", "live"],
        default="csv",
        help="Data source for air quality: 'csv' (historical) or 'live' (real-time API). Default: csv",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        logger.info("Initializing JogAir...")
        orchestrator = TemporalRoutingOrchestrator(data_source=args.data_source)
        
        if args.info:
            # Display data information
            info = orchestrator.get_data_info()
            print("\n" + "=" * 80)
            print("DATA INFORMATION")
            print("=" * 80)
            print(f"Graph Nodes:              {info['graph_nodes']:,}")
            print(f"Graph Edges:              {info['graph_edges']:,}")
            print(f"Air Quality Records:      {info['air_quality_records']}")
            print(f"Data Source:              {info['data_source']}")

            if info['air_quality_date_range']:
                start_date, end_date = info['air_quality_date_range']
                print(f"Air Quality Date Range:   {start_date} to {end_date}")
            else:
                print("Air Quality Date Range:   Not loaded yet (live data)")

            # Show cache status for live data
            if 'cache_status' in info:
                cache = info['cache_status']
                print(f"Cache Valid:              {cache['cache_valid']}")
                if cache['last_fetch']:
                    print(f"Last Fetch:               {cache['last_fetch']}")
                    print(f"Cache Age:                {cache['cache_age_minutes']:.1f} minutes")
                    print(f"Expires In:               {cache['expires_in_minutes']:.1f} minutes")

            print("=" * 80 + "\n")
            return
        
        if not args.start or not args.end:
            parser.print_help()
            print("\n❌ Error: --start and --end are required for route calculation")
            return 1
        
        # Parse request time
        if args.time:
            try:
                request_datetime = parse_datetime(args.time)
            except ValueError as e:
                print(f"\n❌ Error: {e}")
                return 1
        else:
            request_datetime = datetime.now()
            logger.info(f"No time specified, using current time: {request_datetime.isoformat()}")
        
        # Calculate temporal routes
        result = orchestrator.calculate_temporal_routes(
            start_latitude=args.start[0],
            start_longitude=args.start[1],
            end_latitude=args.end[0],
            end_longitude=args.end[1],
            request_datetime=request_datetime,
        )
        
        print(format_route_output(result))
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"\n❌ Error: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        print(f"\n❌ Error: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
