"""
Live Air Quality Data Loader

Fetches real-time and forecasted air quality data from Open-Meteo API
with lazy loading and caching for optimal performance.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class LiveAirQualityLoader:
    """
    Live air quality data loader using Open-Meteo API.

    Features lazy loading with caching:
    - Fetches data only when cache is empty or expired (1 hour)
    - Provides past 1 day + forecast 3 days of hourly data
    - Same interface as AirQualityDataLoader for seamless integration

    Data source: https://air-quality-api.open-meteo.com/v1/air-quality
    """

    # API Configuration
    API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
    LATITUDE = 56.1567  # Aarhus, Denmark
    LONGITUDE = 10.2108
    TIMEZONE = "Europe/Berlin"

    # Cache settings
    CACHE_EXPIRY_MINUTES = 60  # Data valid for 1 hour
    PAST_DAYS = 1  # Include 1 day of historical data
    FORECAST_DAYS = 3  # Include 3 days of forecast

    # Fallback value if API fails
    FALLBACK_POLLUTION_VALUE = 1.0

    def __init__(self):
        """
        Initialize the live loader with empty cache.
        """
        self.cache_df: Optional[pd.DataFrame] = None
        self.last_fetch_time: Optional[datetime] = None
        self.data_range: Optional[tuple] = None

    def _is_cache_valid(self) -> bool:
        """
        Check if cached data is still valid.

        Returns:
            True if cache exists and hasn't expired, False otherwise
        """
        if self.cache_df is None or self.last_fetch_time is None:
            return False

        cache_age = datetime.now() - self.last_fetch_time
        return cache_age < timedelta(minutes=self.CACHE_EXPIRY_MINUTES)

    def _fetch_live_data(self) -> None:
        """
        Fetch live air quality data from Open-Meteo API.

        Updates cache with past 1 day + forecast 3 days of hourly data.

        Raises:
            requests.RequestException: If API request fails
            ValueError: If API response is malformed
        """
        logger.info("Cache empty or expired. Fetching live API data...")

        params = {
            "latitude": self.LATITUDE,
            "longitude": self.LONGITUDE,
            "hourly": "pm2_5,nitrogen_dioxide",
            "past_days": self.PAST_DAYS,
            "forecast_days": self.FORECAST_DAYS,
            "timezone": self.TIMEZONE
        }

        try:
            response = requests.get(self.API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            # Validate response structure
            if "hourly" not in data:
                raise ValueError("API response missing 'hourly' data")

            hourly = data["hourly"]
            required_fields = ["time", "pm2_5", "nitrogen_dioxide"]
            for field in required_fields:
                if field not in hourly:
                    raise ValueError(f"API response missing required field: {field}")

            # Convert to DataFrame
            df = pd.DataFrame({
                "timestamp": pd.to_datetime(hourly["time"]),
                "pm2_5": hourly["pm2_5"],
                "no2": hourly["nitrogen_dioxide"]
            })

            # Convert timezone-aware timestamps to naive UTC for easier comparison
            if df["timestamp"].dt.tz is not None:
                df["timestamp"] = df["timestamp"].dt.tz_convert('UTC').dt.tz_localize(None)

            # Sort by timestamp (API should return sorted, but ensure it)
            df = df.sort_values("timestamp").reset_index(drop=True)

            # Update cache
            self.cache_df = df
            self.last_fetch_time = datetime.now()
            self.data_range = (
                df["timestamp"].min().to_pydatetime(),
                df["timestamp"].max().to_pydatetime()
            )

            logger.info(
                f"Successfully cached live forecast data: "
                f"{len(df)} records from {self.data_range[0]} to {self.data_range[1]}"
            )

        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
        except (KeyError, ValueError) as e:
            logger.error(f"API response parsing failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching live data: {e}")
            raise

    def get_pollution_at_time(
        self,
        request_datetime: datetime
    ) -> Dict[str, float]:
        """
        Get pollution values for a requested timestamp using live data.

        Uses lazy loading: fetches from API only when cache is empty or expired.
        Finds nearest hourly record using absolute time delta.

        Args:
            request_datetime: User-requested time (any precision accepted)

        Returns:
            Dictionary with keys:
                - 'timestamp': The matched timestamp (hourly)
                - 'pm2_5': PM2.5 concentration (µg/m³)
                - 'no2': NO2 concentration (µg/m³)
                - 'time_delta': Time difference in seconds between request and match
                - 'out_of_range': False (live data covers past + forecast)
                - 'data_source': 'live_api'

        Raises:
            TypeError: If request_datetime is not a datetime object
        """
        if not isinstance(request_datetime, datetime):
            raise TypeError(f"request_datetime must be datetime, got {type(request_datetime)}")

        # Lazy loading: fetch data if cache invalid
        if not self._is_cache_valid():
            try:
                self._fetch_live_data()
            except Exception as e:
                # Check if we have stale cache data to fall back to
                if self.cache_df is not None and self.last_fetch_time is not None:
                    cache_age = datetime.now() - self.last_fetch_time
                    cache_age_minutes = cache_age.total_seconds() / 60
                    logger.warning(
                        f"Failed to fetch live data: {e}. "
                        f"Using stale cache data ({cache_age_minutes:.1f} minutes old)."
                    )
                    # Continue with stale cache data below
                else:
                    logger.warning(
                        f"Failed to fetch live data: {e}. "
                        f"No cache data available. Returning fallback pollution value ({self.FALLBACK_POLLUTION_VALUE})."
                    )
                    return {
                        "timestamp": None,
                        "pm2_5": self.FALLBACK_POLLUTION_VALUE,
                        "no2": self.FALLBACK_POLLUTION_VALUE,
                        "time_delta": None,
                        "out_of_range": True,
                        "data_source": "fallback",
                        "error": str(e)
                    }

        # Find nearest timestamp by calculating absolute time delta
        # All timestamps in cache_df are timezone-naive (UTC)
        # Make request_datetime timezone-naive if it has timezone info
        request_naive = request_datetime
        if request_datetime.tzinfo is not None:
            request_naive = request_datetime.astimezone().replace(tzinfo=None)

        time_deltas = abs(self.cache_df["timestamp"] - pd.to_datetime(request_naive))
        closest_index = time_deltas.idxmin()
        nearest_row = self.cache_df.loc[closest_index]

        return {
            "timestamp": nearest_row["timestamp"].to_pydatetime(),
            "pm2_5": float(nearest_row["pm2_5"]),
            "no2": float(nearest_row["no2"]),
            "time_delta": int(time_deltas.loc[closest_index].total_seconds()),
            "out_of_range": False,
            "data_source": "live_api",
            "is_stale": not self._is_cache_valid() if hasattr(self, '_is_cache_valid') else False
        }

    def get_data_range(self) -> Optional[tuple]:
        """
        Get the date range of available live data.

        Returns:
            Tuple of (earliest_datetime, latest_datetime) or None if no data cached
        """
        return self.data_range

    def get_record_count(self) -> int:
        """
        Get total number of cached air quality records.

        Returns:
            Number of hourly records in cache, or 0 if no data cached
        """
        return len(self.cache_df) if self.cache_df is not None else 0

    def get_cache_status(self) -> Dict[str, any]:
        """
        Get detailed cache status information.

        Returns:
            Dictionary with cache status details
        """
        if self.cache_df is None:
            return {
                "cache_valid": False,
                "last_fetch": None,
                "record_count": 0,
                "data_range": None,
                "cache_age_minutes": None
            }

        cache_age = datetime.now() - self.last_fetch_time
        return {
            "cache_valid": self._is_cache_valid(),
            "last_fetch": self.last_fetch_time.isoformat(),
            "record_count": len(self.cache_df),
            "data_range": (
                self.data_range[0].isoformat(),
                self.data_range[1].isoformat()
            ) if self.data_range else None,
            "cache_age_minutes": cache_age.total_seconds() / 60,
            "expires_in_minutes": max(0, self.CACHE_EXPIRY_MINUTES - cache_age.total_seconds() / 60)
        }

    def force_refresh(self) -> None:
        """
        Force a refresh of the cache by clearing it and fetching new data.

        Useful for testing or manual cache invalidation.
        """
        logger.info("Forcing cache refresh...")
        self.cache_df = None
        self.last_fetch_time = None
        self.data_range = None
        self._fetch_live_data()