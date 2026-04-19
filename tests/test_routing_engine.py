"""Unit tests for routing engine."""

import pytest
import networkx as nx

from src.collectors.pipeline.daily.routing_engine import (
    add_pollution_costs_to_graph,
    Route,
    POLLUTION_MULTIPLIERS,
    DEFAULT_MULTIPLIER,
)


class TestAddPollutionCostsToGraph:
    """Test pollution cost calculation and application."""
    
    @pytest.fixture
    def simple_graph(self):
        """Create a simple test graph with known edges."""
        G = nx.MultiDiGraph()
        
        # Add edges with known properties
        # Edge 1: residential, 100m
        G.add_edge(1, 2, key=0, highway="residential", length=100.0)
        
        # Edge 2: primary, 500m
        G.add_edge(2, 3, key=0, highway="primary", length=500.0)
        
        # Edge 3: footway, 50m
        G.add_edge(3, 4, key=0, highway="footway", length=50.0)
        
        # Edge 4: unknown type (should use default multiplier)
        G.add_edge(4, 5, key=0, highway="unknown_type", length=200.0)
        
        # Edge 5: no highway type specified (should use default)
        G.add_edge(5, 6, key=0, length=150.0)
        
        return G
    
    def test_pollution_costs_added(self, simple_graph):
        """Test that pollution_cost attributes are added to all edges."""
        G = simple_graph
        
        # Before augmentation, edges should not have pollution_cost
        for u, v, key, data in G.edges(keys=True, data=True):
            assert "pollution_cost" not in data
        
        # Augment with pollution value
        add_pollution_costs_to_graph(G, pollution_value=1.0)
        
        # After augmentation, all edges should have pollution_cost
        for u, v, key, data in G.edges(keys=True, data=True):
            assert "pollution_cost" in data
            assert isinstance(data["pollution_cost"], (float, int))
            assert data["pollution_cost"] > 0
    
    def test_pollution_cost_formula(self, simple_graph):
        """Test that pollution cost is calculated correctly."""
        G = simple_graph
        pollution_value = 2.0
        
        add_pollution_costs_to_graph(G, pollution_value=pollution_value)
        
        # Check Edge 1: residential, 100m, multiplier=1.0
        edge1_data = G[1][2][0]
        expected_cost = 100.0 * (pollution_value * POLLUTION_MULTIPLIERS["residential"])
        assert edge1_data["pollution_cost"] == expected_cost
        
        # Check Edge 2: primary, 500m, multiplier=2.0
        edge2_data = G[2][3][0]
        expected_cost = 500.0 * (pollution_value * POLLUTION_MULTIPLIERS["primary"])
        assert edge2_data["pollution_cost"] == expected_cost
        
        # Check Edge 3: footway, 50m, multiplier=0.6
        edge3_data = G[3][4][0]
        expected_cost = 50.0 * (pollution_value * POLLUTION_MULTIPLIERS["footway"])
        assert edge3_data["pollution_cost"] == expected_cost
    
    def test_unknown_highway_type_uses_default(self, simple_graph):
        """Test that unknown highway types use the default multiplier."""
        G = simple_graph
        pollution_value = 1.0
        
        add_pollution_costs_to_graph(G, pollution_value=pollution_value)
        
        # Edge 4: unknown type
        edge4_data = G[4][5][0]
        expected_cost = 200.0 * (pollution_value * DEFAULT_MULTIPLIER)
        assert edge4_data["pollution_cost"] == expected_cost
    
    def test_missing_length_uses_default(self, simple_graph):
        """Test that missing length values use a default."""
        G = simple_graph
        
        # Edge 5 has no highway type and default length should be used
        edge5_data_before = G[5][6][0]
        assert edge5_data_before.get("length", 100) == 150.0
        
        pollution_value = 1.0
        add_pollution_costs_to_graph(G, pollution_value=pollution_value)
        
        # After augmentation, should calculate cost with 150m length
        edge5_data = G[5][6][0]
        expected_cost = 150.0 * (pollution_value * DEFAULT_MULTIPLIER)
        assert edge5_data["pollution_cost"] == expected_cost
    
    def test_different_pollution_values_scale_costs(self, simple_graph):
        """Test that increasing pollution value scales pollution costs."""
        G1 = simple_graph.copy()
        G2 = simple_graph.copy()
        
        add_pollution_costs_to_graph(G1, pollution_value=1.0)
        add_pollution_costs_to_graph(G2, pollution_value=2.0)
        
        # Costs in G2 should be exactly 2x the costs in G1
        for (u1, v1, k1), (u2, v2, k2) in zip(
            G1.edges(keys=True), G2.edges(keys=True)
        ):
            cost1 = G1[u1][v1][k1]["pollution_cost"]
            cost2 = G2[u2][v2][k2]["pollution_cost"]
            assert cost2 == pytest.approx(2.0 * cost1)
    
    def test_zero_pollution_value(self, simple_graph):
        """Test edge case with zero pollution value."""
        G = simple_graph
        
        add_pollution_costs_to_graph(G, pollution_value=0.0)
        
        # All pollution costs should be zero
        for u, v, key, data in G.edges(keys=True, data=True):
            assert data["pollution_cost"] == 0.0
    
    def test_highway_type_as_list(self, simple_graph):
        """Test handling of highway type specified as list."""
        G = nx.MultiDiGraph()
        
        # osmnx can sometimes return highway as a list
        G.add_edge(1, 2, key=0, highway=["primary", "secondary"], length=100.0)
        
        add_pollution_costs_to_graph(G, pollution_value=1.0)
        
        # Should use first item in list
        edge_data = G[1][2][0]
        expected_cost = 100.0 * (1.0 * POLLUTION_MULTIPLIERS["primary"])
        assert edge_data["pollution_cost"] == expected_cost
    
    def test_default_pollution_value(self, simple_graph):
        """Test that default pollution value is 1.0 when not specified."""
        G = simple_graph
        
        # Call without specifying pollution_value
        add_pollution_costs_to_graph(G)
        
        # Should use default 1.0
        for u, v, key, data in G.edges(keys=True, data=True):
            assert "pollution_cost" in data
            assert data["pollution_cost"] > 0


class TestRouteNamedTuple:
    """Test Route named tuple."""
    
    def test_route_creation(self):
        """Test creating a Route object."""
        node_ids = [1, 2, 3, 4, 5]
        distance = 500.0
        description = "Test route"
        
        route = Route(
            node_ids=node_ids,
            distance_m=distance,
            description=description,
        )
        
        assert route.node_ids == node_ids
        assert route.distance_m == distance
        assert route.description == description
    
    def test_route_is_immutable(self):
        """Test that Route is immutable (NamedTuple property)."""
        route = Route(node_ids=[1, 2, 3], distance_m=100.0, description="Test")
        
        # Should not be able to modify attributes
        with pytest.raises(AttributeError):
            route.distance_m = 200.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
