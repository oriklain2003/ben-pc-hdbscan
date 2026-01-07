import sqlite3
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from pathlib import Path

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
DB_NAME = "flight_paths.db"

# Pydantic models for request/response
class Point(BaseModel):
    lat: float
    lon: float
    alt: float
    speed: float

class PathSaveRequest(BaseModel):
    name: str = "Untitled Path"
    points: List[Point]
    origin: Optional[str] = None
    destination: Optional[str] = None

def init_db():
    """Initialize the SQLite database with paths and points tables."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Table to store the main path info
    c.execute('''CREATE TABLE IF NOT EXISTS paths (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT NOT NULL,
                 created_at TEXT NOT NULL,
                 origin TEXT,
                 destination TEXT
                 )''')
    
    # Add origin and destination columns if they don't exist (for existing databases)
    try:
        c.execute("ALTER TABLE paths ADD COLUMN origin TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute("ALTER TABLE paths ADD COLUMN destination TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Table to store individual points for each path
    c.execute('''CREATE TABLE IF NOT EXISTS points (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 path_id INTEGER,
                 lat REAL,
                 lon REAL,
                 alt REAL,
                 speed REAL,
                 order_index INTEGER,
                 FOREIGN KEY(path_id) REFERENCES paths(id)
                 )''')
    
    conn.commit()
    conn.close()

@app.get('/')
async def index():
    """Serve the main HTML page."""
    html_path = Path(__file__).parent / "index.html"
    return FileResponse(html_path)

@app.get('/api/paths')
async def get_paths():
    """List all saved paths."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM paths ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    
    paths = []
    for row in rows:
        paths.append({
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "origin": row["origin"],
            "destination": row["destination"]
        })
    return paths

@app.get('/api/paths/{path_id}')
async def get_path_details(path_id: int):
    """Get specific path and its points."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get path metadata
    c.execute("SELECT * FROM paths WHERE id = ?", (path_id,))
    path_row = c.fetchone()
    
    if not path_row:
        raise HTTPException(status_code=404, detail="Path not found")
        
    # Get points
    c.execute("SELECT * FROM points WHERE path_id = ? ORDER BY order_index ASC", (path_id,))
    point_rows = c.fetchall()
    
    points = []
    for row in point_rows:
        points.append({
            "lat": row["lat"],
            "lon": row["lon"],
            "alt": row["alt"],
            "speed": row["speed"]
        })
        
    conn.close()
    
    return {
        "id": path_row["id"],
        "name": path_row["name"],
        "created_at": path_row["created_at"],
        "origin": path_row.get("origin"),
        "destination": path_row.get("destination"),
        "points": points
    }

@app.post('/api/save')
async def save_path(path_data: PathSaveRequest):
    """Save a new path with points."""
    if not path_data.points:
        raise HTTPException(status_code=400, detail="No points provided")

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Insert Path
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO paths (name, created_at, origin, destination) VALUES (?, ?, ?, ?)", 
              (path_data.name, timestamp, path_data.origin, path_data.destination))
    path_id = c.lastrowid
    
    # Insert Points
    for idx, p in enumerate(path_data.points):
        c.execute('''INSERT INTO points (path_id, lat, lon, alt, speed, order_index) 
                     VALUES (?, ?, ?, ?, ?, ?)''', 
                     (path_id, p.lat, p.lon, p.alt, p.speed, idx))
    
    conn.commit()
    conn.close()
    
    return {"message": "Path saved successfully", "id": path_id}

@app.delete('/api/paths/{path_id}')
async def delete_path(path_id: int):
    """Delete a path and all its associated points."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check if path exists
    c.execute("SELECT id FROM paths WHERE id = ?", (path_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Path not found")
    
    # Delete points first (due to foreign key constraint)
    c.execute("DELETE FROM points WHERE path_id = ?", (path_id,))
    
    # Delete path
    c.execute("DELETE FROM paths WHERE id = ?", (path_id,))
    
    conn.commit()
    conn.close()
    
    return {"message": "Path deleted successfully"}

if __name__ == '__main__':


    import uvicorn
    init_db()
    print("Server running on http://localhost:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")