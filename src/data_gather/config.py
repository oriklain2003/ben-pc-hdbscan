"""Configuration settings for FR24 data gathering."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Configuration class for FR24 data gathering."""
    
    # FR24 API Configuration
    API_TOKEN: str = "019b9854-539d-702b-85fc-a349efab9cef|BXPq2SOkIZL5ZZUJxwJtrsLXAIqheURyvveV2pWN508f340e"
    
    # Database Configuration
    DB_NAME: str = "flight_data.db"
    
    # Search Parameters (Israel region by default)
    DEFAULT_BOUNDS: str = "35.675147,29.152161,33.00293,36.166992"
    DEFAULT_MIN_ALTITUDE: int = 1000
    DEFAULT_MAX_ALTITUDE: int = 30000
    
    @property
    def db_path(self) -> str:
        """Get the full path to the database file."""
        return os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "..", 
            self.DB_NAME
        )
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Create configuration from environment variables."""
        return cls(
            API_TOKEN=os.getenv('FR24_API_TOKEN', cls.API_TOKEN),
            DB_NAME=os.getenv('FR24_DB_NAME', cls.DB_NAME),
            DEFAULT_BOUNDS=os.getenv('FR24_BOUNDS', cls.DEFAULT_BOUNDS),
        )
