"""
Air Quality Data Loader

Loads historical air quality data from CSV and provides nearest-hour lookup
for pollution values at user-requested timestamps.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class AirQualityDataLoader:
    """
    Loads and manages air quality data from CSV file.
    
    Data source: data/raw/aarhus_air_quality_raw.csv
    Contains hourly PM2.5 and NO2 measurements for Aarhus, Denmark.
    """
    
    # Default fallback value if requested time is outside data range
    FALLBACK_POLLUTION_VALUE = 1.0
    
    # Maximum allowed time delta (days) before warning user
    MAX_TIME_DELTA_DAYS = 30
    
    def __init__(self, csv_path: Optional[Path] = None):
        """
        Initialize the loader and load air quality data from CSV.
        
        Args:
            csv_path: Path to the CSV file. If None, uses default path
                     (data/raw/aarhus_air_quality_raw.csv relative to project root)
        
        Raises:
            FileNotFoundError: If CSV file does not exist
            ValueError: If CSV structure is invalid (missing columns or bad dates)
        """
        if csv_path is None:
            csv_path = self._get_default_csv_path()
        
        self.csv_path = Path(csv_path)
        self.data: pd.DataFrame = None
        self.data_range: Tuple[datetime, datetime] = None
        
        self._load_and_validate()
    
    def _get_default_csv_path(self) -> Path:
        """
        Get default CSV path relative to project root.
        
        Returns:
            Path to data/raw/aarhus_air_quality_raw.csv
        """
        # Navigate up from src/collectors to project root
        project_root = Path(__file__).parent.parent.parent
        return project_root / "data" / "raw" / "aarhus_air_quality_raw.csv"
    
    def _load_and_validate(self) -> None:
        """
        Load CSV file and validate structure.
        
        Raises:
            FileNotFoundError: If CSV file does not exist
            ValueError: If CSV is missing required columns or has invalid timestamps
        """
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Air quality CSV not found at {self.csv_path}. "
                f"Expected location: data/raw/aarhus_air_quality_raw.csv"
            )
        
        try:
            self.data = pd.read_csv(self.csv_path)
        except Exception as e:
            raise ValueError(f"Failed to read CSV file {self.csv_path}: {e}")
        
        # Validate required columns
        required_columns = {"timestamp", "pm2_5", "no2"}
        missing_columns = required_columns - set(self.data.columns)
        if missing_columns:
            raise ValueError(
                f"CSV is missing required columns: {missing_columns}. "
                f"Found columns: {set(self.data.columns)}"
            )
        
        # Parse timestamp column to datetime
        try:
            self.data["timestamp"] = pd.to_datetime(self.data["timestamp"])
        except Exception as e:
            raise ValueError(f"Failed to parse 'timestamp' column to datetime: {e}")
        
        # Sort by timestamp to enable efficient lookups
        self.data = self.data.sort_values("timestamp").reset_index(drop=True)
        
        # Calculate data range
        self.data_range = (
            self.data["timestamp"].min().to_pydatetime(),
            self.data["timestamp"].max().to_pydatetime()
        )
        
        logger.info(
            f"Loaded air quality data from {self.csv_path}. "
            f"Records: {len(self.data)}, "
            f"Date range: {self.data_range[0]} to {self.data_range[1]}"
        )
    
    def get_pollution_at_time(
        self, 
        request_datetime: datetime
    ) -> Dict[str, float]:
        """
        Get pollution values (PM2.5 and NO2) for a requested timestamp.
        
        Uses nearest-hour matching: finds the hourly record closest in time
        to the requested datetime.
        
        Args:
            request_datetime: User-requested time (any precision accepted)
        
        Returns:
            Dictionary with keys:
                - 'timestamp': The matched timestamp (hourly)
                - 'pm2_5': PM2.5 concentration (µg/m³)
                - 'no2': NO2 concentration (µg/m³)
                - 'time_delta': Time difference in seconds between request and match
        
        Example:
            >>> loader = AirQualityDataLoader()
            >>> result = loader.get_pollution_at_time(datetime(2026, 3, 15, 14, 37))
            >>> print(result['pm2_5'])  # PM2.5 for closest hour
            12.5
        """
        if not isinstance(request_datetime, datetime):
            raise TypeError(f"request_datetime must be datetime, got {type(request_datetime)}")
        
        # Check if requested time is within data range
        if request_datetime < self.data_range[0] or request_datetime > self.data_range[1]:
            days_outside = abs(
                (request_datetime - self.data_range[0]).days 
                if request_datetime < self.data_range[0]
                else (request_datetime - self.data_range[1]).days
            )
            
            logger.warning(
                f"Requested time {request_datetime} is {days_outside} days outside "
                f"data range ({self.data_range[0]} to {self.data_range[1]}). "
                f"Returning fallback value (pollution={self.FALLBACK_POLLUTION_VALUE})."
            )
            
            return {
                "timestamp": None,
                "pm2_5": self.FALLBACK_POLLUTION_VALUE,
                "no2": self.FALLBACK_POLLUTION_VALUE,
                "time_delta": None,
                "out_of_range": True,
                "is_stale": True
            }
        
        # Find nearest timestamp by calculating absolute time delta
        self.data["time_delta"] = (
            self.data["timestamp"] - request_datetime
        ).abs()
        
        nearest_idx = self.data["time_delta"].idxmin()
        nearest_row = self.data.loc[nearest_idx]
        
        return {
            "timestamp": nearest_row["timestamp"].to_pydatetime(),
            "pm2_5": float(nearest_row["pm2_5"]),
            "no2": float(nearest_row["no2"]),
            "time_delta": int(nearest_row["time_delta"].total_seconds()),
            "out_of_range": False,
            "is_stale": False
        }
    
    def get_data_range(self) -> Tuple[datetime, datetime]:
        """
        Get the date range of available air quality data.
        
        Returns:
            Tuple of (earliest_datetime, latest_datetime)
        """
        return self.data_range
    
    def get_record_count(self) -> int:
        """
        Get total number of air quality records loaded.
        
        Returns:
            Number of hourly records in the dataset
        """
        return len(self.data)
