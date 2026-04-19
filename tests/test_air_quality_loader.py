"""Unit tests for AirQualityDataLoader."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
import pandas as pd

from src.collectors.air_quality_loader import AirQualityDataLoader


class TestAirQualityDataLoaderInitialization:
    """Test loader initialization and validation."""
    
    def test_load_valid_csv(self):
        """Test loading a valid air quality CSV file."""
        loader = AirQualityDataLoader()
        
        assert loader.data is not None
        assert len(loader.data) > 0
        assert set(loader.data.columns) >= {"timestamp", "pm2_5", "no2"}
        assert loader.data_range is not None
    
    def test_data_range_loaded(self):
        """Test that data range is correctly identified."""
        loader = AirQualityDataLoader()
        start_date, end_date = loader.get_data_range()
        
        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        assert start_date < end_date
        # From exploration, we know data range is March 9 to April 11, 2026
        assert start_date.year == 2026
        assert start_date.month == 3
        assert end_date.month == 4
    
    def test_record_count(self):
        """Test that record count is retrieved correctly."""
        loader = AirQualityDataLoader()
        count = loader.get_record_count()
        
        assert isinstance(count, int)
        assert count > 0
        # From exploration, we know there are ~792 records
        assert 750 < count < 850
    
    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for missing CSV."""
        with pytest.raises(FileNotFoundError):
            AirQualityDataLoader(csv_path=Path("/nonexistent/path/file.csv"))
    
    def test_invalid_csv_structure(self):
        """Test that ValueError is raised for CSV with missing columns."""
        with NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("date,temperature,humidity\n")
            f.write("2026-03-15 10:00,20.5,65\n")
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="missing required columns"):
                AirQualityDataLoader(csv_path=Path(temp_path))
        finally:
            Path(temp_path).unlink()


class TestAirQualityDataLoaderLookup:
    """Test pollution value lookup functionality."""
    
    def test_exact_timestamp_match(self):
        """Test lookup when request time exactly matches a record."""
        loader = AirQualityDataLoader()
        
        # Get first timestamp in data
        first_timestamp = loader.data["timestamp"].iloc[0].to_pydatetime()
        
        result = loader.get_pollution_at_time(first_timestamp)
        
        assert result["out_of_range"] is False
        assert result["timestamp"] == first_timestamp
        assert result["time_delta"] == 0
        assert result["pm2_5"] > 0
        assert result["no2"] > 0
    
    def test_nearest_hour_lookup_15_min_offset(self):
        """Test lookup with 15 minute offset from hour boundary."""
        loader = AirQualityDataLoader()
        
        # Get first timestamp and add 15 minutes
        first_timestamp = loader.data["timestamp"].iloc[0].to_pydatetime()
        request_time = first_timestamp + timedelta(minutes=15)
        
        result = loader.get_pollution_at_time(request_time)
        
        assert result["out_of_range"] is False
        assert result["timestamp"] == first_timestamp  # Should match first hour
        assert result["time_delta"] == 900  # 15 minutes in seconds
        assert result["pm2_5"] > 0
    
    def test_nearest_hour_lookup_30_min_offset(self):
        """Test lookup with 30 minute offset."""
        loader = AirQualityDataLoader()
        
        first_timestamp = loader.data["timestamp"].iloc[0].to_pydatetime()
        second_timestamp = loader.data["timestamp"].iloc[1].to_pydatetime()
        
        # Request time is 30 minutes into the first hour
        request_time = first_timestamp + timedelta(minutes=30)
        
        result = loader.get_pollution_at_time(request_time)
        
        assert result["out_of_range"] is False
        # Could match either first or second hour (both ~30 min away)
        assert result["timestamp"] in [first_timestamp, second_timestamp]
        assert 0 <= result["time_delta"] <= 1800  # Within 30 minutes
    
    def test_out_of_range_before_data(self):
        """Test lookup for time before data range."""
        loader = AirQualityDataLoader()
        
        # Request time before data range
        request_time = datetime(2025, 1, 1, 12, 0)
        
        result = loader.get_pollution_at_time(request_time)
        
        assert result["out_of_range"] is True
        assert result["timestamp"] is None
        assert result["pm2_5"] == AirQualityDataLoader.FALLBACK_POLLUTION_VALUE
        assert result["no2"] == AirQualityDataLoader.FALLBACK_POLLUTION_VALUE
        assert result["time_delta"] is None
    
    def test_out_of_range_after_data(self):
        """Test lookup for time after data range."""
        loader = AirQualityDataLoader()
        
        # Request time far after data range
        request_time = datetime(2027, 12, 31, 23, 59)
        
        result = loader.get_pollution_at_time(request_time)
        
        assert result["out_of_range"] is True
        assert result["timestamp"] is None
        assert result["pm2_5"] == AirQualityDataLoader.FALLBACK_POLLUTION_VALUE
    
    def test_return_value_structure(self):
        """Test that return value has expected structure."""
        loader = AirQualityDataLoader()
        
        first_timestamp = loader.data["timestamp"].iloc[0].to_pydatetime()
        result = loader.get_pollution_at_time(first_timestamp)
        
        # Check all expected keys exist
        expected_keys = {"timestamp", "pm2_5", "no2", "time_delta", "out_of_range"}
        assert set(result.keys()) == expected_keys
        
        # Check types
        assert isinstance(result["timestamp"], datetime)
        assert isinstance(result["pm2_5"], float)
        assert isinstance(result["no2"], float)
        assert isinstance(result["time_delta"], int)
        assert isinstance(result["out_of_range"], bool)
    
    def test_pollution_values_positive(self):
        """Test that pollution values are within reasonable ranges."""
        loader = AirQualityDataLoader()
        
        # Test a few random timestamps
        for idx in [0, len(loader.data)//2, -1]:
            timestamp = loader.data["timestamp"].iloc[idx].to_pydatetime()
            result = loader.get_pollution_at_time(timestamp)
            
            # PM2.5 typically ranges 0-200 µg/m³ in urban areas
            assert 0 <= result["pm2_5"] <= 200
            # NO2 typically ranges 0-100 µg/m³ in urban areas
            assert 0 <= result["no2"] <= 100
    
    def test_invalid_datetime_type(self):
        """Test that TypeError is raised for non-datetime input."""
        loader = AirQualityDataLoader()
        
        with pytest.raises(TypeError):
            loader.get_pollution_at_time("2026-03-15 14:30")
        
        with pytest.raises(TypeError):
            loader.get_pollution_at_time(123456)


class TestAirQualityDataLoaderDataQuality:
    """Test data quality and consistency."""
    
    def test_timestamps_are_sorted(self):
        """Test that loaded timestamps are sorted chronologically."""
        loader = AirQualityDataLoader()
        
        timestamps = loader.data["timestamp"].values
        assert all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
    
    def test_no_null_values_in_pollution_columns(self):
        """Test that pollution columns don't have null values."""
        loader = AirQualityDataLoader()
        
        assert loader.data["pm2_5"].isna().sum() == 0
        assert loader.data["no2"].isna().sum() == 0
    
    def test_hourly_data_spacing(self):
        """Test that data points are approximately hourly."""
        loader = AirQualityDataLoader()
        
        time_deltas = (
            loader.data["timestamp"].diff().dt.total_seconds()[1:]  # Skip first NaT
        )
        
        # All intervals should be very close to 3600 seconds (1 hour)
        # Allow some tolerance for DST changes or data collection variations
        assert (time_deltas > 3500).all()  # More than ~58 minutes
        assert (time_deltas < 3700).all()  # Less than ~62 minutes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
