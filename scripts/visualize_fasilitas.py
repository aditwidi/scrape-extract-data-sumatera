"""
Visualize fasilitas infrastruktur Sumatera from extracted GeoPackage.
Colors points by category (Pemerintahan, Kesehatan, Pendidikan, Ekonomi).
"""

import time
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# ================================================================
# KONFIGURASI
# ================================================================
_ROOT = Path(__file__).parent.parent
GPKG_FILE = _ROOT / "sumatera_fasilitas_pbf" / "sumatera_fasilitas_infrastruktur.parquet"
OUTPUT_PNG = _ROOT / "visualizations" / "sumatera_fasilitas_map.png"

# Warna dan style per kategori
STYLE = {
    "Pemerintahan": {"color": "#e41a1c", "marker": "s", "size": 8, "zorder": 5},
    "Kesehatan": {"color": "#4daf4a", "marker": "+", "size": 10, "zorder": 4},
    "Pendidikan": {"color": "#377eb8", "marker": "^", "size": 6, "zorder": 3},
    "Ekonomi": {"color": "#ff7f00", "marker": "o", "size": 6, "zorder": 6},
}


def main():
    start = time.time()

    # --- Load data ---
    print(f"Loading {GPKG_FILE}...")
    gdf = gpd.read_parquet(GPKG_FILE)
    print(f"  {len(gdf):,} fasilitas loaded in {time.time() - start:.1f}s")

    # --- Setup figure ---
    fig, ax = plt.subplots(1, 1, figsize=(16, 20), dpi=150)
    ax.set_facecolor("#1a1a2e")
    fig.set_facecolor("#1a1a2e")

    # --- Plot each category ---
    for kategori, style in STYLE.items():
        subset = gdf[gdf["kategori"] == kategori]
        if subset.empty:
            continue
        print(f"  Plotting {kategori}: {len(subset):,} titik...")
        ax.scatter(
            subset.geometry.x,
            subset.geometry.y,
            c=str(style["color"]),
            marker=str(style["marker"]),
            s=float(style["size"]),
            alpha=0.7,
            zorder=int(style["zorder"]),
            linewidths=0.3,
            edgecolors="none",
        )

    # --- Legend ---
    legend_elements = [
        Line2D([0], [0], marker=str(s["marker"]), color="w",
               markerfacecolor=str(s["color"]), markersize=8,
               linestyle="None",
               label=f"{k} ({len(gdf[gdf['kategori'] == k]):,})")
        for k, s in STYLE.items()
        if len(gdf[gdf["kategori"] == k]) > 0
    ]
    ax.legend(
        handles=legend_elements,
        loc="lower left",
        fontsize=10,
        framealpha=0.8,
        facecolor="#2d2d44",
        edgecolor="#555",
        labelcolor="white",
    )

    # --- Title & labels ---
    ax.set_title(
        "Fasilitas Infrastruktur Pulau Sumatera\n"
        "(Pemerintahan, Kesehatan, Pendidikan, Ekonomi)",
        fontsize=16,
        fontweight="bold",
        color="white",
        pad=15,
    )

    ax.text(
        0.99, 0.01,
        f"Total: {len(gdf):,} fasilitas (OSM Extract)",
        transform=ax.transAxes,
        ha="right", va="bottom",
        fontsize=9, color="#cccccc",
        style="italic",
    )

    ax.set_axis_off()
    plt.tight_layout(pad=1)

    # --- Save ---
    OUTPUT_PNG.parent.mkdir(exist_ok=True)
    print(f"\nSaving {OUTPUT_PNG}...")
    plt.savefig(OUTPUT_PNG, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()

    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s → {OUTPUT_PNG}")


if __name__ == "__main__":
    main()
