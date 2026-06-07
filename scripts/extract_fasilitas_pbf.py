"""
Extract fasilitas infrastruktur from Sumatra .osm.pbf file.

Categories:
- Pemerintahan (government offices, police, townhall)
- Kesehatan (hospitals, clinics, pharmacies)
- Pendidikan (schools, universities, kindergartens)
- Ekonomi (Pasar, Indomaret, Alfamaret, Supermarket only)

Usage:
    python scripts/extract_fasilitas_pbf.py                        # auto-detect from data-input/
    python scripts/extract_fasilitas_pbf.py path/to/file.osm.pbf  # explicit path
"""

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import osmium
from shapely.geometry import Point

# ================================================================
# KONFIGURASI
# ================================================================
_ROOT = Path(__file__).parent.parent


def _parse_args() -> Path:
    parser = argparse.ArgumentParser(
        description="Extract fasilitas infrastruktur from a Sumatra .osm.pbf file."
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
OUTPUT_DIR = _ROOT / "sumatera_fasilitas"

# ================================================================
# KLASIFIKASI FASILITAS
# ================================================================

# Pemerintahan - OSM tags yang termasuk
PEMERINTAHAN_TAGS = {
    ("amenity", "police"),
    ("amenity", "townhall"),
    ("office", "government"),
    ("office", "administrative"),
    ("amenity", "courthouse"),
    ("amenity", "fire_station"),
    ("office", "military"),
}

# Kesehatan - OSM tags
KESEHATAN_TAGS = {
    ("amenity", "hospital"),
    ("amenity", "clinic"),
    ("amenity", "pharmacy"),
    ("amenity", "doctors"),
    ("amenity", "dentist"),
    ("amenity", "health_post"),
    ("amenity", "nursing_home"),
    ("healthcare", "hospital"),
    ("healthcare", "clinic"),
    ("healthcare", "pharmacy"),
    ("healthcare", "doctor"),
    ("healthcare", "centre"),
    ("healthcare", "laboratory"),
}

# Pendidikan - OSM tags
PENDIDIKAN_TAGS = {
    ("amenity", "school"),
    ("amenity", "university"),
    ("amenity", "college"),
    ("amenity", "kindergarten"),
    ("amenity", "library"),
    ("amenity", "language_school"),
    ("amenity", "training"),
}

# Ekonomi - hanya Pasar, Indomaret, Alfamaret, Supermarket
EKONOMI_AMENITY_TAGS = {
    ("amenity", "marketplace"),
}
EKONOMI_SHOP_TAGS = {
    ("shop", "supermarket"),
}
# Indomaret & Alfamaret - variasi penulisan nama
EKONOMI_NAME_KEYWORDS = [
    "indomaret", "indomart", "indo maret", "indo mart",
    "alfamaret", "alfamart", "alfa maret", "alfa mart",
]


# ================================================================
# HANDLER
# ================================================================
class FasilitasHandler(osmium.SimpleHandler):
    """Extract facility nodes and way-centroids from .pbf."""

    def __init__(self):
        super().__init__()
        self.facilities = []
        self.count = 0

    def _classify(self, tags):
        """Classify a tagged object into a category, return (kategori, sub_kategori) or None."""
        # Check Pemerintahan
        for key, val in PEMERINTAHAN_TAGS:
            if tags.get(key) == val:
                return ("Pemerintahan", val)

        # Check Kesehatan
        for key, val in KESEHATAN_TAGS:
            if tags.get(key) == val:
                return ("Kesehatan", val)

        # Check Pendidikan
        for key, val in PENDIDIKAN_TAGS:
            if tags.get(key) == val:
                return ("Pendidikan", val)

        # Check Ekonomi - marketplace
        for key, val in EKONOMI_AMENITY_TAGS:
            if tags.get(key) == val:
                return ("Ekonomi", "pasar")

        # Check Ekonomi - supermarket
        for key, val in EKONOMI_SHOP_TAGS:
            if tags.get(key) == val:
                name = tags.get("name", "").lower()
                # Exclude generic toko
                if "toko" in name and "supermarket" not in name:
                    return None
                return ("Ekonomi", "supermarket")

        # Check Ekonomi - Indomaret/Alfamaret by name
        name = tags.get("name", "").lower()
        if any(kw in name for kw in EKONOMI_NAME_KEYWORDS):
            return ("Ekonomi", "minimarket")

        return None

    def _add_facility(self, lon, lat, tags, osm_id, osm_type):
        result = self._classify(tags)
        if result is None:
            return

        kategori, sub_kategori = result
        self.facilities.append({
            "lon": lon,
            "lat": lat,
            "kategori": kategori,
            "sub_kategori": sub_kategori,
            "name": tags.get("name", ""),
            "osm_id": osm_id,
            "osm_type": osm_type,
            "amenity": tags.get("amenity", ""),
            "shop": tags.get("shop", ""),
            "office": tags.get("office", ""),
            "healthcare": tags.get("healthcare", ""),
            "operator": tags.get("operator", ""),
            "addr_street": tags.get("addr:street", ""),
            "addr_city": tags.get("addr:city", ""),
        })
        self.count += 1
        if self.count % 5000 == 0:
            print(f"  ... {self.count:,} fasilitas ditemukan")

    def node(self, n):
        if not n.tags:
            return
        try:
            self._add_facility(n.location.lon, n.location.lat, n.tags, n.id, "node")
        except osmium.InvalidLocationError:
            pass

    def way(self, w):
        if not w.tags:
            return
        # For ways (buildings), use centroid of nodes
        try:
            coords = [(n.lon, n.lat) for n in w.nodes]
            if len(coords) < 2:
                return
            # Simple centroid
            lon = sum(c[0] for c in coords) / len(coords)
            lat = sum(c[1] for c in coords) / len(coords)
            self._add_facility(lon, lat, w.tags, w.id, "way")
        except osmium.InvalidLocationError:
            pass


# ================================================================
# MAIN
# ================================================================
def main():
    start_time = time.time()

    print("=" * 60)
    print("EXTRACT FASILITAS INFRASTRUKTUR FROM .osm.pbf")
    print(f"Input: {PBF_FILE}")
    print(f"Size:  {PBF_FILE.stat().st_size / 1024 / 1024:.1f} MB")
    print("=" * 60)
    print("\nKategori yang diekstrak:")
    print("  - Pemerintahan (kantor pemerintah, polisi, dll)")
    print("  - Kesehatan (RS, klinik, apotek, dll)")
    print("  - Pendidikan (sekolah, universitas, TK, dll)")
    print("  - Ekonomi (Pasar, Indomaret, Alfamaret, Supermarket)")

    # --- Parse .pbf ---
    print(f"\n[1/2] Parsing {PBF_FILE.name}...")
    handler = FasilitasHandler()
    handler.apply_file(str(PBF_FILE), locations=True)
    print(f"  Total fasilitas ditemukan: {handler.count:,}")

    if handler.count == 0:
        print("  Tidak ada fasilitas ditemukan!")
        return

    # --- Build GeoDataFrame ---
    print("\n[2/2] Building GeoDataFrame & menyimpan...")

    geometries = [Point(f["lon"], f["lat"]) for f in handler.facilities]
    attrs = [{k: v for k, v in f.items() if k not in ("lon", "lat")}
             for f in handler.facilities]

    gdf = gpd.GeoDataFrame(attrs, geometry=geometries, crs="EPSG:4326")

    # --- Setup output dirs ---
    combined_dir = OUTPUT_DIR / "combined"
    per_cat_dir  = OUTPUT_DIR / "per-category"
    combined_dir.mkdir(parents=True, exist_ok=True)
    per_cat_dir.mkdir(parents=True, exist_ok=True)

    print("\n  Ringkasan per kategori:")
    for kategori in ["Pemerintahan", "Kesehatan", "Pendidikan", "Ekonomi"]:
        subset = gdf[gdf["kategori"] == kategori]
        print(f"\n    {kategori} ({len(subset):,} total):")
        sub_counts = subset["sub_kategori"].value_counts()
        for sub, cnt in sub_counts.items():
            print(f"      {sub:<20} {cnt:>6,}")

    # --- Save combined (3 format) ---
    base = "sumatera_fasilitas_infrastruktur"
    print(f"\n  [combined]")
    gdf.to_parquet(combined_dir / f"{base}.parquet")
    print(f"    Parquet    : {combined_dir / f'{base}.parquet'}")
    gdf.to_file(combined_dir / f"{base}.geojson", driver="GeoJSON")
    print(f"    GeoJSON    : {combined_dir / f'{base}.geojson'}")
    gdf.to_file(combined_dir / f"{base}.gpkg", driver="GPKG")
    print(f"    GeoPackage : {combined_dir / f'{base}.gpkg'}")

    # --- Save per kategori (3 format) ---
    for kategori in ["Pemerintahan", "Kesehatan", "Pendidikan", "Ekonomi"]:
        subset = gdf[gdf["kategori"] == kategori]
        if subset.empty:
            continue
        fname = f"sumatera_{kategori.lower()}"
        print(f"\n  [{kategori}] {len(subset):,} fasilitas")
        subset.to_parquet(per_cat_dir / f"{fname}.parquet")
        print(f"    Parquet    : {per_cat_dir / f'{fname}.parquet'}")
        subset.to_file(per_cat_dir / f"{fname}.geojson", driver="GeoJSON")
        print(f"    GeoJSON    : {per_cat_dir / f'{fname}.geojson'}")
        subset.to_file(per_cat_dir / f"{fname}.gpkg", driver="GPKG")
        print(f"    GeoPackage : {per_cat_dir / f'{fname}.gpkg'}")

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"SELESAI dalam {elapsed:.1f} detik")
    print(f"  Total: {len(gdf):,} fasilitas")
    print(f"  Output: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
