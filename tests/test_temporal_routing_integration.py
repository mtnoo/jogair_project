"""Integration tests for temporal routing orchestrator."""

import pytest
from datetime import datetime

from src.collectors.pipeline.temporal_routing_orchestrator import (
    TemporalRoutingOrchestrator,
    RouteComparison,
)


class TestTemporalRoutingOrchestratorInitialization:
    """Test orchestrator initialization."""
    
    def test_orchestrator_initializes(self):
        """Test that orchestrator initializes without errors."""
        orchestrator = TemporalRoutingOrchestrator()
        
        assert orchestrator is not None
        assert orchestrator.graph is not None
        assert orchestrator.air_quality_loader is not None
    
    def test_graph_is_loaded(self):
        """Test that graph is properly loaded."""
        orchestrator = TemporalRoutingOrchestrator()
        
        assert len(orchestrator.graph.nodes) > 0
        assert len(orchestrator.graph.edges) > 0
        # From exploration, we know the Aarhus network has thousands of nodes/edges
        assert len(orchestrator.graph.nodes) > 1000
        assert len(orchestrator.graph.edges) > 2000
    
    def test_air_quality_data_is_loaded(self):
        """Test that air quality data is properly loaded."""
        orchestrator = TemporalRoutingOrchestrator()
        
        record_count = orchestrator.air_quality_loader.get_record_count()
        assert record_count > 750


class TestTemporalRoutingOrchestratorDataInfo:
    """Test data info retrieval."""
    
    def test_get_data_info(self):
        """Test that data info is returned correctly."""
        orchestrator = TemporalRoutingOrchestrator()
        info = orchestrator.get_data_info()
        
        assert "graph_nodes" in info
        assert "graph_edges" in info
        assert "air_quality_records" in info
        assert "air_quality_date_range" in info
        
        assert info["graph_nodes"] > 0
        assert info["graph_edges"] > 0
        assert info["air_quality_records"] > 0
        
        start_date, end_date = info["air_quality_date_range"]
        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        assert start_date < end_date


