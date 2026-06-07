"""
Extract road network from Sumatra .osm.pbf file.

Input:  any .osm.pbf file (auto-detected from data-input/ or passed as argument)
Output: GeoJSON files per provinsi + 1 combined Sumatra file

Usage:
    python scripts/extract_road_network_pbf.py                          # auto-detect from data-input/
    python scripts/extract_road_network_pbf.py path/to/file.osm.pbf    # explicit path
"""

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import osmium
from shapely.geometry import LineString

# ================================================================
# KONFIGURASI
# ================================================================
_ROOT = Path(__file__).parent.parent


def _parse_args() -> Path:
    parser = argparse.ArgumentParser(
        description="Extract road network from a Sumatra .osm.pbf file."
    )
    parser.add_argument(
        "pbf_file",
        nargs="?",
        help="Path to .osm.pbf file (default: newest *.osm.pbf in data-input/)",
    )
    args = parser.parse_args()

    if args.pbf_file:
        p = Path(args.pbf_file)
        if not p.exists():
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(1)
        return p

    # Auto-detect newest .osm.pbf in data-input/
    candidates = sorted((_ROOT / "data-input").glob("*.osm.pbf"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not candidates:
        print("ERROR: No .osm.pbf found in data-input/. Pass a path as argument.", file=sys.stderr)
        sys.exit(1)
    print(f"Auto-detected: {candidates[0]}")
    return candidates[0]

PBF_FILE = _parse_args()
OUTPUT_DIR = _ROOT / "sumatera_jaringan_jalan"

KLASIFIKASI_STATUS = {
    "motorway": "Jalan Nasional",
    "motorway_link": "Jalan Nasional",
    "trunk": "Jalan Nasional",
    "trunk_link": "Jalan Nasional",
    "primary": "Jalan Nasional",
    "primary_link": "Jalan Nasional",
    "secondary": "Jalan Provinsi",
    "secondary_link": "Jalan Provinsi",
    "tertiary": "Jalan Kabupaten",
    "tertiary_link": "Jalan Kabupaten",
    "unclassified": "Jalan Kabupaten",
    "road": "Jalan Kabupaten",
    "residential": "Jalan Kota",
    "living_street": "Jalan Kota",
    "service": "Jalan Desa",
    "track": "Jalan Desa",
    "corridor": "Jalan Desa",
    "pedestrian": "Jalan Pejalan Kaki",
    "footway": "Jalan Pejalan Kaki",
    "path": "Jalan Pejalan Kaki",
    "steps": "Jalan Pejalan Kaki",
    "cycleway": "Jalan Pejalan Kaki",
    "bridleway": "Jalan Pejalan Kaki",
}


# ================================================================
# HANDLER: Extract road ways from .pbf
# ================================================================
class RoadHandler(osmium.SimpleHandler):
    """Extracts all ways with a 'highway' tag and builds geometries."""

    def __init__(self):
        super().__init__()
        self.roads = []
        self.count = 0

    def way(self, w):
        highway = w.tags.get("highway")
        if not highway:
            return

        # Skip non-road highway types
        if highway in ("proposed", "construction", "razed", "abandoned"):
            return

        # Build coordinate list from nodes
        try:
            coords = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            return

        if len(coords) < 2:
            return

        self.roads.append(
            {
                "geometry": coords,
                "highway": highway,
                "name": w.tags.get("name", ""),
                "oneway": w.tags.get("oneway", ""),
                "maxspeed": w.tags.get("maxspeed", ""),
                "surface": w.tags.get("surface", ""),
                "lanes": w.tags.get("lanes", ""),
                "ref": w.tags.get("ref", ""),
                "osm_id": w.id,
            }
        )

        self.count += 1
        if self.count % 100_000 == 0:
            print(f"  ... {self.count:,} jalan terbaca")


# ================================================================
# MAIN
# ================================================================
def main():
    start_time = time.time()

    print("=" * 60)
    print("EXTRACT ROAD NETWORK FROM .osm.pbf")
    print(f"Input: {PBF_FILE}")
    print(f"Size:  {PBF_FILE.stat().st_size / 1024 / 1024:.1f} MB")
    print("=" * 60)

    # --- Step 1: Parse .pbf file ---
    print("\n[1/3] Parsing .pbf file...")
    handler = RoadHandler()

    # Use NodeLocationsForWays to resolve node coordinates
    handler.apply_file(str(PBF_FILE), locations=True)

    print(f"  Total jalan ditemukan: {handler.count:,}")

    # --- Step 2: Build GeoDataFrame ---
    print("\n[2/3] Building GeoDataFrame...")

    geometries = []
    attributes = []

    for road in handler.roads:
        try:
            geom = LineString(road["geometry"])
            geometries.append(geom)
            attributes.append(
                {
                    "highway": road["highway"],
                    "name": road["name"],
                    "oneway": road["oneway"],
                    "maxspeed": road["maxspeed"],
                    "surface": road["surface"],
                    "lanes": road["lanes"],
                    "ref": road["ref"],
                    "osm_id": road["osm_id"],
                }
            )
        except Exception:
            continue

    gdf = gpd.GeoDataFrame(attributes, geometry=geometries, crs="EPSG:4326")

    # Klasifikasi status jalan
    gdf["klasifikasi_status"] = gdf["highway"].map(
        lambda x: KLASIFIKASI_STATUS.get(x, "Lainnya")
    )

    # Hitung panjang dalam meter (project to UTM zone 48S for Sumatra)
    gdf_projected = gdf.to_crs(epsg=32748)
    gdf["length_m"] = gdf_projected.geometry.length

    print(f"  Total segmen valid: {len(gdf):,}")
    print(f"  Total panjang: {gdf['length_m'].sum() / 1000:,.2f} km")

    # --- Step 3: Save output ---
    print("\n[3/3] Menyimpan output...")
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Ringkasan per klasifikasi
    print("\n  Ringkasan per klasifikasi:")
    summary = (
        gdf.groupby("klasifikasi_status")["length_m"]
        .agg(["count", "sum"])
        .rename(columns={"count": "segmen", "sum": "total_m"})
    )
    summary["total_km"] = summary["total_m"] / 1000
    for status, row in summary.iterrows():
        print(f"    {status:<22} {row['segmen']:>10,} segmen | {row['total_km']:>12,.2f} km")

    # Simpan file gabungan seluruh Sumatera (3 format)
    out_parquet = OUTPUT_DIR / "sumatera_road_network.parquet"
    out_geojson = OUTPUT_DIR / "sumatera_road_network.geojson"
    out_gpkg    = OUTPUT_DIR / "sumatera_road_network.gpkg"

    print(f"\n  Menyimpan parquet    : {out_parquet}")
    gdf.to_parquet(out_parquet)

    print(f"  Menyimpan GeoJSON    : {out_geojson}")
    gdf.to_file(out_geojson, driver="GeoJSON")

    print(f"  Menyimpan GeoPackage : {out_gpkg}")
    gdf.to_file(out_gpkg, driver="GPKG")

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"SELESAI dalam {elapsed:.1f} detik")
    print(f"  {len(gdf):,} segmen | {gdf['length_m'].sum() / 1000:,.2f} km")
    print(f"  Output: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
