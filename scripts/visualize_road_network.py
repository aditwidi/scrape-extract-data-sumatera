"""
Visualize Sumatra road network from extracted GeoPackage.
Colors roads by classification (klasifikasi_status).
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
GPKG_FILE = _ROOT / "sumatera_jaringan_jalan" / "sumatera_road_network.parquet"
OUTPUT_PNG = _ROOT / "visualizations" / "sumatera_road_network_map.png"

# Warna dan ketebalan per klasifikasi (urut dari paling penting)
STYLE = {
    "Jalan Nasional": {"color": "#e41a1c", "linewidth": 0.8, "zorder": 6},
    "Jalan Provinsi": {"color": "#ff7f00", "linewidth": 0.5, "zorder": 5},
    "Jalan Kabupaten": {"color": "#4daf4a", "linewidth": 0.3, "zorder": 4},
    "Jalan Kota": {"color": "#377eb8", "linewidth": 0.15, "zorder": 3},
    "Jalan Desa": {"color": "#984ea3", "linewidth": 0.1, "zorder": 2},
    "Jalan Pejalan Kaki": {"color": "#a65628", "linewidth": 0.08, "zorder": 1},
    "Lainnya": {"color": "#999999", "linewidth": 0.05, "zorder": 0},
}


def main():
    start = time.time()

    # --- Load data ---
    print(f"Loading {GPKG_FILE}...")
    gdf = gpd.read_parquet(GPKG_FILE)
    print(f"  {len(gdf):,} segmen loaded in {time.time() - start:.1f}s")

    # --- Setup figure ---
    fig, ax = plt.subplots(1, 1, figsize=(16, 20), dpi=150)
    ax.set_facecolor("#1a1a2e")
    fig.set_facecolor("#1a1a2e")

    # --- Plot each classification layer (background first, important last) ---
    for klasifikasi in reversed(list(STYLE.keys())):
        style = STYLE[klasifikasi]
        subset = gdf[gdf["klasifikasi_status"] == klasifikasi]
        if subset.empty:
            continue
        print(f"  Plotting {klasifikasi}: {len(subset):,} segmen...")
        subset.plot(
            ax=ax,
            color=style["color"],
            linewidth=style["linewidth"],
            zorder=style["zorder"],
        )

    # --- Legend ---
    legend_elements = [
        Line2D([0], [0], color=str(s["color"]),
               linewidth=max(float(s["linewidth"]) * 3, 1.5),
               label=f"{k} ({len(gdf[gdf['klasifikasi_status']==k]):,})")
        for k, s in STYLE.items()
        if len(gdf[gdf["klasifikasi_status"] == k]) > 0
    ]
    ax.legend(
        handles=legend_elements,
        loc="lower left",
        fontsize=9,
        framealpha=0.8,
        facecolor="#2d2d44",
        edgecolor="#555",
        labelcolor="white",
    )

    # --- Labels & formatting ---
    ax.set_title(
        "Jaringan Jalan Pulau Sumatera",
        fontsize=16,
        fontweight="bold",
        color="white",
        pad=15,
    )

    total_km = gdf["length_m"].sum() / 1000
    ax.text(
        0.99, 0.01,
        f"Total: {len(gdf):,} segmen | {total_km:,.0f} km",
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
    plt.savefig(OUTPUT_PNG, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()

    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s → {OUTPUT_PNG}")


if __name__ == "__main__":
    main()
