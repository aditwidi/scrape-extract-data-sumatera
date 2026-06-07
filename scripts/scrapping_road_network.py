import time
from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd
from tqdm import tqdm

# ================================================================
# KONFIGURASI
# ================================================================
_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = "sumatera_jaringan_jalan"  # folder utama
NETWORK_TYPE = "all"
DELAY_BETWEEN_REQUESTS = 30  # detik antar request untuk hindari rate-limit
MAX_RETRIES = 3

# Konfigurasi osmnx agar lebih tahan timeout
ox.settings.overpass_rate_limit = True
ox.settings.max_query_area_size = 10_000_000_000
ox.settings.use_cache = True
ox.settings.http_user_agent = "SumateraRoadNetwork/1.0 (academic research project)"

# 10 Provinsi di Pulau Sumatera
PROVINSI_SUMATERA = [
    "Aceh, Indonesia",
    "Sumatera Utara, Indonesia",
    "Sumatera Barat, Indonesia",
    "Riau, Indonesia",
    "Kepulauan Riau, Indonesia",
    "Jambi, Indonesia",
    "Bengkulu, Indonesia",
    "Sumatera Selatan, Indonesia",
    "Kepulauan Bangka Belitung, Indonesia",
    "Lampung, Indonesia",
]

# Load daftar kota/kabupaten dari CSV
WILAYAH_PER_PROVINSI: dict[str, list[tuple[str, str]]] = {}
with open(_ROOT / "data-input" / "wilayah_sumatera.csv") as f:
    next(f)  # skip header
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",", 2)
        prov, jenis, nama = parts[0], parts[1], parts[2]
        if prov not in WILAYAH_PER_PROVINSI:
            WILAYAH_PER_PROVINSI[prov] = []
        WILAYAH_PER_PROVINSI[prov].append((jenis, nama))

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
# FUNGSI UTILITAS
# ================================================================
def normalize_highway(val):
    if isinstance(val, list):
        return val[0]
    return str(val)


def safe_folder_name(name):
    """Bersihkan nama untuk dijadikan nama folder"""
    return name.replace(", Indonesia", "").replace("/", "_").replace(" ", "_").lower()


def proses_kota(nama_kota, folder_kota):
    """Download dan simpan jaringan jalan 1 kota/kabupaten dengan retry"""
    # Buat variasi query jika nama asli gagal di Nominatim
    queries = [nama_kota]
    for prefix in ("Kabupaten ", "Kota "):
        if nama_kota.startswith(prefix):
            stripped = nama_kota.replace(prefix, "", 1)
            queries.append(stripped)
            break

    for query in queries:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                tqdm.write(f"    Downloading: {query} ...")
                G = ox.graph_from_place(query, network_type=NETWORK_TYPE)
                _, gdf_edges = ox.graph_to_gdfs(G)

                # Normalisasi & klasifikasi
                gdf_edges["highway_clean"] = gdf_edges["highway"].apply(
                    normalize_highway
                )
                gdf_edges["klasifikasi_status"] = gdf_edges["highway_clean"].apply(
                    lambda x: KLASIFIKASI_STATUS.get(x, "Lainnya")
                )

                # Pilih kolom relevan
                cols_want = [
                    "geometry",
                    "highway_clean",
                    "klasifikasi_status",
                    "length",
                    "name",
                    "oneway",
                    "maxspeed",
                ]
                cols_exist = [c for c in cols_want if c in gdf_edges.columns]
                gdf_export = gdf_edges[cols_exist].copy().to_crs(epsg=4326)

                # Simpan GeoJSON per kota
                out_path = folder_kota / f"{folder_kota.name}_jaringan_jalan.geojson"
                gdf_export.to_file(out_path, driver="GeoJSON")

                n_seg = len(gdf_export)
                km = round(gdf_export["length"].sum() / 1000, 2)
                tqdm.write(
                    f"    Selesai: {n_seg:,} segmen | {km:.2f} km → {out_path}"
                )
                return gdf_export

            except Exception as e:
                is_nominatim = "Nominatim" in str(e)
                if is_nominatim:
                    tqdm.write(f"    Nama tidak ditemukan: {query}")
                    break  # coba query variant berikutnya
                if attempt < MAX_RETRIES:
                    wait = 30 * attempt
                    tqdm.write(f"    RETRY {attempt}/{MAX_RETRIES}: {query} — {e}")
                    tqdm.write(f"    Menunggu {wait}s sebelum retry...")
                    time.sleep(wait)
                else:
                    tqdm.write(f"    GAGAL: {query} — {e}")
                    return None

    tqdm.write(f"    GAGAL (semua variasi nama): {nama_kota}")
    return None


