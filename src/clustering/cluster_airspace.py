"""cluster_airspace.py

Utility script that loads flight track points from a local SQLite database and
performs a three-level clustering:

1. First by origin / destination airport pair (ICAO codes).
2. Inside each O/D pair by geographic trajectory similarity (lat / lon) using
   DBSCAN with the Haversine metric.
3. Inside each geographic cluster by altitude profile, again using DBSCAN.

The result is a hierarchical labelling of every point and flight which can be
used to understand the structure of the airspace with high mathematical
fidelity.

---
Database schema (flight_data.db):

flights table
──────────────
    id              INTEGER PRIMARY KEY AUTOINCREMENT
    fr24_id         TEXT UNIQUE NOT NULL
    orig_icao       TEXT            -- ICAO origin code
    dest_icao       TEXT            -- ICAO destination code
    ... (other metadata)

flight_points table
───────────────────
    id              INTEGER PRIMARY KEY AUTOINCREMENT
    fr24_id         TEXT NOT NULL   -- FK → flights.fr24_id
    timestamp       TEXT NOT NULL
    lat             REAL NOT NULL   -- degrees
    lon             REAL NOT NULL   -- degrees
    alt             INTEGER         -- feet
    point_order     INTEGER
    ... (other fields)

---
Math / clustering details
────────────────────────
* Geographic clustering uses DBSCAN with the Haversine metric (great-circle
  distance). ``eps_geo`` is expressed in kilometres and internally converted
  to radians (``eps_km / EarthRadius``).
* Altitude clustering again uses DBSCAN but on the *alt* axis only. ``eps_alt``
  is given in the same unit as *alt* in the database (feet).

Both DBSCAN stages are density-based and do not require the number of clusters
in advance, making them suitable for air-traffic data where the structure is
not known a-priori.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

EARTH_RADIUS_KM = 6_371.0088  # IUGG mean Earth radius


def load_data(db_path: Path) -> pd.DataFrame:
    """Return a *single* DataFrame joining flights and flight_points.

    The resulting frame has columns:
        fr24_id, orig_icao, dest_icao, timestamp, lat, lon, alt, point_order
    """

    con = sqlite3.connect(db_path)
    try:
        flights = pd.read_sql(
            "SELECT fr24_id, orig_icao, dest_icao FROM flights", con
        )
        points = pd.read_sql(
            "SELECT id, fr24_id, timestamp, lat, lon, alt, point_order FROM flight_points",
            con,
        )
    finally:
        con.close()

    df = points.merge(flights, on="fr24_id", how="left", validate="many_to_one")
    missing = df["orig_icao"].isna().sum()
    if missing:
        print(f"Warning: {missing} points reference flights not present in 'flights' table – dropping them")
        df = df.dropna(subset=["orig_icao", "dest_icao"])
    return df


def haversine_dbscan(
    coords_deg: np.ndarray, *, eps_km: float = 5.0, min_samples: int = 20
) -> np.ndarray:
    """Cluster lat-lon coordinates using DBSCAN-Haversine.

    Parameters
    ----------
    coords_deg : (N, 2) ndarray of **degrees** [lat, lon].
    eps_km     : Maximum cluster radius in kilometres.
    min_samples: Standard DBSCAN density parameter.

    Returns
    -------
    labels : (N,) ndarray of cluster labels (-1 denotes noise).
    """

    # Convert to radians for haversine metric as required by scikit-learn.
    coords_rad = np.radians(coords_deg)
    eps_rad = eps_km / EARTH_RADIUS_KM
    model = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine")
    return model.fit_predict(coords_rad)


def altitude_dbscan(alt: np.ndarray, *, eps_alt: float = 300.0, min_samples: int = 20) -> np.ndarray:
    """1-D DBSCAN on altitude.

    eps_alt is in the same unit as the altitude column (metres or feet).
    """

    alt = alt.reshape(-1, 1)
    model = DBSCAN(eps=eps_alt, min_samples=min_samples, metric="euclidean")
    return model.fit_predict(alt)


def hierarchical_cluster(
    df: pd.DataFrame,
    *,
    eps_geo_km: float = 5.0,
    eps_alt: float = 300.0,
    min_samples_geo: int = 20,
    min_samples_alt: int = 20,
) -> pd.DataFrame:
    """Perform the three-level clustering and return the original DataFrame
    annotated with *geo_cluster* and *alt_cluster* columns.

    Hierarchy:
      Level 0 – Origin / Destination ICAO pair
      Level 1 – Geographic cluster (Haversine DBSCAN on lat/lon)
      Level 2 – Altitude cluster (Euclidean DBSCAN on alt)
    """

    df = df.copy()
    df["geo_cluster"] = -1  # initialise
    df["alt_cluster"] = -1

    # Level-0: iterate O/D pairs (vectorised grouping)
    od_groups = df.groupby(["orig_icao", "dest_icao"], sort=False)
    for (orig, dest), g_idx in od_groups.groups.items():
        # Work on a *view* for in-place labelling
        coords = df.loc[g_idx, ["lat", "lon"]].values.astype(float)
        labels_geo = haversine_dbscan(coords, eps_km=eps_geo_km, min_samples=min_samples_geo)
        df.loc[g_idx, "geo_cluster"] = labels_geo

        # Level-1: altitude clustering inside each geo cluster
        for geo_id in np.unique(labels_geo):
            if geo_id == -1:
                continue  # skip noise trajectory clusters
            geo_mask = (df.index.isin(g_idx)) & (df["geo_cluster"] == geo_id)
            altitudes = df.loc[geo_mask, "alt"].values.astype(float)
            labels_alt = altitude_dbscan(altitudes, eps_alt=eps_alt, min_samples=min_samples_alt)
            df.loc[geo_mask, "alt_cluster"] = labels_alt

    return df


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hierarchical airspace clustering script")
    default_db = Path(__file__).resolve().parents[2] / "flight_data.db"
    p.add_argument(
        "db",
        type=Path,
        nargs="?",
        default=default_db,
        help=f"Path to local SQLite database (default: {default_db})",
    )
    p.add_argument(
        "--eps-geo-km",
        type=float,
        default=5.0,
        help="DBSCAN eps for geographic clustering in kilometres (default: 5 km)",
    )
    p.add_argument(
        "--eps-alt",
        type=float,
        default=500.0,
        help="DBSCAN eps for altitude clustering in feet (default: 500 ft)",
    )
    p.add_argument(
        "--min-samples-geo",
        type=int,
        default=10,
        help="min_samples for geographic DBSCAN (default: 10)",
    )
    p.add_argument(
        "--min-samples-alt",
        type=int,
        default=10,
        help="min_samples for altitude DBSCAN (default: 10)",
    )
    p.add_argument(
        "--out",
        type=Path,
        help="Optional CSV file to write the labeled points",
    )
    return p.parse_args(argv)


def summarise_clusters(df: pd.DataFrame) -> None:
    """Print a summary of the clustering results."""
    od_pairs = df.groupby(["orig_icao", "dest_icao"]).ngroups
    print(f"\nOrigin-Destination pairs: {od_pairs}")

    # Count valid (non-noise) clusters
    has_noise_geo = -1 in df["geo_cluster"].values
    has_noise_alt = -1 in df["alt_cluster"].values
    n_geo = df["geo_cluster"].nunique() - (1 if has_noise_geo else 0)
    n_alt = df["alt_cluster"].nunique() - (1 if has_noise_alt else 0)
    print(f"Geographic clusters: {n_geo}")
    print(f"Altitude clusters:   {n_alt}")

    noise_geo_pct = (df["geo_cluster"] == -1).mean() * 100
    noise_alt_pct = (df["alt_cluster"] == -1).mean() * 100
    print(f"Noise (geo):  {noise_geo_pct:.1f}%")
    print(f"Noise (alt):  {noise_alt_pct:.1f}%")

    # Per-OD summary
    print("\n-- Per O/D pair summary --")
    for (orig, dest), grp in df.groupby(["orig_icao", "dest_icao"], sort=False):
        geo_ids = grp["geo_cluster"].unique()
        geo_ids = geo_ids[geo_ids != -1]
        print(f"  {orig} -> {dest}: {len(grp):,} pts, {len(geo_ids)} geo cluster(s)")


def main() -> None:
    args = parse_args()

    df = load_data(args.db)
    print(f"Loaded {len(df):,} points from {args.db}")
    print(f"Unique flights: {df['fr24_id'].nunique()}")

    df_clustered = hierarchical_cluster(
        df,
        eps_geo_km=args.eps_geo_km,
        eps_alt=args.eps_alt,
        min_samples_geo=args.min_samples_geo,
        min_samples_alt=args.min_samples_alt,
    )

    summarise_clusters(df_clustered)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        df_clustered.to_csv(args.out, index=False)
        print(f"\nLabelled data written to {args.out}")


if __name__ == "__main__":
    main()
