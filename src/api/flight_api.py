from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fr24sdk.client import Client
from pathlib import Path
from typing import Optional
import sqlite3
import json

app = FastAPI(title="Flight Tracker API")

# Enable CORS so the HTML file can make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize FR24 client
client = Client(api_token="019b9854-539d-702b-85fc-a349efab9cef|BXPq2SOkIZL5ZZUJxwJtrsLXAIqheURyvveV2pWN508f340e")

# Bounds for the region (lat_min, lat_max, lon_min, lon_max)
BOUNDS = "35.675147,29.152161,33.00293,36.166992"

# Path to flight database
DB_PATH = Path(__file__).resolve().parents[2] / "flight_data.db"


def get_db_connection():
    """Get a SQLite database connection."""
    return sqlite3.connect(DB_PATH)


def run_clustering_if_needed():
    """Import and run clustering, returns the clustered DataFrame."""
    import sys
    clustering_path = Path(__file__).resolve().parents[1] / "clustering"
    if str(clustering_path) not in sys.path:
        sys.path.insert(0, str(clustering_path))
    
    from cluster_airspace import load_data, hierarchical_cluster
    
    df = load_data(DB_PATH)
    df_clustered = hierarchical_cluster(
        df,
        eps_geo_km=5.0,
        eps_alt=500.0,
        min_samples_geo=10,
        min_samples_alt=10,
    )
    return df_clustered


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Flight Tracker API", "endpoints": ["/api/flights"]}



@app.get("/api/flights")
async def get_flights():
    """Get current flight positions within the defined bounds"""
    try:
        # Get flight data from FR24
        flights_data = client.live.flight_positions.get_full(bounds=BOUNDS)
        
        
        return JSONResponse(content=flights_data.model_dump())
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to fetch flight data"}
        )


@app.get("/api/flights/tracks/{flight_id}")
async def get_flight_tracks(flight_id: str):
    try:
        track = client.flight_tracks.get(flight_id=flight_id)
        
        return JSONResponse(content=track.model_dump())
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to fetch flight track"}
        )

@app.get("/api/flights/count")
async def get_flight_count():
    """Get the count of current flights"""
    try:
        flights_data = client.live.flight_positions.get_full(bounds=BOUNDS)
        flights_dict = flights_data.model_dump()
        
        flight_count = len(flights_dict.get("data", []))
        
        return {"count": flight_count}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to fetch flight count"}
        )


# ─────────────────────────────────────────────────────────────────────────────
# CLUSTER ENDPOINTS - For visualizing historical flight paths by cluster
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/clusters/routes")
async def get_cluster_routes():
    """Get all unique origin-destination pairs from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT f.orig_icao, f.dest_icao, COUNT(fp.id) as point_count
            FROM flights f
            JOIN flight_points fp ON f.fr24_id = fp.fr24_id
            WHERE f.orig_icao IS NOT NULL AND f.dest_icao IS NOT NULL
            GROUP BY f.orig_icao, f.dest_icao
            ORDER BY point_count DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        routes = [
            {"origin": row[0], "dest": row[1], "point_count": row[2]}
            for row in rows
        ]
        return {"routes": routes, "count": len(routes)}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to fetch routes"}
        )


@app.get("/api/clusters/data")
async def get_clustered_data(
    origin: Optional[str] = Query(None, description="Origin ICAO code"),
    dest: Optional[str] = Query(None, description="Destination ICAO code"),
    geo_cluster: Optional[int] = Query(None, description="Geographic cluster ID"),
    alt_cluster: Optional[int] = Query(None, description="Altitude cluster ID"),
):
    """
    Get clustered flight path data with optional filters.
    Returns points grouped by fr24_id (flight) with cluster labels.
    """
    try:
        df = run_clustering_if_needed()
        
        # Apply filters
        if origin:
            df = df[df["orig_icao"] == origin]
        if dest:
            df = df[df["dest_icao"] == dest]
        if geo_cluster is not None:
            df = df[df["geo_cluster"] == geo_cluster]
        if alt_cluster is not None:
            df = df[df["alt_cluster"] == alt_cluster]
        
        if df.empty:
            return {"flights": [], "summary": {"total_points": 0, "total_flights": 0}}
        
        # Group by flight and build response
        flights = []
        for fr24_id, group in df.groupby("fr24_id"):
            group_sorted = group.sort_values("point_order")
            points = [
                {
                    "lat": row["lat"],
                    "lon": row["lon"],
                    "alt": row["alt"],
                    "timestamp": row["timestamp"],
                    "geo_cluster": int(row["geo_cluster"]),
                    "alt_cluster": int(row["alt_cluster"]),
                }
                for _, row in group_sorted.iterrows()
            ]
            flights.append({
                "fr24_id": fr24_id,
                "origin": group["orig_icao"].iloc[0],
                "dest": group["dest_icao"].iloc[0],
                "geo_cluster": int(group["geo_cluster"].iloc[0]),
                "alt_cluster": int(group["alt_cluster"].iloc[0]),
                "points": points,
            })
        
        # Summary stats
        summary = {
            "total_points": len(df),
            "total_flights": len(flights),
            "geo_clusters": sorted([c for c in df["geo_cluster"].unique() if c != -1]),
            "alt_clusters": sorted([c for c in df["alt_cluster"].unique() if c != -1]),
        }
        
        return {"flights": flights, "summary": summary}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to fetch clustered data"}
        )


@app.get("/api/clusters/summary")
async def get_cluster_summary(
    origin: Optional[str] = Query(None, description="Origin ICAO code"),
    dest: Optional[str] = Query(None, description="Destination ICAO code"),
):
    """
    Get a summary of clusters for a given O/D pair (or all if not specified).
    Returns cluster IDs and point counts without full point data.
    """
    try:
        df = run_clustering_if_needed()
        
        if origin:
            df = df[df["orig_icao"] == origin]
        if dest:
            df = df[df["dest_icao"] == dest]
        
        if df.empty:
            return {"clusters": [], "summary": {}}
        
        # Build cluster summary
        cluster_summary = []
        for (geo_id,), grp in df.groupby(["geo_cluster"]):
            if geo_id == -1:
                continue
            alt_clusters = grp["alt_cluster"].value_counts().to_dict()
            cluster_summary.append({
                "geo_cluster": int(geo_id),
                "point_count": len(grp),
                "flight_count": grp["fr24_id"].nunique(),
                "alt_clusters": {int(k): int(v) for k, v in alt_clusters.items() if k != -1},
                "center_lat": float(grp["lat"].mean()),
                "center_lon": float(grp["lon"].mean()),
                "avg_alt": float(grp["alt"].mean()) if grp["alt"].notna().any() else None,
            })
        
        summary = {
            "total_points": len(df),
            "total_flights": df["fr24_id"].nunique(),
            "noise_points": int((df["geo_cluster"] == -1).sum()),
            "od_pair": f"{origin or '*'} -> {dest or '*'}",
        }
        
        return {"clusters": cluster_summary, "summary": summary}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to fetch cluster summary"}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
