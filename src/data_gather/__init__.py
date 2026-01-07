"""
FR24 Data Gathering Module

This module provides functionality to fetch flight data from FlightRadar24 API
and store it in a SQLite database with proper schema design.
"""

try:
    from .config import Config
    from .database import FlightDatabase
    from .fr24_client import FR24Client
    from .data_collector import FlightDataCollector, CollectionStats
except ImportError:
    from config import Config
    from database import FlightDatabase
    from fr24_client import FR24Client
    from data_collector import FlightDataCollector, CollectionStats

__all__ = [
    'Config', 
    'FlightDatabase', 
    'FR24Client', 
    'FlightDataCollector',
    'CollectionStats'
]
