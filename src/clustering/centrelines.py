"""Compute representative centre-lines per path_id and store as CSV.
Run after cluster_airspace.hierarchical_cluster has produced a labelled
DataFrame.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import pandas as pd
import numpy as np


def centreline(points: pd.DataFrame, n_samples: int = 50) -> pd.DataFrame:
    """Return *n_samples* equally-spaced lat/lon points representing the path."""
    points = points.sort_values("point_order")
    points["progress"] = (
        points.groupby("fr24_id")
        ["point_order"].rank(method="first")
    )
    points["progress"] /= points.groupby("fr24_id")["point_order"].transform("max")

    grid = np.linspace(0, 1, n_samples)
    lat = np.interp(grid, points["progress"], points["lat"])
    lon = np.interp(grid, points["progress"], points["lon"])
    return pd.DataFrame({"progress": grid, "lat": lat, "lon": lon})


def build_centrelines(df: pd.DataFrame, n_samples: int = 50) -> pd.DataFrame:
    # Check if path_id column exists
    if "path_id" not in df.columns:
        raise ValueError(
            "path_id column not found in input CSV. "
            "Please re-run cluster_airspace.py with the updated version to generate path_id."
        )
    
    cl_df = (
        df.groupby("path_id", group_keys=False, as_index=False)
        .apply(lambda g: centreline(g, n_samples), include_groups=False)
        .reset_index(drop=True)
    )
    
    # Get path_id from original data
    path_ids = df.groupby("path_id").first().reset_index()[["path_id"]]
    
    # Repeat each path_id n_samples times to match centreline points
    path_ids_expanded = []
    for _, row in path_ids.iterrows():
        path_ids_expanded.extend([row["path_id"]] * n_samples)
    
    cl_df["path_id"] = path_ids_expanded[:len(cl_df)]
    
    # split path_id back into components for easier querying
    comp = cl_df["path_id"].str.split("_", expand=True)
    cl_df["origin"], cl_df["dest"], cl_df["geo_cluster"], cl_df["alt_cluster"] = comp[0], comp[1], comp[2].astype(int), comp[3].astype(int)
    return cl_df


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cluster_csv", type=Path, help="CSV with clustered points inc. path_id")
    ap.add_argument("output_csv", type=Path, help="Destination centre-lines CSV")
    ns = ap.parse_args(argv)

    df = pd.read_csv(ns.cluster_csv)
    cl = build_centrelines(df)
    ns.output_csv.parent.mkdir(parents=True, exist_ok=True)
    cl.to_csv(ns.output_csv, index=False)
    print(f"Written {len(cl['path_id'].unique())} path centre-lines to {ns.output_csv}")


if __name__ == "__main__":
    main()
