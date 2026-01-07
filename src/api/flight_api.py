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

# Path to flight database and clusters files
DB_PATH = Path(__file__).resolve().parents[2] / "flight_data.db"
CLUSTERS_CSV_PATH = Path(__file__).resolve().parents[2] / "clusters.csv"
TRAJECTORY_CLUSTERS_PATH = Path(__file__).resolve().parents[2] / "trajectory_clusters.json"
PATH_CENTRELINES_CSV = Path(__file__).resolve().parents[2] / "path_centrelines.csv"

# Cache for cluster data - loaded once at startup
_clusters_df_cache = None
_trajectory_clusters_cache = None
_centrelines_df_cache = None
_flight_path_assignments_cache = None


def get_db_connection():
    """Get a SQLite database connection."""
    return sqlite3.connect(DB_PATH)


def load_clusters_df():
    """Load pre-computed cluster data from CSV (cached in memory)."""
    global _clusters_df_cache
    import pandas as pd
    
    if _clusters_df_cache is None:
        if not CLUSTERS_CSV_PATH.exists():
            raise FileNotFoundError(
                f"Clusters CSV not found at {CLUSTERS_CSV_PATH}. "
                "Run 'python src/clustering/cluster_airspace.py --out clusters.csv' first."
            )
        print(f"Loading clusters from {CLUSTERS_CSV_PATH}...")
        _clusters_df_cache = pd.read_csv(CLUSTERS_CSV_PATH)
        print(f"Loaded {len(_clusters_df_cache):,} points from clusters.csv")
    
    return _clusters_df_cache


def reload_clusters():
    """Force reload of cluster data from CSV."""
    global _clusters_df_cache
    _clusters_df_cache = None
    return load_clusters_df()


def load_trajectory_clusters():
    """Load pre-computed trajectory clusters from JSON (cached in memory)."""
    global _trajectory_clusters_cache
    
    if _trajectory_clusters_cache is None:
        if not TRAJECTORY_CLUSTERS_PATH.exists():
            raise FileNotFoundError(
                f"Trajectory clusters not found at {TRAJECTORY_CLUSTERS_PATH}. "
                "Run 'python src/clustering/trajectory_clustering.py' first."
            )
        print(f"Loading trajectory clusters from {TRAJECTORY_CLUSTERS_PATH}...")
        with open(TRAJECTORY_CLUSTERS_PATH, 'r') as f:
            _trajectory_clusters_cache = json.load(f)
        print(f"Loaded {_trajectory_clusters_cache['summary']['total_routes']} routes")
    
    return _trajectory_clusters_cache


def reload_trajectory_clusters():
    """Force reload of trajectory clusters from JSON."""
    global _trajectory_clusters_cache
    _trajectory_clusters_cache = None
    return load_trajectory_clusters()


def load_centrelines():
    """Load pre-computed path centre-lines from CSV (cached in memory)."""
    global _centrelines_df_cache
    import pandas as pd
    
    if _centrelines_df_cache is None:
        if not PATH_CENTRELINES_CSV.exists():
            raise FileNotFoundError(
                f"Path centrelines not found at {PATH_CENTRELINES_CSV}. "
                "Run clustering and centreline generation first."
            )
        print(f"Loading centrelines from {PATH_CENTRELINES_CSV}...")
        _centrelines_df_cache = pd.read_csv(PATH_CENTRELINES_CSV)
        print(f"Loaded {_centrelines_df_cache['path_id'].nunique()} unique paths")
    
    return _centrelines_df_cache


def load_flight_path_assignments():
    """Build flight → path_id assignments with deviation metrics (cached)."""
    global _flight_path_assignments_cache
    import pandas as pd
    
    if _flight_path_assignments_cache is None:
        df = load_clusters_df()
        
        # Assign each flight to its most common path_id
        def most_common_path(grp):
            mode_result = grp["path_id"].mode()
            if len(mode_result) == 0:
                return "NO_PATH"
            return mode_result.iloc[0]
        
        flight_path = df.groupby("fr24_id").apply(most_common_path)
        
        # Calculate deviation ratio (proportion of points NOT on the assigned path)
        def calc_deviation(grp):
            assigned_path = flight_path.get(grp.name, "NO_PATH")
            if assigned_path == "NO_PATH":
                return 1.0
            return (grp["path_id"] != assigned_path).mean()
        
        deviation_ratio = df.groupby("fr24_id").apply(calc_deviation)
        
        _flight_path_assignments_cache = pd.DataFrame({
            "fr24_id": flight_path.index,
            "assigned_path_id": flight_path.values,
            "deviation_ratio": deviation_ratio.values
        })
        print(f"Computed path assignments for {len(_flight_path_assignments_cache)} flights")
    
    return _flight_path_assignments_cache


