# Scrapping Sumatera

Data jaringan jalan dan fasilitas infrastruktur Pulau Sumatera dari OpenStreetMap (OSM).

---

## Struktur Proyek

```
scrapping-sumatera/
├── data-input/                  # File input (CSV & PBF)
│   ├── wilayah_sumatera.csv     # Daftar kota/kabupaten per provinsi
│   └── *.osm.pbf                # File PBF dari Geofabrik (di-gitignore)
├── scripts/
│   ├── scrapping_road_network.py   # Download via osmnx (metode utama)
│   ├── extract_road_network_pbf.py # Ekstrak dari PBF (fallback)
│   ├── extract_fasilitas_pbf.py    # Ekstrak fasilitas dari PBF
│   ├── visualize_road_network.py   # Visualisasi jaringan jalan
│   └── visualize_fasilitas.py     # Visualisasi fasilitas
├── sumatera_jaringan_jalan/     # Output jaringan jalan (di-gitignore)
├── sumatera_fasilitas/          # Output fasilitas (di-gitignore)
│   ├── combined/
│   └── per-category/
└── visualizations/              # Output peta PNG (di-gitignore)
```

---

## Instalasi

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Penggunaan Scripts

### 1. Scrapping Jaringan Jalan (Metode Utama)

Menggunakan **osmnx** untuk mengunduh jaringan jalan langsung dari Overpass API,
per kota/kabupaten berdasarkan `data-input/wilayah_sumatera.csv`.

```bash
python scripts/scrapping_road_network.py
```

> **Catatan:** Script ini membutuhkan koneksi internet yang stabil. Ada delay antar
> request (30 detik) untuk menghindari rate-limit Overpass API.

---

### 2. Extract dari PBF (Fallback — Error 104 / Connection Reset)

Jika `scrapping_road_network.py` mengalami error **Connection Reset by Peer (104)**
atau timeout berulang dari Overpass API, gunakan metode ini sebagai alternatif.

Metode ini membaca langsung dari file `.osm.pbf` lokal sehingga tidak memerlukan
koneksi internet saat ekstraksi.

#### Langkah 1 — Download file PBF

Unduh file PBF Sumatera dari Geofabrik:

**[https://download.geofabrik.de/asia/indonesia/sumatra.html](https://download.geofabrik.de/asia/indonesia/sumatra.html)**

Pilih file **`sumatra-latest.osm.pbf`** lalu letakkan di folder `data-input/`:

```
data-input/
└── sumatra-latest.osm.pbf
```

#### Langkah 2 — Jalankan extract

**Jaringan Jalan:**
```bash
# Auto-detect file PBF terbaru di data-input/
python scripts/extract_road_network_pbf.py

# Atau tentukan path secara eksplisit
python scripts/extract_road_network_pbf.py data-input/sumatra-latest.osm.pbf
```

Output disimpan ke `sumatera_jaringan_jalan/`:
```
sumatera_jaringan_jalan/
├── sumatera_road_network.parquet
├── sumatera_road_network.geojson
└── sumatera_road_network.gpkg
```

**Fasilitas Infrastruktur:**
```bash
# Auto-detect file PBF terbaru di data-input/
python scripts/extract_fasilitas_pbf.py

# Atau tentukan path secara eksplisit
python scripts/extract_fasilitas_pbf.py data-input/sumatra-latest.osm.pbf
```

Kategori yang diekstrak: Pemerintahan, Kesehatan, Pendidikan, Ekonomi.

Output disimpan ke `sumatera_fasilitas/`:
```
sumatera_fasilitas/
├── combined/
│   ├── sumatera_fasilitas_infrastruktur.parquet
│   ├── sumatera_fasilitas_infrastruktur.geojson
│   └── sumatera_fasilitas_infrastruktur.gpkg
└── per-category/
    ├── sumatera_pemerintahan.parquet / .geojson / .gpkg
    ├── sumatera_kesehatan.parquet   / .geojson / .gpkg
    ├── sumatera_pendidikan.parquet  / .geojson / .gpkg
    └── sumatera_ekonomi.parquet    / .geojson / .gpkg
```

---

### 3. Visualisasi

Setelah data tersedia (dari scrapping maupun extract), jalankan script visualisasi
untuk menghasilkan peta PNG di `visualizations/`.

```bash
# Peta jaringan jalan
python scripts/visualize_road_network.py

# Peta fasilitas infrastruktur
python scripts/visualize_fasilitas.py
```

---

## Kapan Gunakan Script Mana?

| Situasi | Script yang digunakan |
|---|---|
| Koneksi internet stabil | `scrapping_road_network.py` |
| Error 104 / connection reset berulang | `extract_road_network_pbf.py` |
| Butuh data fasilitas (RS, sekolah, dll) | `extract_fasilitas_pbf.py` |
| Visualisasi dari data yang sudah ada | `visualize_*.py` |
