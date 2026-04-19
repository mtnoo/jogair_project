"""
Temporal Routing Orchestrator

Coordinates the workflow of integrating temporal air quality data with spatial routing.
This module handles user requests by:
1. Loading the city network graph
2. Loading historical air quality data
3. Fetching pollution value for user-requested time
4. Augmenting the graph with dynamic pollution costs
5. Computing route options (shortest distance vs. clean air)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, Optional, Union

from src.collectors.air_quality_loader import AirQualityDataLoader
from src.collectors.live_air_quality_loader import LiveAirQualityLoader
from src.collectors.pipeline.daily.routing_engine import (
    Route,
    add_pollution_costs_to_graph,
    calculate_routes,
    load_city_graph,
)

logger = logging.getLogger(__name__)


class RouteComparison(NamedTuple):
    """Comparison result for two routes."""

    shortest_distance_route: Route
    clean_air_route: Route
    pollution_value: float
    pollution_unit: str
    request_datetime: datetime
    matched_datetime: Optional[datetime]
    time_delta_seconds: Optional[int]
    out_of_range: bool
    data_source: str
    is_stale_data: bool


class TemporalRoutingOrchestrator:
    """
    Orchestrates temporal routing by integrating air quality data with route calculation.

    Supports multiple data sources:
    - 'csv': Historical data from CSV file (default)
    - 'live': Real-time data from Open-Meteo API with lazy loading

    This is the main entry point for users requesting routes at specific times.
    It handles:
    - Loading and caching the city graph (once)
    - Loading and caching air quality data (once for CSV, lazy for live)
    - Fetching pollution values for requested timestamps
    - Computing routes with dynamic pollution costs
    """

    def __init__(self, data_source: str = "csv"):
        """
        Initialize the orchestrator by loading graph and air quality data.

        Args:
            data_source: Data source to use ('csv' or 'live')

        Raises:
            FileNotFoundError: If graph or air quality data files are missing (CSV mode)
            ValueError: If data files have invalid structure or invalid data_source
        """
        if data_source not in ["csv", "live"]:
            raise ValueError(f"Invalid data_source: {data_source}. Must be 'csv' or 'live'")

        self.data_source = data_source
        logger.info(f"Initializing TemporalRoutingOrchestrator with {data_source} data source...")

        # Load and cache graph (done once at initialization)
        self.graph = load_city_graph()
        logger.info(f"Graph loaded: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")

        # Initialize air quality loader based on data source
        if data_source == "csv":
            self.air_quality_loader = AirQualityDataLoader()
            data_range = self.air_quality_loader.get_data_range()
            record_count = self.air_quality_loader.get_record_count()
            logger.info(
                f"CSV air quality data loaded: {record_count} records, "
                f"date range {data_range[0]} to {data_range[1]}"
            )
        elif data_source == "live":
            self.air_quality_loader = LiveAirQualityLoader()
            logger.info("Live air quality loader initialized (will fetch data on first request)")
    
    def calculate_temporal_routes(
        self,
        start_latitude: float,
        start_longitude: float,
        end_latitude: float,
        end_longitude: float,
        request_datetime: datetime,
    ) -> RouteComparison:
        """
        Calculate shortest distance and clean air routes for a specific time.
        
        This is the main public method. It:
        1. Fetches pollution value for the requested datetime
        2. Augments the graph with dynamic pollution costs
        3. Computes both shortest distance and clean air routes
        
        Args:
            start_latitude: Starting point latitude
            start_longitude: Starting point longitude
            end_latitude: Ending point latitude
            end_longitude: Ending point longitude
            request_datetime: Requested time for route calculation (any precision accepted)
        
        Returns:
            RouteComparison: Contains both routes, pollution value, and metadata
        
        Raises:
            ValueError: If coordinates are invalid or route cannot be calculated
            nx.NetworkXNoPath: If no path exists between start and end
        
        Example:
            >>> orchestrator = TemporalRoutingOrchestrator()
            >>> result = orchestrator.calculate_temporal_routes(
            ...     start_latitude=56.1552,
            ...     start_longitude=10.2082,
            ...     end_latitude=56.1571,
            ...     end_longitude=10.2112,
            ...     request_datetime=datetime(2026, 3, 15, 14, 30)
            ... )
            >>> print(f"Shortest: {result.shortest_distance_route.distance_m}m")
            >>> print(f"Clean Air: {result.clean_air_route.distance_m}m")
        """
        logger.info(
            f"Calculating temporal routes for {request_datetime.isoformat()} "
            f"from ({start_latitude}, {start_longitude}) to ({end_latitude}, {end_longitude})"
        )
        
        # Validate coordinates
        if not (-90 <= start_latitude <= 90 and -180 <= start_longitude <= 180):
            raise ValueError(f"Invalid start coordinates: ({start_latitude}, {start_longitude})")
        if not (-90 <= end_latitude <= 90 and -180 <= end_longitude <= 180):
            raise ValueError(f"Invalid end coordinates: ({end_latitude}, {end_longitude})")
        
        # Fetch pollution value for requested time
        pollution_data = self.air_quality_loader.get_pollution_at_time(request_datetime)
        pollution_value = pollution_data["pm2_5"]  # Use PM2.5 as primary pollutant
        matched_datetime = pollution_data["timestamp"]
        time_delta_seconds = pollution_data["time_delta"]
        out_of_range = pollution_data["out_of_range"]
        is_stale_data = pollution_data.get("is_stale", False)
        
        logger.info(
            f"Matched pollution data: PM2.5={pollution_value:.1f} µg/m³ "
            f"at {matched_datetime} (delta: {time_delta_seconds}s)"
        )
        
        # Create a working copy of the graph and augment with pollution costs
        # Note: We augment a copy to avoid modifying the cached graph
        import networkx as nx
        graph_copy = self.graph.copy()
        add_pollution_costs_to_graph(graph_copy, pollution_value=pollution_value)
        
        # Calculate routes
        shortest_route, clean_air_route = calculate_routes(
            graph_copy,
            start_latitude,
            start_longitude,
            end_latitude,
            end_longitude,
        )
        
        logger.info(
            f"Routes calculated: Shortest {shortest_route.distance_m:.0f}m, "
            f"Clean Air {clean_air_route.distance_m:.0f}m"
        )
        
        return RouteComparison(
            shortest_distance_route=shortest_route,
            clean_air_route=clean_air_route,
            pollution_value=pollution_value,
            pollution_unit="µg/m³",
            request_datetime=request_datetime,
            matched_datetime=matched_datetime,
            time_delta_seconds=time_delta_seconds,
            out_of_range=out_of_range,
            data_source=self.data_source,
            is_stale_data=is_stale_data,
        )
    
    def get_data_info(self) -> dict:
        """
        Get information about loaded data.

        Returns:
            Dictionary with:
                - graph_nodes: Number of nodes in the network
                - graph_edges: Number of edges in the network
                - air_quality_records: Number of air quality observations
                - air_quality_date_range: (earliest_datetime, latest_datetime) tuple or None
                - data_source: 'csv' or 'live'
                - cache_status: Cache information (for live data only)
        """
        data_range = self.air_quality_loader.get_data_range()
        info = {
            "graph_nodes": len(self.graph.nodes),
            "graph_edges": len(self.graph.edges),
            "air_quality_records": self.air_quality_loader.get_record_count(),
            "air_quality_date_range": data_range,
            "data_source": self.data_source,
        }

        # Add cache status for live data
        if self.data_source == "live" and hasattr(self.air_quality_loader, 'get_cache_status'):
            info["cache_status"] = self.air_quality_loader.get_cache_status()

        return info