def reload_centrelines():
    """Force reload of centrelines data."""
    global _centrelines_df_cache, _flight_path_assignments_cache
    _centrelines_df_cache = None
    _flight_path_assignments_cache = None
    return load_centrelines()


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
    """Get all unique origin-destination pairs from the clusters CSV."""
    try:
        df = load_clusters_df()
        
        # Group by O/D and count points
        routes_df = df.groupby(["orig_icao", "dest_icao"]).size().reset_index(name="point_count")
        routes_df = routes_df.sort_values("point_count", ascending=False)
        
        routes = [
            {
                "origin": str(row["orig_icao"]),
                "dest": str(row["dest_icao"]),
                "point_count": int(row["point_count"])
            }
            for _, row in routes_df.iterrows()
        ]
        return JSONResponse(content={"routes": routes, "count": len(routes)})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to fetch routes"}
        )


def to_python(val):
    """Convert numpy types to native Python types for JSON serialization."""
    import numpy as np
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return val


@app.get("/api/clusters/reload")
async def reload_cluster_data():
    """Force reload cluster data from CSV file."""
    try:
        df = reload_clusters()
        return {"message": "Clusters reloaded", "total_points": len(df)}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to reload clusters"}
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
        df = load_clusters_df().copy()
        
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
            return JSONResponse(content={"flights": [], "summary": {"total_points": 0, "total_flights": 0}})
        
        # Group by flight and build response
        flights = []
        for fr24_id, group in df.groupby("fr24_id"):
            group_sorted = group.sort_values("point_order")
            points = [
                {
                    "lat": to_python(row["lat"]),
                    "lon": to_python(row["lon"]),
                    "alt": to_python(row["alt"]),
                    "timestamp": str(row["timestamp"]) if row["timestamp"] else None,
                    "geo_cluster": to_python(row["geo_cluster"]),
                    "alt_cluster": to_python(row["alt_cluster"]),
                }
                for _, row in group_sorted.iterrows()
            ]
            flights.append({
                "fr24_id": str(fr24_id),
                "origin": str(group["orig_icao"].iloc[0]),
                "dest": str(group["dest_icao"].iloc[0]),
                "geo_cluster": to_python(group["geo_cluster"].iloc[0]),
                "alt_cluster": to_python(group["alt_cluster"].iloc[0]),
                "points": points,
            })
        
        # Summary stats - convert numpy types
        geo_clusters = [int(c) for c in df["geo_cluster"].unique() if c != -1]
        alt_clusters = [int(c) for c in df["alt_cluster"].unique() if c != -1]
        
        summary = {
            "total_points": int(len(df)),
            "total_flights": int(len(flights)),
            "geo_clusters": sorted(geo_clusters),
            "alt_clusters": sorted(alt_clusters),
        }
        
        return JSONResponse(content={"flights": flights, "summary": summary})
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
        df = load_clusters_df().copy()
        
        if origin:
            df = df[df["orig_icao"] == origin]
        if dest:
            df = df[df["dest_icao"] == dest]
        
        if df.empty:
            return JSONResponse(content={"clusters": [], "summary": {}})
        
        # Build cluster summary
        cluster_summary = []
        for (geo_id,), grp in df.groupby(["geo_cluster"]):
            if geo_id == -1:
                continue
            alt_clusters = grp["alt_cluster"].value_counts().to_dict()
            cluster_summary.append({
                "geo_cluster": int(geo_id),
                "point_count": int(len(grp)),
                "flight_count": int(grp["fr24_id"].nunique()),
                "alt_clusters": {int(k): int(v) for k, v in alt_clusters.items() if k != -1},
                "center_lat": float(grp["lat"].mean()),
                "center_lon": float(grp["lon"].mean()),
                "avg_alt": float(grp["alt"].mean()) if grp["alt"].notna().any() else None,
            })
        
        summary = {
            "total_points": int(len(df)),
            "total_flights": int(df["fr24_id"].nunique()),
            "noise_points": int((df["geo_cluster"] == -1).sum()),
            "od_pair": f"{origin or '*'} -> {dest or '*'}",
        }
        
        return JSONResponse(content={"clusters": cluster_summary, "summary": summary})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to fetch cluster summary"}
        )


# ─────────────────────────────────────────────────────────────────────────────
# TRAJECTORY ROUTE ENDPOINTS - Aggregated flight corridors
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/routes")
async def get_all_routes():
    """
    Get all aggregated flight routes (trajectory clusters).
    Returns representative paths showing distinct ways to fly between airports.
    """
    try:
        data = load_trajectory_clusters()
        return JSONResponse(content=data)
    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"error": str(e), "message": "Run trajectory clustering first"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to load routes"}
        )


