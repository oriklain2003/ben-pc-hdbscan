"""
Example script demonstrating how to use the FR24 data gathering module.

This shows various ways to collect flight data programmatically.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data_gather import Config, FlightDataCollector


def example_basic_usage():
    """Basic usage with default configuration."""
    print("Example 1: Basic Usage")
    print("-" * 50)
    
    collector = FlightDataCollector()
    
    stats = collector.collect_historic_data(
        time_str="2026-01-07T00:00:00Z",
        verbose=True
    )
    
    print(f"\nResult: {stats}\n\n")


def example_custom_region():
    """Collect data for a custom geographic region."""
    print("Example 2: Custom Region")
    print("-" * 50)
    
    config = Config()
    collector = FlightDataCollector(config)
    
    # Example: Mediterranean region
    mediterranean_bounds = "45.0,30.0,0.0,40.0"  # lat_max,lat_min,lon_min,lon_max
    
    stats = collector.collect_historic_data(
        time_str="2026-01-07T06:00:00Z",
        bounds=mediterranean_bounds,
        min_altitude=10000,
        max_altitude=45000,
        verbose=True
    )
    
    print(f"\nResult: {stats}\n\n")


def example_batch_collection():
    """Collect data for multiple time points."""
    print("Example 3: Batch Collection (Multiple Times)")
    print("-" * 50)
    
    collector = FlightDataCollector()
    
    # Collect data every 6 hours
    time_points = [
        "2026-01-07T00:00:00Z",
        "2026-01-07T06:00:00Z",
        "2026-01-07T12:00:00Z",
        "2026-01-07T18:00:00Z",
    ]
    
    total_stats = {
        'new_flights': 0,
        'skipped_flights': 0,
        'total_points': 0
    }
    
    for time_str in time_points:
        print(f"\nCollecting data for {time_str}...")
        stats = collector.collect_historic_data(
            time_str=time_str,
            verbose=False
        )
        
        total_stats['new_flights'] += stats.new_flights
        total_stats['skipped_flights'] += stats.skipped_flights
        total_stats['total_points'] += stats.total_points
        
        print(f"  Added: {stats.new_flights} flights, {stats.total_points} points")
    
    print(f"\nTotal Summary:")
    print(f"  New flights: {total_stats['new_flights']}")
    print(f"  Skipped: {total_stats['skipped_flights']}")
    print(f"  Total points: {total_stats['total_points']}")
    print()


def example_custom_database():
    """Use a custom database location."""
    print("Example 4: Custom Database")
    print("-" * 50)
    
    config = Config(DB_NAME="custom_flights.db")
    collector = FlightDataCollector(config)
    
    print(f"Using database: {config.db_path}")
    
    stats = collector.collect_historic_data(
        time_str="2026-01-07T00:00:00Z",
        verbose=True
    )
    
    # Access database directly if needed
    print(f"\nDatabase statistics:")
    print(f"  Total flights: {collector.db.get_flight_count()}")
    print(f"  Total points: {collector.db.get_point_count()}")
    print()


def example_query_after_collection():
    """Collect data and then query the database."""
    print("Example 5: Collection + Query")
    print("-" * 50)
    
    collector = FlightDataCollector()
    
    # Collect data
    stats = collector.collect_historic_data(
        time_str="2026-01-07T00:00:00Z",
        verbose=False
    )
    
    print(f"Collected: {stats}")
    
    # Query database
    with collector.db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Get flight count by aircraft type
        cursor.execute("""
            SELECT type, COUNT(*) as count
            FROM flights
            WHERE type IS NOT NULL
            GROUP BY type
            ORDER BY count DESC
            LIMIT 5
        """)
        
        print("\nTop 5 aircraft types:")
        for aircraft_type, count in cursor.fetchall():
            print(f"  {aircraft_type}: {count} flights")
        
        # Get route statistics
        cursor.execute("""
            SELECT orig_icao, dest_icao, COUNT(*) as count
            FROM flights
            WHERE orig_icao IS NOT NULL AND dest_icao IS NOT NULL
            GROUP BY orig_icao, dest_icao
            ORDER BY count DESC
            LIMIT 5
        """)
        
        print("\nTop 5 routes:")
        for origin, dest, count in cursor.fetchall():
            print(f"  {origin} -> {dest}: {count} flights")
    
    print()


if __name__ == "__main__":
    print("=" * 70)
    print("FR24 Data Collection Examples")
    print("=" * 70)
    print()
    
    # Run examples
    # Uncomment the ones you want to run
    
    example_basic_usage()
    # example_custom_region()
    # example_batch_collection()
    # example_custom_database()
    # example_query_after_collection()
    
    print("=" * 70)
    print("Examples completed!")
    print("=" * 70)
