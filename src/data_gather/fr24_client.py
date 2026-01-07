"""FlightRadar24 API client wrapper."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fr24sdk.client import Client
from fr24sdk.models.flight import (
    FlightPositionsFullResponse, 
    FlightPositionsFull,
    FlightTracksResponse,
    FlightSummaryFullResponse
)


class FR24Client:
    """Wrapper class for FlightRadar24 API operations."""
    
    def __init__(self, api_token: str):
        """
        Initialize the FR24 API client.
        
        Args:
            api_token: FlightRadar24 API token
        """
        self.client = Client(api_token=api_token)
    
    def get_historic_flights(
        self,
        bounds: str,
        timestamp: int,
        min_altitude: int = 1000,
        max_altitude: int = 30000
    ) -> FlightPositionsFullResponse:
        """
        Fetch historic flight positions for a specific time and region.
        
        Args:
            bounds: Geographic bounds (lat_max,lat_min,lon_min,lon_max)
            timestamp: Unix timestamp for the historic query
            min_altitude: Minimum altitude filter in feet
            max_altitude: Maximum altitude filter in feet
            
        Returns:
            FlightPositionsFullResponse containing flight data
        """
        return self.client.historic.flight_positions.get_full(
            bounds=bounds,
            timestamp=timestamp,
            altitude_ranges=[{
                "min_altitude": min_altitude, 
                "max_altitude": max_altitude
            }]
        )
    
    def get_flight_track(self, flight_id: str) -> Optional[FlightTracksResponse]:
        """
        Fetch the full trajectory for a specific flight.
        
        Args:
            flight_id: FlightRadar24 flight identifier
            
        Returns:
            FlightTracksResponse containing track data, or None if not available
        """
        try:
            return self.client.flight_tracks.get(flight_id=flight_id)
        except Exception as e:
            return None
    
    @staticmethod
    def parse_timestamp(time_str: str) -> int:
        """
        Parse ISO 8601 timestamp string to Unix timestamp.
        
        Args:
            time_str: ISO 8601 formatted timestamp (e.g., "2026-01-07T00:00:00Z")
            
        Returns:
            Unix timestamp as integer
        """
        return int(
            datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").timestamp()
        )

    def get_flights_full_metadata(self, flight_ids: List[str]) -> Optional[FlightSummaryFullResponse]:
        """
        Fetch full flight summary metadata for given flight IDs.
        
        Args:
            flight_ids: List of FlightRadar24 flight identifiers
            
        Returns:
            FlightSummaryFullResponse containing detailed flight metadata, or None if error
        """
        try:
            return self.client.flight_summary.get_full(flight_ids=flight_ids)
        except Exception as e:
            return None