# ================================================================
# MAIN — Download per provinsi, subfolder per kota
# ================================================================
Path(OUTPUT_DIR).mkdir(exist_ok=True)

all_gdfs = []  # untuk gabungkan jadi 1 file Sumatera

for provinsi in tqdm(PROVINSI_SUMATERA, desc="Sumatera", unit="provinsi", ncols=100):
    nama_prov = provinsi.replace(", Indonesia", "")
    tqdm.write("\n" + "=" * 55)
    tqdm.write(f"PROVINSI: {nama_prov}")
    tqdm.write("=" * 55)

    # Buat folder provinsi
    folder_prov = Path(OUTPUT_DIR) / safe_folder_name(provinsi)
    folder_prov.mkdir(exist_ok=True)

    try:
        # Ambil daftar kota/kabupaten dari CSV
        kota_list = WILAYAH_PER_PROVINSI.get(nama_prov, [])
        if not kota_list:
            tqdm.write(f"  SKIP: {nama_prov} tidak ditemukan di CSV")
            continue
        tqdm.write(f"  {len(kota_list)} kota/kabupaten dari CSV")

        # Proses setiap kota
        for jenis, nama in tqdm(kota_list, desc=nama_prov, unit="kota", leave=False, ncols=100):
            query_kota = f"{jenis} {nama}, {nama_prov}, Indonesia"
            folder_kota = folder_prov / safe_folder_name(nama)
            folder_kota.mkdir(exist_ok=True)

            # Skip jika sudah pernah didownload
            out_file = folder_kota / f"{folder_kota.name}_jaringan_jalan.geojson"
            if out_file.exists() and out_file.stat().st_size > 0:
                tqdm.write(f"    SKIP (sudah ada): {nama}")
                continue

            gdf_kota = proses_kota(query_kota, folder_kota)
            if gdf_kota is not None:
                gdf_kota["provinsi"] = nama_prov
                gdf_kota["kota"] = nama
                all_gdfs.append(gdf_kota)

            # Delay antar request untuk hindari rate-limit
            time.sleep(DELAY_BETWEEN_REQUESTS)

    except Exception as e:
        tqdm.write(f"  ERROR provinsi {nama_prov}: {e}")
        continue

# ================================================================
# GABUNGKAN SEMUA → 1 FILE SUMATERA
# ================================================================
if all_gdfs:
    print("\n" + "=" * 55)
    print("Menggabungkan semua data menjadi 1 file Sumatera...")
    gdf_sumatera = pd.concat(all_gdfs, ignore_index=True)
    gdf_sumatera = gpd.GeoDataFrame(gdf_sumatera, geometry="geometry", crs="EPSG:4326")

    sumatera_path = Path(OUTPUT_DIR) / "sumatera_jaringan_jalan_lengkap.geojson"
    gdf_sumatera.to_file(sumatera_path, driver="GeoJSON")

    total_km = round(gdf_sumatera["length"].sum() / 1000, 2)
    total_seg = len(gdf_sumatera)
    print(f"Tersimpan: {sumatera_path}")
    print(f"Total: {total_seg:,} segmen | {total_km:,.2f} km")
