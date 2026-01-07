"""Main data collection orchestrator."""
import time
from typing import Optional
from dataclasses import dataclass

try:
    from .config import Config
    from .database import FlightDatabase
    from .fr24_client import FR24Client
except ImportError:
    from config import Config
    from database import FlightDatabase
    from fr24_client import FR24Client


@dataclass
class CollectionStats:
    """Statistics from a data collection run."""
    new_flights: int = 0
    skipped_flights: int = 0
    total_points: int = 0
    
    def __str__(self) -> str:
        return (
            f"New flights: {self.new_flights}, "
            f"Skipped: {self.skipped_flights}, "
            f"Points: {self.total_points}"
        )


class FlightDataCollector:
    """Orchestrates flight data collection from FR24 API to database."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the data collector.
        
        Args:
            config: Configuration object (uses default if None)
        """
        self.config = config or Config()
        self.db = FlightDatabase(self.config.db_path)
        self.client = FR24Client(self.config.API_TOKEN)
    
    def collect_historic_data(
        self,
        time_str: str,
        bounds: Optional[str] = None,
        min_altitude: Optional[int] = None,
        max_altitude: Optional[int] = None,
        verbose: bool = True
    ) -> CollectionStats:
        """
        Collect historic flight data for a specific time.
        
        Args:
            time_str: ISO 8601 timestamp (e.g., "2026-01-07T00:00:00Z")
            bounds: Geographic bounds (uses default if None)
            min_altitude: Minimum altitude filter (uses default if None)
            max_altitude: Maximum altitude filter (uses default if None)
            verbose: Print progress messages
            
        Returns:
            CollectionStats object with collection statistics
        """
        # Use defaults if not provided
        bounds = bounds or self.config.DEFAULT_BOUNDS
        min_altitude = min_altitude or self.config.DEFAULT_MIN_ALTITUDE
        max_altitude = max_altitude or self.config.DEFAULT_MAX_ALTITUDE
        
        if verbose:
            print("=" * 70)
            print("FR24 Data Collection")
            print("=" * 70)
            print(f"[CONFIG] Time: {time_str}")
            print(f"[CONFIG] Bounds: {bounds}")
            print(f"[CONFIG] Altitude: {min_altitude}-{max_altitude} ft")
            print(f"[DB] Database: {self.config.db_path}")
        
        # Parse timestamp
        timestamp = FR24Client.parse_timestamp(time_str)
        
        # Fetch historic flights
        if verbose:
            print(f"\n[FETCH] Fetching historic flight positions...")
        
        flights_response = self.client.get_historic_flights(
            bounds=bounds,
            timestamp=timestamp,
            min_altitude=min_altitude,
            max_altitude=max_altitude
        )
        
        if not flights_response.data:
            if verbose:
                print("   [WARN] No flights found for the specified criteria")
            return CollectionStats()
        
        if verbose:
            print(f"   [OK] Found {len(flights_response.data)} flights")
            print(f"\n[PROCESS] Processing flights...")
        
        # Process each flight
        stats = CollectionStats()
        flight_ids_for_metadata = []  # Collect IDs for batch metadata fetch
        
        for idx, flight in enumerate(flights_response.data, 1):
            fr24_id = flight.fr24_id
            flight_name = flight.flight or flight.callsign or fr24_id
            
            # Check if flight already exists
            if self.db.flight_exists(fr24_id):
                stats.skipped_flights += 1
                if verbose:
                    print(f"[{idx}/{len(flights_response.data)}] [SKIP] {flight_name}")
                continue
            
            if verbose:
                print(f"[{idx}/{len(flights_response.data)}] [NEW] {flight_name} ({fr24_id})")
            
            # Insert flight position data
            try:
                self.db.insert_flight_metadata(flight, time_str)
                stats.new_flights += 1
                flight_ids_for_metadata.append(fr24_id)  # Add to list for metadata fetch
                time.sleep(2)
                if verbose:
                    print(f"  [OK] Inserted flight position data")
            except Exception as e:
                if verbose:
                    print(f"  [ERROR] Error inserting position data: {e}")
                continue
            
            # Fetch and insert full track
            try:
                if verbose:
                    print(f"  [TRACK] Fetching full flight track...")
                
                track_response = self.client.get_flight_track(fr24_id)
                
                if track_response and track_response.data and track_response.data[0].tracks:
                    tracks = track_response.data[0].tracks
                    point_count = self.db.insert_flight_track_points(fr24_id, tracks)
                    stats.total_points += point_count
                    if verbose:
                        print(f"  [OK] Inserted {point_count} track points")
                else:
                    if verbose:
                        print(f"  [WARN] No track data available")
                        
            except Exception as e:
                if verbose:
                    print(f"  [WARN] Could not fetch track: {e}")
        
        # Fetch detailed metadata for all new flights
        if flight_ids_for_metadata:
            if verbose:
                print(f"\n[METADATA] Fetching detailed metadata for {len(flight_ids_for_metadata)} flights...")
            
            try:
                # FR24 API supports batch requests (up to 15 at a time)
                batch_size = 15
                metadata_count = 0
                
                for i in range(0, len(flight_ids_for_metadata), batch_size):
                    batch = flight_ids_for_metadata[i:i + batch_size]
                    
                    metadata_response = self.client.get_flights_full_metadata(batch)
                    
                    if metadata_response and metadata_response.data:
                        for flight_metadata in metadata_response.data:
                            try:
                                if not self.db.flight_metadata_exists(flight_metadata.fr24_id):
                                    self.db.insert_flight_summary_metadata(flight_metadata)
                                    metadata_count += 1
                            except Exception as e:
                                if verbose:
                                    print(f"  [WARN] Could not insert metadata for {flight_metadata.fr24_id}: {e}")
                
                if verbose:
                    print(f"  [OK] Inserted {metadata_count} flight metadata records")
                    
            except Exception as e:
                if verbose:
                    print(f"  [ERROR] Error fetching flight metadata: {e}")
        
        # Summary
        if verbose:
            print("\n" + "=" * 70)
            print("[SUMMARY]")
            print("=" * 70)
            print(f"[OK] New flights added: {stats.new_flights}")
            print(f"[SKIP] Skipped (duplicates): {stats.skipped_flights}")
            print(f"[POINTS] Total track points inserted: {stats.total_points}")
            print(f"[DB] Total in database: {self.db.get_flight_count()} flights, "
                  f"{self.db.get_point_count()} points")
            print("=" * 70)
        
        return stats
