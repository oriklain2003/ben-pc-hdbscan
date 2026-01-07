"""
Main script for collecting FlightRadar24 data and storing it in SQLite.

This script fetches historic flight data from the FR24 API and stores both
flight metadata and full trajectory points in a SQLite database.

Usage:
    python fr24_get_data.py
    or
    python -m src.data_gather.fr24_get_data
"""

import sys
import os
import time
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from data_collector import FlightDataCollector
from config import Config


from datetime import datetime, timedelta

def main():
    """Main entry point for data collection."""
    # Initialize configuration (can be customized or loaded from environment)
    config = Config()
    
    # Create data collector
    collector = FlightDataCollector(config)
    
    # Specify the start, end times and step in minutes
    start_time_str = "2026-01-06T06:00:00Z"
    end_time_str = "2026-01-07T07:00:00Z"
    step_minutes = 60 * 4  # Change this to set your desired jump
    
    # Parse times
    start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ")
    end_time = datetime.strptime(end_time_str, "%Y-%m-%dT%H:%M:%SZ")
    delta = timedelta(minutes=step_minutes)
    
    try:
        current_time = start_time
        while current_time <= end_time:
            time_str = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"\n[INFO] Collecting data for time: {time_str}")
            
            stats = collector.collect_historic_data(
                time_str=time_str,
                verbose=True
            )
            print(f"[OK] Data collection completed for {time_str}: {stats}")
            
            current_time += delta
            time.sleep(2)

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Data collection interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Error during data collection: {e}")
        raise


if __name__ == "__main__":
    main()
