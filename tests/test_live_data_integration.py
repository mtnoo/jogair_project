"""
Integration Tests for Live Data Temporal Routing

Tests the integration between live air quality data and temporal routing,
ensuring the orchestrator works correctly with live data sources.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.collectors.pipeline.temporal_routing_orchestrator import TemporalRoutingOrchestrator


class TestLiveDataTemporalRoutingIntegration:
    """Integration tests for live data temporal routing."""

    @pytest.fixture
    def mock_api_response(self):
        """Mock API response with realistic air quality data."""
        return {
            "hourly": {
                "time": [
                    "2026-04-18T00:00:00Z",
                    "2026-04-18T01:00:00Z",
                    "2026-04-18T02:00:00Z",
                    "2026-04-18T03:00:00Z",
                ],
                "pm2_5": [5.2, 4.8, 6.1, 7.3],
                "nitrogen_dioxide": [12.3, 11.8, 13.2, 14.5],
            }
        }

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_orchestrator_initialization_live_data(self, mock_get, mock_api_response):
        """Test orchestrator initialization with live data source."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Initialize orchestrator with live data
        orchestrator = TemporalRoutingOrchestrator(data_source="live")

        # Verify data source
        assert orchestrator.data_source == "live"
        assert hasattr(orchestrator.air_quality_loader, 'cache_df')

        # Verify graph is loaded
        assert orchestrator.graph is not None
        assert len(orchestrator.graph.nodes) > 0
        assert len(orchestrator.graph.edges) > 0

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_calculate_temporal_routes_live_data(self, mock_get, mock_api_response):
        """Test route calculation with live air quality data."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Initialize orchestrator
        orchestrator = TemporalRoutingOrchestrator(data_source="live")

        # Calculate routes
        request_time = datetime(2026, 4, 18, 1, 30)  # 1:30 AM
        result = orchestrator.calculate_temporal_routes(
            start_latitude=56.1552,
            start_longitude=10.2082,
            end_latitude=56.1571,
            end_longitude=10.2112,
            request_datetime=request_time
        )

        # Verify result structure
        assert result.shortest_distance_route is not None
        assert result.clean_air_route is not None
        assert isinstance(result.pollution_value, float)
        assert result.pollution_unit == "µg/m³"
        assert result.request_datetime == request_time
        assert result.matched_datetime is not None
        assert isinstance(result.time_delta_seconds, int)
        assert isinstance(result.out_of_range, bool)
        assert result.data_source == "live"

        # Verify pollution value is from live data (should be 4.8 for 01:00 timestamp)
        assert result.pollution_value == 4.8

        # Verify routes have valid data
        shortest = result.shortest_distance_route
        clean = result.clean_air_route

        assert shortest.distance_m > 0
        assert clean.distance_m > 0
        assert len(shortest.node_ids) > 0
        assert len(clean.node_ids) > 0

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_calculate_long_live_route(self, mock_get, mock_api_response):
        """Test live route calculation for the Dokk1 → Marselisborg Forest route."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        orchestrator = TemporalRoutingOrchestrator(data_source="live")
        result = orchestrator.calculate_temporal_routes(
            start_latitude=56.1533,
            start_longitude=10.2144,
            end_latitude=56.1365,
            end_longitude=10.2050,
            request_datetime=datetime(2026, 4, 18, 2, 15)
        )

        assert result.data_source == "live"
        assert result.pollution_value == 6.1
        assert result.shortest_distance_route.distance_m > 0
        assert result.clean_air_route.distance_m > 0
        assert result.clean_air_route.distance_m >= result.shortest_distance_route.distance_m
        assert len(result.shortest_distance_route.node_ids) > 0
        assert len(result.clean_air_route.node_ids) > 0

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_get_data_info_live_data(self, mock_get, mock_api_response):
        """Test data info retrieval with live data."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Initialize orchestrator
        orchestrator = TemporalRoutingOrchestrator(data_source="live")

        # Trigger lazy loading by making a route request
        result = orchestrator.calculate_temporal_routes(
            start_latitude=56.1552,
            start_longitude=10.2082,
            end_latitude=56.1571,
            end_longitude=10.2112,
            request_datetime=datetime(2026, 4, 18, 1, 0)
        )

        # Now check data info after data has been loaded
        info = orchestrator.get_data_info()

        # Verify basic structure
        assert 'graph_nodes' in info
        assert 'graph_edges' in info
        assert 'air_quality_records' in info
        assert 'air_quality_date_range' in info
        assert 'data_source' in info
        assert 'cache_status' in info

        # Verify data source
        assert info['data_source'] == 'live'

        # Verify cache status
        cache = info['cache_status']
        assert 'cache_valid' in cache
        assert 'last_fetch' in cache
        assert 'record_count' in cache
        assert 'cache_age_minutes' in cache

        # Verify record count after loading
        assert info['air_quality_records'] == 4

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_live_data_caching_behavior(self, mock_get, mock_api_response):
        """Test that live data is cached and reused."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Initialize orchestrator
        orchestrator = TemporalRoutingOrchestrator(data_source="live")

        # First request - should call API
        result1 = orchestrator.calculate_temporal_routes(
            start_latitude=56.1552,
            start_longitude=10.2082,
            end_latitude=56.1571,
            end_longitude=10.2112,
            request_datetime=datetime(2026, 4, 18, 1, 0)
        )

        # Second request - should use cache
        result2 = orchestrator.calculate_temporal_routes(
            start_latitude=56.1552,
            start_longitude=10.2082,
            end_latitude=56.1571,
            end_longitude=10.2112,
            request_datetime=datetime(2026, 4, 18, 2, 0)
        )

        # Verify API was called only once
        assert mock_get.call_count == 1

        # Verify both results are valid
        assert result1.pollution_value == 4.8  # 01:00
        assert result2.pollution_value == 6.1  # 02:00

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_live_data_different_pollution_levels(self, mock_get, mock_api_response):
        """Test route calculation with different pollution levels from live data."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Initialize orchestrator
        orchestrator = TemporalRoutingOrchestrator(data_source="live")

        # Test with lower pollution (4.8 µg/m³ at 01:00)
        result_low = orchestrator.calculate_temporal_routes(
            start_latitude=56.1552,
            start_longitude=10.2082,
            end_latitude=56.1571,
            end_longitude=10.2112,
            request_datetime=datetime(2026, 4, 18, 1, 0)
        )

        # Test with higher pollution (7.3 µg/m³ at 03:00)
        result_high = orchestrator.calculate_temporal_routes(
            start_latitude=56.1552,
            start_longitude=10.2082,
            end_latitude=56.1571,
            end_longitude=10.2112,
            request_datetime=datetime(2026, 4, 18, 3, 0)
        )

        # Verify different pollution values
        assert result_low.pollution_value == 4.8
        assert result_high.pollution_value == 7.3

        # Verify both routes are calculated
        assert result_low.shortest_distance_route.distance_m > 0
        assert result_high.shortest_distance_route.distance_m > 0

        # Note: In a real scenario, higher pollution might result in different routes,
        # but with the current test coordinates and graph, routes might be the same.
        # The important thing is that different pollution values are being used.

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_live_data_fallback_on_api_failure(self, mock_get):
        """Test fallback behavior when live API fails."""
        # Mock API failure
        mock_get.side_effect = Exception("API unavailable")

        # Initialize orchestrator
        orchestrator = TemporalRoutingOrchestrator(data_source="live")

        # Calculate routes - should use fallback pollution value
        result = orchestrator.calculate_temporal_routes(
            start_latitude=56.1552,
            start_longitude=10.2082,
            end_latitude=56.1571,
            end_longitude=10.2112,
            request_datetime=datetime(2026, 4, 18, 12, 0)
        )

        # Verify fallback behavior
        assert result.pollution_value == 1.0  # Fallback value
        assert result.out_of_range is True
        assert result.data_source == "live"

        # Verify routes are still calculated with fallback value
        assert result.shortest_distance_route is not None
        assert result.clean_air_route is not None

    def test_invalid_data_source(self):
        """Test error handling for invalid data source."""
        with pytest.raises(ValueError, match="Invalid data_source"):
            TemporalRoutingOrchestrator(data_source="invalid")

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_live_data_info_display(self, mock_get, mock_api_response, capsys):
        """Test that live data info displays correctly."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Initialize orchestrator
        orchestrator = TemporalRoutingOrchestrator(data_source="live")

        # Trigger data loading
        result = orchestrator.calculate_temporal_routes(
            start_latitude=56.1552,
            start_longitude=10.2082,
            end_latitude=56.1571,
            end_longitude=10.2112,
            request_datetime=datetime(2026, 4, 18, 1, 0)
        )

        # Get data info after loading
        info = orchestrator.get_data_info()

        # Verify cache status is included
        assert 'cache_status' in info
        cache = info['cache_status']
        assert cache['record_count'] == 4
        assert cache['cache_valid'] is True