class TestTemporalRoutingOrchestratorRoutCalculation:
    """Test route calculation with temporal data."""
    
    # Aarhus test coordinates
    # Start: Varna Square (56.1552, 10.2082)
    # End: Aarhus Cathedral (56.1571, 10.2112)
    START_LAT = 56.1552
    START_LON = 10.2082
    END_LAT = 56.1571
    END_LON = 10.2112
    
    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator instance for testing."""
        return TemporalRoutingOrchestrator()
    
    def test_calculate_routes_with_valid_time(self, orchestrator):
        """Test route calculation with a valid time in data range."""
        # Use a time in the middle of the data range (March 15, 2026)
        request_time = datetime(2026, 3, 15, 14, 30)
        
        result = orchestrator.calculate_temporal_routes(
            self.START_LAT,
            self.START_LON,
            self.END_LAT,
            self.END_LON,
            request_time,
        )
        
        assert isinstance(result, RouteComparison)
        assert result.shortest_distance_route is not None
        assert result.clean_air_route is not None
    
    def test_route_comparison_structure(self, orchestrator):
        """Test that route comparison has expected structure."""
        request_time = datetime(2026, 3, 15, 14, 30)
        
        result = orchestrator.calculate_temporal_routes(
            self.START_LAT,
            self.START_LON,
            self.END_LAT,
            self.END_LON,
            request_time,
        )
        
        # Check all expected attributes
        assert hasattr(result, 'shortest_distance_route')
        assert hasattr(result, 'clean_air_route')
        assert hasattr(result, 'pollution_value')
        assert hasattr(result, 'pollution_unit')
        assert hasattr(result, 'request_datetime')
        assert hasattr(result, 'matched_datetime')
        assert hasattr(result, 'time_delta_seconds')
        assert hasattr(result, 'out_of_range')
        
        # Check types
        assert isinstance(result.pollution_value, float)
        assert isinstance(result.pollution_unit, str)
        assert isinstance(result.request_datetime, datetime)
        assert isinstance(result.matched_datetime, datetime)
        assert isinstance(result.time_delta_seconds, int)
        assert isinstance(result.out_of_range, bool)
    
    def test_routes_have_valid_geometry(self, orchestrator):
        """Test that calculated routes have valid node lists."""
        request_time = datetime(2026, 3, 15, 14, 30)
        
        result = orchestrator.calculate_temporal_routes(
            self.START_LAT,
            self.START_LON,
            self.END_LAT,
            self.END_LON,
            request_time,
        )
        
        # Both routes should have node lists
        assert len(result.shortest_distance_route.node_ids) > 0
        assert len(result.clean_air_route.node_ids) > 0
        
        # Routes should have reasonable lengths (at least 2 nodes)
        assert len(result.shortest_distance_route.node_ids) >= 2
        assert len(result.clean_air_route.node_ids) >= 2
    
    def test_routes_have_positive_distances(self, orchestrator):
        """Test that routes have positive distance values."""
        request_time = datetime(2026, 3, 15, 14, 30)
        
        result = orchestrator.calculate_temporal_routes(
            self.START_LAT,
            self.START_LON,
            self.END_LAT,
            self.END_LON,
            request_time,
        )
        
        assert result.shortest_distance_route.distance_m > 0
        assert result.clean_air_route.distance_m > 0
    
    def test_pollution_value_is_retrieved(self, orchestrator):
        """Test that pollution value is properly retrieved."""
        request_time = datetime(2026, 3, 15, 14, 30)
        
        result = orchestrator.calculate_temporal_routes(
            self.START_LAT,
            self.START_LON,
            self.END_LAT,
            self.END_LON,
            request_time,
        )
        
        # Pollution value should be reasonable (typical PM2.5 range)
        assert 0 < result.pollution_value <= 200
        assert result.pollution_unit == "µg/m³"
    
    def test_matched_datetime_is_in_data_range(self, orchestrator):
        """Test that matched datetime falls within data range."""
        request_time = datetime(2026, 3, 15, 14, 30)
        
        result = orchestrator.calculate_temporal_routes(
            self.START_LAT,
            self.START_LON,
            self.END_LAT,
            self.END_LON,
            request_time,
        )
        
        start_date, end_date = orchestrator.air_quality_loader.get_data_range()
        assert start_date <= result.matched_datetime <= end_date
    
    def test_time_delta_is_reasonable(self, orchestrator):
        """Test that time delta between request and match is reasonable."""
        request_time = datetime(2026, 3, 15, 14, 30)
        
        result = orchestrator.calculate_temporal_routes(
            self.START_LAT,
            self.START_LON,
            self.END_LAT,
            self.END_LON,
            request_time,
        )
        
        # Should match within ~30 minutes (1800 seconds) for hourly data
        assert 0 <= result.time_delta_seconds <= 1800
    
    def test_out_of_range_detection(self, orchestrator):
        """Test detection of out-of-range times."""
        # Request time far before data range
        request_time = datetime(2025, 1, 1, 12, 0)
        
        result = orchestrator.calculate_temporal_routes(
            self.START_LAT,
            self.START_LON,
            self.END_LAT,
            self.END_LON,
            request_time,
        )
        
        assert result.out_of_range is True
        assert result.matched_datetime is None
        # Fallback pollution value should be used
        assert result.pollution_value == 1.0


class TestTemporalRoutingOrchestratorInputValidation:
    """Test input validation."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator instance for testing."""
        return TemporalRoutingOrchestrator()
    
    def test_invalid_start_latitude(self, orchestrator):
        """Test error handling for invalid start latitude."""
        with pytest.raises(ValueError):
            orchestrator.calculate_temporal_routes(
                start_latitude=91.0,  # Invalid, latitude range is -90 to 90
                start_longitude=10.2,
                end_latitude=56.15,
                end_longitude=10.21,
                request_datetime=datetime(2026, 3, 15),
            )
    
    def test_invalid_start_longitude(self, orchestrator):
        """Test error handling for invalid start longitude."""
        with pytest.raises(ValueError):
            orchestrator.calculate_temporal_routes(
                start_latitude=56.15,
                start_longitude=181.0,  # Invalid, longitude range is -180 to 180
                end_latitude=56.15,
                end_longitude=10.21,
                request_datetime=datetime(2026, 3, 15),
            )
    
    def test_invalid_end_coordinates(self, orchestrator):
        """Test error handling for invalid end coordinates."""
        with pytest.raises(ValueError):
            orchestrator.calculate_temporal_routes(
                start_latitude=56.15,
                start_longitude=10.2,
                end_latitude=-91.0,  # Invalid
                end_longitude=10.21,
                request_datetime=datetime(2026, 3, 15),
            )


class TestTemporalRoutingOrchestratorPollutionEffects:
    """Test that pollution values affect route selection."""
    
    START_LAT = 56.1552
    START_LON = 10.2082
    END_LAT = 56.1571
    END_LON = 10.2112
    
    def test_routes_differ_by_pollution_level(self):
        """Test that routes can differ based on pollution levels."""
        orchestrator = TemporalRoutingOrchestrator()
        
        # Low pollution period (e.g., mid-April, spring)
        low_pollution_time = datetime(2026, 4, 5, 12, 0)
        result_low = orchestrator.calculate_temporal_routes(
            self.START_LAT,
            self.START_LON,
            self.END_LAT,
            self.END_LON,
            low_pollution_time,
        )
        
        # High pollution period (e.g., mid-March)
        high_pollution_time = datetime(2026, 3, 12, 12, 0)
        result_high = orchestrator.calculate_temporal_routes(
            self.START_LAT,
            self.START_LON,
            self.END_LAT,
            self.END_LON,
            high_pollution_time,
        )
        
        # Pollution values should be different
        assert result_low.pollution_value != result_high.pollution_value
        
        # At high pollution, clean air route costs should increase relative to distance
        # (more penalty for using high-pollution roads)
        assert result_high.pollution_value > result_low.pollution_value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