@app.get("/api/routes/list")
async def get_routes_list():
    """Get list of O/D pairs with route counts."""
    try:
        data = load_trajectory_clusters()
        routes_list = [
            {
                "origin": r["origin"],
                "dest": r["dest"],
                "total_flights": r["total_flights"],
                "num_routes": r["num_routes"]
            }
            for r in data["routes"]
        ]
        return JSONResponse(content={
            "routes": routes_list,
            "summary": data["summary"]
        })
    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"error": str(e), "message": "Run trajectory clustering first"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to load routes"}
        )


@app.get("/api/routes/{origin}/{dest}")
async def get_route_corridors(origin: str, dest: str):
    """
    Get aggregated route corridors for a specific O/D pair.
    Returns representative paths showing the distinct ways to fly this route.
    """
    try:
        data = load_trajectory_clusters()
        
        # Find matching O/D pair
        for route in data["routes"]:
            if route["origin"] == origin and route["dest"] == dest:
                return JSONResponse(content=route)
        
        return JSONResponse(
            status_code=404,
            content={"error": f"No routes found for {origin} -> {dest}"}
        )
    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"error": str(e), "message": "Run trajectory clustering first"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to load route"}
        )


@app.get("/api/routes/reload")
async def reload_routes():
    """Force reload trajectory clusters from JSON file."""
    try:
        data = reload_trajectory_clusters()
        return {"message": "Routes reloaded", "total_routes": data["summary"]["total_routes"]}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to reload routes"}
        )


# ─────────────────────────────────────────────────────────────────────────────
# PATH CENTRELINE ENDPOINTS - Representative paths for deviation detection
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/path/{origin}/{dest}")
async def get_path_centrelines(origin: str, dest: str):
    """
    Get centre-line paths for a specific origin-destination pair.
    Returns all discovered path variants (geo/alt clusters) with 50-point centre-lines.
    """
    try:
        cl_df = load_centrelines()
        
        # Filter for this O/D pair
        filtered = cl_df[
            (cl_df["origin"] == origin) & (cl_df["dest"] == dest)
        ]
        
        if filtered.empty:
            return JSONResponse(
                status_code=404,
                content={"error": f"No paths found for {origin} -> {dest}"}
            )
        
        # Group by path_id
        paths = []
        for path_id, grp in filtered.groupby("path_id"):
            grp_sorted = grp.sort_values("progress")
            points = [
                {
                    "progress": float(row["progress"]),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"])
                }
                for _, row in grp_sorted.iterrows()
            ]
            paths.append({
                "path_id": str(path_id),
                "geo_cluster": int(grp["geo_cluster"].iloc[0]),
                "alt_cluster": int(grp["alt_cluster"].iloc[0]),
                "points": points
            })
        
        return JSONResponse(content={
            "origin": origin,
            "dest": dest,
            "num_paths": len(paths),
            "paths": paths
        })
    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"error": str(e), "message": "Run centreline generation first"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to load path centrelines"}
        )


@app.get("/api/flight/{fr24_id}/deviation")
async def get_flight_deviation(fr24_id: str):
    """
    Check if a historical flight deviates from normal paths.
    Returns:
      - assigned_path_id: The most common path this flight followed
      - deviation_ratio: Fraction of points NOT on the assigned path (0.0 = perfect, 1.0 = completely off)
      - is_off_path: True if deviation_ratio > 0.2 (20% threshold)
    """
    try:
        assignments = load_flight_path_assignments()
        
        # Find this flight
        flight_data = assignments[assignments["fr24_id"] == fr24_id]
        
        if flight_data.empty:
            return JSONResponse(
                status_code=404,
                content={"error": f"Flight {fr24_id} not found in clustered data"}
            )
        
        row = flight_data.iloc[0]
        deviation_ratio = float(row["deviation_ratio"])
        assigned_path = str(row["assigned_path_id"])
        
        # Parse path components if valid
        path_components = None
        if assigned_path != "NO_PATH":
            parts = assigned_path.split("_")
            if len(parts) == 4:
                path_components = {
                    "origin": parts[0],
                    "dest": parts[1],
                    "geo_cluster": int(parts[2]),
                    "alt_cluster": int(parts[3])
                }
        
        return JSONResponse(content={
            "fr24_id": fr24_id,
            "assigned_path_id": assigned_path,
            "path_components": path_components,
            "deviation_ratio": deviation_ratio,
            "is_off_path": deviation_ratio > 0.2,  # 20% threshold
            "status": "off-path" if deviation_ratio > 0.2 else "normal"
        })
    except FileNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={"error": str(e), "message": "Run clustering first"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to compute deviation"}
        )


@app.get("/api/centrelines/reload")
async def reload_centrelines_endpoint():
    """Force reload centreline data from CSV file."""
    try:
        df = reload_centrelines()
        return {"message": "Centrelines reloaded", "total_paths": df["path_id"].nunique()}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to reload centrelines"}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
