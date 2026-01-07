"""trajectory_clustering.py

Proper trajectory-based clustering for airspace path analysis.

This clusters FULL FLIGHT TRAJECTORIES (not individual points) to identify
distinct route corridors between origin-destination pairs.

Approach:
1. Load flights grouped by O/D pair
2. Resample each trajectory to a fixed number of waypoints
3. Compute pairwise trajectory distances using Fréchet distance
4. Cluster trajectories using hierarchical clustering
5. Compute a representative centerline for each cluster

Output: Aggregated route corridors showing the X distinct ways to fly from A to B.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import List, Tuple, Dict
import json

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

# Earth radius for haversine calculations
EARTH_RADIUS_KM = 6371.0088


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two points in km."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def resample_trajectory(coords: np.ndarray, n_points: int = 50) -> np.ndarray:
    """
    Resample a trajectory to exactly n_points evenly spaced along its length.
    
    Args:
        coords: (N, 2) array of [lat, lon] points
        n_points: Number of points to resample to
    
    Returns:
        (n_points, 2) array of resampled [lat, lon] points
    """
    if len(coords) < 2:
        return np.repeat(coords, n_points, axis=0)[:n_points]
    
    # Compute cumulative distance along trajectory
    distances = [0.0]
    for i in range(1, len(coords)):
        d = haversine_distance(coords[i-1, 0], coords[i-1, 1], coords[i, 0], coords[i, 1])
        distances.append(distances[-1] + d)
    
    total_length = distances[-1]
    if total_length == 0:
        return np.repeat(coords[:1], n_points, axis=0)
    
    distances = np.array(distances)
    
    # Interpolate at evenly spaced distances
    target_distances = np.linspace(0, total_length, n_points)
    resampled = np.zeros((n_points, 2))
    
    for i, target_d in enumerate(target_distances):
        # Find segment containing this distance
        idx = np.searchsorted(distances, target_d, side='right') - 1
        idx = max(0, min(idx, len(coords) - 2))
        
        # Linear interpolation within segment
        seg_start = distances[idx]
        seg_end = distances[idx + 1]
        seg_length = seg_end - seg_start
        
        if seg_length > 0:
            t = (target_d - seg_start) / seg_length
        else:
            t = 0
        
        resampled[i] = coords[idx] + t * (coords[idx + 1] - coords[idx])
    
    return resampled


def frechet_distance(traj1: np.ndarray, traj2: np.ndarray) -> float:
    """
    Compute discrete Fréchet distance between two trajectories.
    
    This measures the similarity of two curves considering their ordering,
    often described as the minimum leash length for a person walking a dog
    where both must walk along their respective paths.
    
    Args:
        traj1, traj2: (N, 2) arrays of [lat, lon] points (should be same length)
    
    Returns:
        Fréchet distance in km
    """
    n, m = len(traj1), len(traj2)
    
    # Build distance matrix between all point pairs
    dist_matrix = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            dist_matrix[i, j] = haversine_distance(
                traj1[i, 0], traj1[i, 1], traj2[j, 0], traj2[j, 1]
            )
    
    # Dynamic programming for Fréchet distance
    ca = np.full((n, m), -1.0)
    
    def _c(i: int, j: int) -> float:
        if ca[i, j] > -0.5:
            return ca[i, j]
        
        if i == 0 and j == 0:
            ca[i, j] = dist_matrix[0, 0]
        elif i > 0 and j == 0:
            ca[i, j] = max(_c(i - 1, 0), dist_matrix[i, 0])
        elif i == 0 and j > 0:
            ca[i, j] = max(_c(0, j - 1), dist_matrix[0, j])
        else:
            ca[i, j] = max(
                min(_c(i - 1, j), _c(i - 1, j - 1), _c(i, j - 1)),
                dist_matrix[i, j]
            )
        return ca[i, j]
    
    return _c(n - 1, m - 1)


def compute_centroid_trajectory(trajectories: List[np.ndarray]) -> np.ndarray:
    """
    Compute the centroid (mean) trajectory from a list of trajectories.
    All trajectories should have the same number of points.
    
    Args:
        trajectories: List of (N, 2) arrays
    
    Returns:
        (N, 2) array representing the mean trajectory
    """
    if not trajectories:
        return np.array([])
    
    stacked = np.stack(trajectories, axis=0)  # (num_traj, n_points, 2)
    return np.mean(stacked, axis=0)


def load_flights_by_od(db_path: Path) -> Dict[Tuple[str, str], List[dict]]:
    """
    Load flights from database, grouped by origin-destination pair.
    
    Returns:
        Dict mapping (origin, dest) -> list of flight dicts with 'fr24_id' and 'points'
    """
    conn = sqlite3.connect(db_path)
    
    # Get flights with their O/D
    flights_df = pd.read_sql("""
        SELECT fr24_id, orig_icao, dest_icao 
        FROM flights 
        WHERE orig_icao IS NOT NULL AND dest_icao IS NOT NULL
    """, conn)
    
    # Get all points
    points_df = pd.read_sql("""
        SELECT fr24_id, lat, lon, alt, point_order 
        FROM flight_points
        ORDER BY fr24_id, point_order
    """, conn)
    
    conn.close()
    
    # Group by O/D
    od_flights = {}
    
    for _, flight in flights_df.iterrows():
        fr24_id = flight['fr24_id']
        od_key = (flight['orig_icao'], flight['dest_icao'])
        
        # Get points for this flight
        flight_points = points_df[points_df['fr24_id'] == fr24_id].sort_values('point_order')
        
        if len(flight_points) < 5:  # Skip flights with too few points
            continue
        
        coords = flight_points[['lat', 'lon']].values
        alts = flight_points['alt'].values
        
        if od_key not in od_flights:
            od_flights[od_key] = []
        
        od_flights[od_key].append({
            'fr24_id': fr24_id,
            'coords': coords,
            'alts': alts
        })
    
    return od_flights


def cluster_trajectories(
    flights: List[dict],
    n_resample: int = 50,
    distance_threshold_km: float = 20.0,
    min_cluster_size: int = 2
) -> List[dict]:
    """
    Cluster flight trajectories and compute representative paths.
    
    Args:
        flights: List of flight dicts with 'fr24_id', 'coords', 'alts'
        n_resample: Number of points to resample trajectories to
        distance_threshold_km: Max Fréchet distance for same cluster
        min_cluster_size: Minimum flights to form a valid cluster
    
    Returns:
        List of cluster dicts with 'cluster_id', 'flight_ids', 'representative_path', 'flight_count'
    """
    if len(flights) < 2:
        if len(flights) == 1:
            return [{
                'cluster_id': 0,
                'flight_ids': [flights[0]['fr24_id']],
                'representative_path': flights[0]['coords'].tolist(),
                'avg_alt': float(np.nanmean(flights[0]['alts'])) if len(flights[0]['alts']) > 0 else None,
                'flight_count': 1
            }]
        return []
    
    # Resample all trajectories to same length
    resampled = [resample_trajectory(f['coords'], n_resample) for f in flights]
    
    n_flights = len(flights)
    
    # Compute pairwise Fréchet distances
    print(f"    Computing {n_flights * (n_flights - 1) // 2} pairwise distances...")
    dist_matrix = np.zeros((n_flights, n_flights))
    
    for i in range(n_flights):
        for j in range(i + 1, n_flights):
            d = frechet_distance(resampled[i], resampled[j])
            dist_matrix[i, j] = d
            dist_matrix[j, i] = d
    
    # Hierarchical clustering
    condensed = squareform(dist_matrix)
    if len(condensed) == 0:
        return []
    
    Z = linkage(condensed, method='average')
    labels = fcluster(Z, t=distance_threshold_km, criterion='distance')
    
    # Build clusters
    clusters = {}
    for idx, label in enumerate(labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(idx)
    
    # Compute representative path for each cluster
    results = []
    cluster_id = 0
    
    for label, indices in clusters.items():
        if len(indices) < min_cluster_size:
            continue  # Skip small clusters (noise)
        
        cluster_trajectories = [resampled[i] for i in indices]
        centroid = compute_centroid_trajectory(cluster_trajectories)
        
        # Average altitude
        all_alts = []
        for i in indices:
            all_alts.extend(flights[i]['alts'].tolist())
        avg_alt = float(np.nanmean(all_alts)) if all_alts else None
        
        results.append({
            'cluster_id': cluster_id,
            'flight_ids': [flights[i]['fr24_id'] for i in indices],
            'representative_path': centroid.tolist(),
            'avg_alt': avg_alt,
            'flight_count': len(indices)
        })
        cluster_id += 1
    
    # Sort by flight count descending
    results.sort(key=lambda x: x['flight_count'], reverse=True)
    
    # Re-assign cluster IDs after sorting
    for i, r in enumerate(results):
        r['cluster_id'] = i
    
    return results


def run_trajectory_clustering(
    db_path: Path,
    n_resample: int = 50,
    distance_threshold_km: float = 20.0,
    min_cluster_size: int = 2
) -> Dict:
    """
    Run full trajectory clustering pipeline.
    
    Returns:
        Dict with 'routes' containing clustered paths for each O/D pair
    """
    print(f"Loading flights from {db_path}...")
    od_flights = load_flights_by_od(db_path)
    
    print(f"Found {len(od_flights)} origin-destination pairs")
    
    all_routes = []
    
    for (origin, dest), flights in od_flights.items():
        print(f"  {origin} -> {dest}: {len(flights)} flights")
        
        if len(flights) < min_cluster_size:
            print(f"    Skipping (fewer than {min_cluster_size} flights)")
            continue
        
        clusters = cluster_trajectories(
            flights,
            n_resample=n_resample,
            distance_threshold_km=distance_threshold_km,
            min_cluster_size=min_cluster_size
        )
        
        if clusters:
            route_data = {
                'origin': origin,
                'dest': dest,
                'total_flights': len(flights),
                'num_routes': len(clusters),
                'routes': clusters
            }
            all_routes.append(route_data)
            print(f"    Found {len(clusters)} distinct route(s)")
    
    return {
        'routes': all_routes,
        'summary': {
            'total_od_pairs': len(all_routes),
            'total_routes': sum(r['num_routes'] for r in all_routes)
        }
    }


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Trajectory-based clustering for airspace analysis")
    default_db = Path(__file__).resolve().parents[2] / "flight_data.db"
    
    p.add_argument("db", type=Path, nargs="?", default=default_db,
                   help=f"Path to SQLite database (default: {default_db})")
    p.add_argument("--n-resample", type=int, default=50,
                   help="Number of points to resample trajectories (default: 50)")
    p.add_argument("--distance-threshold", type=float, default=20.0,
                   help="Max Fréchet distance (km) for same cluster (default: 20)")
    p.add_argument("--min-cluster-size", type=int, default=2,
                   help="Minimum flights to form a cluster (default: 2)")
    p.add_argument("--out", type=Path, default=None,
                   help="Output JSON file (default: trajectory_clusters.json)")
    
    return p.parse_args(argv)


def main():
    args = parse_args()
    
    result = run_trajectory_clustering(
        args.db,
        n_resample=args.n_resample,
        distance_threshold_km=args.distance_threshold,
        min_cluster_size=args.min_cluster_size
    )
    
    print(f"\n=== Summary ===")
    print(f"O/D pairs with routes: {result['summary']['total_od_pairs']}")
    print(f"Total distinct routes: {result['summary']['total_routes']}")
    
    # Save to JSON
    out_path = args.out or Path(__file__).resolve().parents[2] / "trajectory_clusters.json"
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
