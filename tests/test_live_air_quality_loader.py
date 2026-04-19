"""
Tests for Live Air Quality Loader

Tests the LiveAirQualityLoader class which fetches real-time air quality data
from the Open-Meteo API with lazy loading and caching.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pandas as pd

from src.collectors.live_air_quality_loader import LiveAirQualityLoader


class TestLiveAirQualityLoader:
    """Test suite for LiveAirQualityLoader."""

    @pytest.fixture
    def loader(self):
        """Create a fresh loader instance for each test."""
        return LiveAirQualityLoader()

    @pytest.fixture
    def mock_api_response(self):
        """Mock API response data."""
        return {
            "hourly": {
                "time": [
                    "2026-04-18T00:00:00Z",
                    "2026-04-18T01:00:00Z",
                    "2026-04-18T02:00:00Z",
                ],
                "pm2_5": [5.2, 4.8, 6.1],
                "nitrogen_dioxide": [12.3, 11.8, 13.2],
            }
        }

    def test_initialization(self, loader):
        """Test loader initializes with empty cache."""
        assert loader.cache_df is None
        assert loader.last_fetch_time is None
        assert loader.data_range is None

    def test_is_cache_valid_empty_cache(self, loader):
        """Test cache validity with empty cache."""
        assert not loader._is_cache_valid()

    def test_is_cache_valid_expired_cache(self, loader):
        """Test cache validity with expired cache."""
        # Set cache with old timestamp
        loader.last_fetch_time = datetime.now() - timedelta(hours=2)
        assert not loader._is_cache_valid()

    def test_is_cache_valid_valid_cache(self, loader):
        """Test cache validity with valid cache."""
        # Set cache with recent timestamp and some data
        loader.last_fetch_time = datetime.now() - timedelta(minutes=30)
        loader.cache_df = pd.DataFrame({'timestamp': [datetime.now()], 'pm2_5': [5.0], 'no2': [10.0]})
        assert loader._is_cache_valid()

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_fetch_live_data_success(self, mock_get, loader, mock_api_response):
        """Test successful API data fetch."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Fetch data
        loader._fetch_live_data()

        # Verify cache is populated
        assert loader.cache_df is not None
        assert loader.last_fetch_time is not None
        assert loader.data_range is not None

        # Verify data structure
        assert len(loader.cache_df) == 3
        assert list(loader.cache_df.columns) == ['timestamp', 'pm2_5', 'no2']
        assert loader.cache_df['pm2_5'].iloc[0] == 5.2
        assert loader.cache_df['no2'].iloc[0] == 12.3

        # Verify data range (should be naive datetimes now)
        expected_start = pd.to_datetime("2026-04-18T00:00:00")
        expected_end = pd.to_datetime("2026-04-18T02:00:00")
        assert loader.data_range[0] == expected_start.to_pydatetime()
        assert loader.data_range[1] == expected_end.to_pydatetime()

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_fetch_live_data_api_error(self, mock_get, loader):
        """Test API error handling."""
        # Mock API failure
        mock_get.side_effect = Exception("API connection failed")

        with pytest.raises(Exception, match="API connection failed"):
            loader._fetch_live_data()

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_get_pollution_at_time_lazy_loading(self, mock_get, loader, mock_api_response):
        """Test lazy loading on first request."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Request pollution data
        request_time = datetime(2026, 4, 18, 1, 30)  # Between 01:00 and 02:00
        result = loader.get_pollution_at_time(request_time)

        # Verify API was called (lazy loading)
        mock_get.assert_called_once()

        # Verify result structure
        assert isinstance(result, dict)
        assert 'timestamp' in result
        assert 'pm2_5' in result
        assert 'no2' in result
        assert 'time_delta' in result
        assert 'out_of_range' in result
        assert 'data_source' in result

        # Verify data source
        assert result['data_source'] == 'live_api'

        # Verify matched closest timestamp (01:00)
        expected_timestamp = pd.to_datetime("2026-04-18T01:00:00").to_pydatetime()  # Naive datetime
        assert result['timestamp'] == expected_timestamp
        assert result['pm2_5'] == 4.8
        assert result['no2'] == 11.8

        # Verify time delta (30 minutes = 1800 seconds)
        assert result['time_delta'] == 1800
        assert not result['out_of_range']

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_get_pollution_at_time_cached_data(self, mock_get, loader, mock_api_response):
        """Test using cached data without API call."""
        # Pre-populate cache
        loader.cache_df = pd.DataFrame({
            'timestamp': pd.to_datetime(["2026-04-18T00:00:00", "2026-04-18T01:00:00"]),  # Naive
            'pm2_5': [5.2, 4.8],
            'no2': [12.3, 11.8]
        })
        loader.last_fetch_time = datetime.now() - timedelta(minutes=30)

        # Request pollution data
        request_time = datetime(2026, 4, 18, 0, 15)
        result = loader.get_pollution_at_time(request_time)

        # Verify API was NOT called (using cache)
        mock_get.assert_not_called()

        # Verify result
        assert result['pm2_5'] == 5.2
        assert result['time_delta'] == 900  # 15 minutes

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_get_pollution_at_time_cache_expiry(self, mock_get, loader, mock_api_response):
        """Test cache expiry triggers new API call."""
        # Pre-populate expired cache
        loader.cache_df = pd.DataFrame({
            'timestamp': pd.to_datetime(["2026-04-18T00:00:00"]),  # Naive
            'pm2_5': [5.2],
            'no2': [12.3]
        })
        loader.last_fetch_time = datetime.now() - timedelta(hours=2)  # Expired

        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Request pollution data
        request_time = datetime(2026, 4, 18, 1, 0)
        result = loader.get_pollution_at_time(request_time)

        # Verify API was called (cache expired)
        mock_get.assert_called_once()

        # Verify new data is used
        assert result['pm2_5'] == 4.8  # From new API data

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_get_pollution_at_time_api_failure_fallback(self, mock_get, loader):
        """Test fallback behavior when API fails."""
        # Mock API failure
        mock_get.side_effect = Exception("Network error")

        # Request pollution data
        request_time = datetime(2026, 4, 18, 12, 0)
        result = loader.get_pollution_at_time(request_time)

        # Verify fallback result
        assert result['pm2_5'] == 1.0  # Fallback value
        assert result['no2'] == 1.0
        assert result['out_of_range'] is True
        assert result['data_source'] == 'fallback'
        assert 'error' in result

    def test_get_pollution_at_time_invalid_input(self, loader):
        """Test invalid datetime input."""
        with pytest.raises(TypeError, match="request_datetime must be datetime"):
            loader.get_pollution_at_time("2026-04-18")

    def test_get_data_range_no_data(self, loader):
        """Test data range when no data loaded."""
        assert loader.get_data_range() is None

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_get_data_range_with_data(self, mock_get, loader, mock_api_response):
        """Test data range after loading data."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Load data
        loader._fetch_live_data()

        # Check data range
        data_range = loader.get_data_range()
        assert data_range is not None
        assert len(data_range) == 2
        assert isinstance(data_range[0], datetime)
        assert isinstance(data_range[1], datetime)

    def test_get_record_count_no_data(self, loader):
        """Test record count when no data loaded."""
        assert loader.get_record_count() == 0

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_get_record_count_with_data(self, mock_get, loader, mock_api_response):
        """Test record count after loading data."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Load data
        loader._fetch_live_data()

        # Check record count
        assert loader.get_record_count() == 3

    def test_get_cache_status_empty(self, loader):
        """Test cache status with empty cache."""
        status = loader.get_cache_status()
        assert not status['cache_valid']
        assert status['last_fetch'] is None
        assert status['record_count'] == 0
        assert status['data_range'] is None
        assert status['cache_age_minutes'] is None

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_get_cache_status_loaded(self, mock_get, loader, mock_api_response):
        """Test cache status after loading data."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Load data
        loader._fetch_live_data()

        # Check cache status
        status = loader.get_cache_status()
        assert status['cache_valid'] is True
        assert status['last_fetch'] is not None
        assert status['record_count'] == 3
        assert status['data_range'] is not None
        assert status['cache_age_minutes'] >= 0
        assert status['expires_in_minutes'] <= 60

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_force_refresh(self, mock_get, loader, mock_api_response):
        """Test force refresh functionality."""
        # Pre-populate cache
        loader.cache_df = pd.DataFrame({'timestamp': [], 'pm2_5': [], 'no2': []})
        loader.last_fetch_time = datetime.now() - timedelta(hours=1)

        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Force refresh
        loader.force_refresh()

        # Verify API was called and cache updated
        mock_get.assert_called_once()
        assert loader.cache_df is not None
        assert len(loader.cache_df) == 3

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_exact_timestamp_match(self, mock_get, loader, mock_api_response):
        """Test exact timestamp matching."""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Request exact timestamp
        request_time = datetime(2026, 4, 18, 1, 0)  # Exactly matches 01:00
        result = loader.get_pollution_at_time(request_time)

        # Verify exact match
        assert result['time_delta'] == 0
        assert result['pm2_5'] == 4.8

    @patch('src.collectors.live_air_quality_loader.requests.get')
    def test_out_of_range_request(self, mock_get, loader, mock_api_response):
        """Test request far outside data range."""
        # Mock API response with limited data
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        # Request time far in the future
        request_time = datetime(2026, 12, 18, 12, 0)
        result = loader.get_pollution_at_time(request_time)

        # Should still return data (live API covers past + forecast)
        # The API provides past days + forecast days, so this should work
        assert not result['out_of_range']
        assert result['data_source'] == 'live_api'