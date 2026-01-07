"""
Quick start script for the Flight Tracker API
Run this to start the FastAPI server
"""
import uvicorn
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    print("=" * 60)
    print("🛫 Starting Flight Tracker API Server")
    print("=" * 60)
    print("\n📍 API will be available at: http://localhost:8000")
    print("📊 Interactive docs at: http://localhost:8000/docs")
    print("🗺️  Open flight_map.html in your browser to view the map")
    print("\n⏹️  Press CTRL+C to stop the server\n")
    print("=" * 60 + "\n")
    
    uvicorn.run(
        "api.flight_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
