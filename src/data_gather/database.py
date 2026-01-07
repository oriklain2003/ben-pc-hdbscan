"""Database management for flight data storage."""

import sqlite3
from typing import List, Optional
from contextlib import contextmanager
from fr24sdk.models.flight import FlightPositionsFull, FlightTrackPoint, FlightSummaryFull


class FlightDatabase:
    """Manages SQLite database operations for flight data."""
    
    def __init__(self, db_path: str):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_tables()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    def _ensure_tables(self) -> None:
        """Create database tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create flights metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fr24_id TEXT UNIQUE NOT NULL,
                    flight TEXT,
                    callsign TEXT,
                    hex TEXT,
                    type TEXT,
                    reg TEXT,
                    painted_as TEXT,
                    operating_as TEXT,
                    orig_iata TEXT,
                    orig_icao TEXT,
                    dest_iata TEXT,
                    dest_icao TEXT,
                    squawk TEXT,
                    source TEXT,
                    snapshot_timestamp TEXT,
                    eta TEXT,
                    lat REAL,
                    lon REAL,
                    alt INTEGER,
                    gspeed INTEGER,
                    vspeed INTEGER,
                    track INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create flight_points trajectory table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flight_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fr24_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    alt INTEGER,
                    gspeed INTEGER,
                    vspeed INTEGER,
                    track INTEGER,
                    squawk TEXT,
                    callsign TEXT,
                    source TEXT,
                    point_order INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (fr24_id) REFERENCES flights(fr24_id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_flight_points_fr24_id 
                ON flight_points(fr24_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_flight_points_timestamp 
                ON flight_points(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_flights_route 
                ON flights(orig_icao, dest_icao)
            """)
            
            # Create flight_metadata table with full summary data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flight_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fr24_id TEXT UNIQUE NOT NULL,
                    flight TEXT,
                    callsign TEXT,
                    operating_as TEXT,
                    painted_as TEXT,
                    type TEXT,
                    reg TEXT,
                    orig_icao TEXT,
                    orig_iata TEXT,
                    datetime_takeoff TEXT,
                    runway_takeoff TEXT,
                    dest_icao TEXT,
                    dest_iata TEXT,
                    dest_icao_actual TEXT,
                    dest_iata_actual TEXT,
                    datetime_landed TEXT,
                    runway_landed TEXT,
                    flight_time REAL,
                    actual_distance REAL,
                    circle_distance REAL,
                    category TEXT,
                    hex TEXT,
                    first_seen TEXT,
                    last_seen TEXT,
                    flight_ended INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (fr24_id) REFERENCES flights(fr24_id)
                )
            """)
            
            # Create indexes for flight_metadata
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_flight_metadata_route 
                ON flight_metadata(orig_icao, dest_icao)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_flight_metadata_times 
                ON flight_metadata(datetime_takeoff, datetime_landed)
            """)
            
            conn.commit()
    
    def flight_exists(self, fr24_id: str) -> bool:
        """
        Check if a flight already exists in the database.
        
        Args:
            fr24_id: FlightRadar24 flight identifier
            
        Returns:
            True if flight exists, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM flights WHERE fr24_id = ? LIMIT 1", 
                (fr24_id,)
            )
            return cursor.fetchone() is not None
    
    def insert_flight_metadata(
        self, 
        flight: FlightPositionsFull, 
        snapshot_time: str
    ) -> None:
        """
        Insert flight metadata into the flights table.
        
        Args:
            flight: Flight position data from FR24 API
            snapshot_time: Timestamp when the snapshot was taken
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            flight_data = flight.model_dump()
            
            cursor.execute("""
                INSERT INTO flights (
                    fr24_id, flight, callsign, hex, type, reg,
                    painted_as, operating_as, orig_iata, orig_icao,
                    dest_iata, dest_icao, squawk, source,
                    snapshot_timestamp, eta, lat, lon, alt,
                    gspeed, vspeed, track
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                flight_data['fr24_id'],
                flight_data.get('flight'),
                flight_data.get('callsign'),
                flight_data.get('hex'),
                flight_data.get('type'),
                flight_data.get('reg'),
                flight_data.get('painted_as'),
                flight_data.get('operating_as'),
                flight_data.get('orig_iata'),
                flight_data.get('orig_icao'),
                flight_data.get('dest_iata'),
                flight_data.get('dest_icao'),
                flight_data.get('squawk'),
                flight_data.get('source'),
                snapshot_time,
                flight_data.get('eta'),
                flight_data.get('lat'),
                flight_data.get('lon'),
                flight_data.get('alt'),
                flight_data.get('gspeed'),
                flight_data.get('vspeed'),
                flight_data.get('track')
            ))
            
            conn.commit()
    
    def insert_flight_summary_metadata(
        self, 
        flight_summary: FlightSummaryFull
    ) -> None:
        """
        Insert detailed flight summary metadata into the flight_metadata table.
        
        Args:
            flight_summary: Flight summary data from FR24 API
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            summary_data = flight_summary.model_dump()
            
            cursor.execute("""
                INSERT INTO flight_metadata (
                    fr24_id, flight, callsign, operating_as, painted_as,
                    type, reg, orig_icao, orig_iata, datetime_takeoff,
                    runway_takeoff, dest_icao, dest_iata, dest_icao_actual,
                    dest_iata_actual, datetime_landed, runway_landed,
                    flight_time, actual_distance, circle_distance,
                    category, hex, first_seen, last_seen, flight_ended
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                summary_data['fr24_id'],
                summary_data.get('flight'),
                summary_data.get('callsign'),
                summary_data.get('operating_as'),
                summary_data.get('painted_as'),
                summary_data.get('type'),
                summary_data.get('reg'),
                summary_data.get('orig_icao'),
                summary_data.get('orig_iata'),
                summary_data.get('datetime_takeoff'),
                summary_data.get('runway_takeoff'),
                summary_data.get('dest_icao'),
                summary_data.get('dest_iata'),
                summary_data.get('dest_icao_actual'),
                summary_data.get('dest_iata_actual'),
                summary_data.get('datetime_landed'),
                summary_data.get('runway_landed'),
                summary_data.get('flight_time'),
                summary_data.get('actual_distance'),
                summary_data.get('circle_distance'),
                summary_data.get('category'),
                summary_data.get('hex'),
                summary_data.get('first_seen'),
                summary_data.get('last_seen'),
                1 if summary_data.get('flight_ended') else 0
            ))
            
            conn.commit()
    
    def flight_metadata_exists(self, fr24_id: str) -> bool:
        """
        Check if flight metadata already exists in the database.
        
        Args:
            fr24_id: FlightRadar24 flight identifier
            
        Returns:
            True if metadata exists, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM flight_metadata WHERE fr24_id = ? LIMIT 1", 
                (fr24_id,)
            )
            return cursor.fetchone() is not None
    
    def insert_flight_track_points(
        self, 
        fr24_id: str, 
        track_points: List[FlightTrackPoint]
    ) -> int:
        """
        Insert flight track points into the flight_points table.
        
        Args:
            fr24_id: FlightRadar24 flight identifier
            track_points: List of trajectory points
            
        Returns:
            Number of points inserted
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Prepare batch insert data
            points_data = [
                (
                    fr24_id,
                    point.timestamp,
                    point.lat,
                    point.lon,
                    point.alt,
                    point.gspeed,
                    point.vspeed,
                    point.track,
                    point.squawk,
                    point.callsign,
                    point.source,
                    idx  # point_order
                )
                for idx, point in enumerate(track_points)
            ]
            
            # Batch insert for performance
            cursor.executemany("""
                INSERT INTO flight_points (
                    fr24_id, timestamp, lat, lon, alt, gspeed,
                    vspeed, track, squawk, callsign, source, point_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, points_data)
            
            conn.commit()
            return len(points_data)
    
    def get_flight_count(self) -> int:
        """Get the total number of flights in the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM flights")
            return cursor.fetchone()[0]
    
    def get_point_count(self) -> int:
        """Get the total number of flight points in the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM flight_points")
            return cursor.fetchone()[0]
