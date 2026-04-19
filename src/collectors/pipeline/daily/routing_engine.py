"""JogAir routing engine: calculate clean air and shortest distance routes."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import NamedTuple

import networkx as nx
import osmnx as ox


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Pollution multipliers by OpenStreetMap highway type
POLLUTION_MULTIPLIERS = {
    "primary": 2.0,
    "primary_link": 1.9,
    "secondary": 1.5,
    "secondary_link": 1.4,
    "tertiary": 1.2,
    "tertiary_link": 1.1,
    "residential": 1.0,
    "living_street": 0.8,
    "footway": 0.6,
    "path": 0.5,
    "pedestrian": 0.5,
    "park": 0.4,
    "track": 0.5,
}

DEFAULT_MULTIPLIER = 1.0  # Fallback for unmapped highway types


class Route(NamedTuple):
    """A route represented as a list of node IDs."""

    node_ids: list[int]
    distance_m: float
    description: str


def load_city_graph() -> nx.MultiDiGraph:
    """Load the Aarhus pedestrian street graph from GraphML.

    Returns:
        networkx.MultiDiGraph: The loaded street network graph.

    Raises:
        FileNotFoundError: If the GraphML file does not exist.
    """
    # Resolve path relative to this script
    project_root = Path(__file__).resolve().parents[4]
    graph_path = project_root / "data" / "processed" / "aarhus_walk_network.graphml"

    if not graph_path.exists():
        raise FileNotFoundError(f"Graph file not found at {graph_path}")

    logger.info("Loading city graph from %s", graph_path)
    graph = ox.load_graphml(graph_path)
    logger.info("Graph loaded: %s nodes, %s edges", len(graph.nodes), len(graph.edges))

    return graph


def add_pollution_costs_to_graph(graph: nx.MultiDiGraph, pollution_value: float = 1.0) -> None:
    """Add pollution_cost attribute to all edges based on highway type and length.

    The pollution_cost combines the edge length with a highway-type multiplier.
    This allows routes to prefer quieter, less-polluted street types.

    Args:
        graph: The street network graph to augment.
        pollution_value: Base pollution value for calculating costs (default: 1.0).
            In future versions, this can be adjusted based on real-time air quality data
            (e.g., from DMI API) to dynamically reflect current pollution conditions.
    """
    logger.info("Calculating pollution costs for %s edges...", len(graph.edges))

    for u, v, key, data in graph.edges(keys=True, data=True):
        # Get the edge length in meters
        length = data.get("length", 100)  # Default to 100m if missing

        # Get the highway type and its multiplier
        highway_type = data.get("highway", "residential")

        # Handle cases where highway is a list (osmnx can do this)
        if isinstance(highway_type, list):
            highway_type = highway_type[0]

        multiplier = POLLUTION_MULTIPLIERS.get(highway_type, DEFAULT_MULTIPLIER)

        # Calculate pollution cost
        pollution_cost = length * (pollution_value * multiplier)

        # Add to edge attributes
        graph[u][v][key]["pollution_cost"] = pollution_cost

    logger.info("Pollution costs calculated for all edges.")


def calculate_routes(
    graph: nx.MultiDiGraph, start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> tuple[Route, Route]:
    """Calculate shortest distance and clean air routes between two points.

    Args:
        graph: The street network graph.
        start_lat: Starting latitude.
        start_lon: Starting longitude.
        end_lat: Ending latitude.
        end_lon: Ending longitude.

    Returns:
        tuple[Route, Route]: (shortest_distance_route, clean_air_route)

    Raises:
        nx.NetworkXNoPath: If no path exists between start and end nodes.
    """
    logger.info("Calculating routes from (%.4f, %.4f) to (%.4f, %.4f)", start_lat, start_lon, end_lat, end_lon)

    # Find nearest nodes to the input coordinates
    start_node = ox.nearest_nodes(graph, start_lon, start_lat)
    end_node = ox.nearest_nodes(graph, end_lon, end_lat)
    logger.info("Start node: %s, End node: %s", start_node, end_node)

    # Calculate shortest distance route
    start_time = time.time()
    shortest_path = nx.shortest_path(graph, start_node, end_node, weight="length")
    shortest_time = time.time() - start_time

    # Calculate total distance for shortest path
    shortest_distance = 0.0
    for i in range(len(shortest_path) - 1):
        u, v = shortest_path[i], shortest_path[i + 1]
        # Safely get the shortest edge (handles MultiDiGraph with multiple keys)
        edge_data = min(graph[u][v].values(), key=lambda x: x.get("length", float("inf")))
        shortest_distance += edge_data.get("length", 0)

    shortest_route = Route(
        node_ids=shortest_path,
        distance_m=shortest_distance,
        description=f"Shortest Distance ({len(shortest_path)} nodes, {shortest_distance:.0f}m)",
    )
    logger.info(
        "Shortest path calculated in %.2fs: %s nodes, %.0f meters",
        shortest_time,
        len(shortest_path),
        shortest_distance,
    )

    # Calculate clean air route
    start_time = time.time()
    clean_path = nx.shortest_path(graph, start_node, end_node, weight="pollution_cost")
    clean_time = time.time() - start_time

    # Calculate total pollution cost and distance for clean path
    clean_distance = 0.0
    clean_pollution_cost = 0.0
    for i in range(len(clean_path) - 1):
        u, v = clean_path[i], clean_path[i + 1]
        # Safely get the shortest edge (handles MultiDiGraph with multiple keys)
        edge_data = min(graph[u][v].values(), key=lambda x: x.get("length", float("inf")))
        clean_distance += edge_data.get("length", 0)
        clean_pollution_cost += edge_data.get("pollution_cost", 0)

    clean_air_route = Route(
        node_ids=clean_path,
        distance_m=clean_distance,
        description=f"Clean Air ({len(clean_path)} nodes, {clean_distance:.0f}m, pollution cost: {clean_pollution_cost:.0f})",
    )
    logger.info(
        "Clean air path calculated in %.2fs: %s nodes, %.0f meters, pollution cost: %.0f",
        clean_time,
        len(clean_path),
        clean_distance,
        clean_pollution_cost,
    )

    return shortest_route, clean_air_route


if __name__ == "__main__":
    # Load the graph
    graph = load_city_graph()

    # Add pollution costs to all edges
    add_pollution_costs_to_graph(graph, pollution_value=1.0)

    # Test routes with dummy Aarhus coordinates
    # Start: Varna Square (56.1552, 10.2082)
    # End: Aarhus Cathedral (56.1571, 10.2112)
    start_lat, start_lon = 56.1552, 10.2082
    end_lat, end_lon = 56.1571, 10.2112

    shortest, clean = calculate_routes(graph, start_lat, start_lon, end_lat, end_lon)

    print("\n" + "=" * 70)
    print("ROUTE COMPARISON")
    print("=" * 70)
    print(f"Shortest Distance Route: {shortest.description}")
    print(f"Clean Air Route:        {clean.description}")
    if shortest.distance_m > 0:
        distance_diff_pct = (clean.distance_m / shortest.distance_m - 1) * 100
        print(f"\nDistance difference: {clean.distance_m - shortest.distance_m:.0f}m ({distance_diff_pct:.1f}% longer)")
    else:
        print(f"\nDistance difference: {clean.distance_m - shortest.distance_m:.0f}m")
    print("=" * 70 + "\n")
