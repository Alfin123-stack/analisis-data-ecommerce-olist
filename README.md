# Proyek Analisis Data: E-Commerce Public Dataset

Analisis data pesanan toko online Olist (Januari 2017 - Agustus 2018) dan dashboard sederhana pakai Streamlit.

Dashboard online: https://kqbqmmopa3ldu2mau8nzzc.streamlit.app/

## Isi Folder

```
submission
├───dashboard
│   ├───main_data.csv
│   └───dashboard.py
├───data
│   ├───customers_dataset.csv
│   ├───geolocation_dataset.csv
│   ├───order_items_dataset.csv
│   ├───orders_dataset.csv
│   ├───products_dataset.csv
│   └───product_category_name_translation.csv
├───notebook.ipynb
├───README.md
├───requirements.txt
└───url.txt                (link dashboard di Streamlit Cloud)
```

## Setup Environment

Pilih salah satu cara. Semua perintah dijalankan dari folder `submission`.

### Cara 1: venv (bawaan Python)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Di macOS atau Linux, aktivasinya pakai `source venv/bin/activate`.

Kalau di PowerShell muncul error "running scripts is disabled", jalankan ini dulu, lalu ulangi aktivasinya:

```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Cara 2: Anaconda

```
conda create --name main-ds python=3.12
conda activate main-ds
pip install -r requirements.txt
```

### Cara 3: Shell/Terminal (pipenv)

```
pip install pipenv
pipenv install
pipenv shell
pip install -r requirements.txt
```

`pipenv install` membaca `requirements.txt` secara otomatis, jadi perintah `pip install` terakhir hanya memastikan semua library terpasang.

## Menjalankan Dashboard

Dari folder `submission`:

```
streamlit run dashboard/dashboard.py
```

Atau dari dalam folder `dashboard`:

```
cd dashboard
streamlit run dashboard.py
```

Dashboard terbuka di `http://localhost:8501`.

Peta interaktif di dashboard memakai folium dan peta dasar CARTO, jadi butuh koneksi internet dan API key CARTO (gratis).

### API key peta (CARTO)

1. Minta key di https://carto.com/basemaps/apikey/ (gratis, tanpa akun).
2. Jangan menulis key di kode, README, atau `url.txt`.
3. Isi key dengan nama `CARTO_KEY`:
   - **Lokal:** buat file `.streamlit/secrets.toml` berisi `CARTO_KEY = "isi-key-kamu"`, atau set environment variable `CARTO_KEY`. Jangan ikutkan `secrets.toml` ke GitHub atau ZIP, dan tambahkan `.streamlit/secrets.toml` ke `.gitignore` supaya tidak ikut ter-push.
   - **Streamlit Cloud:** buka pengaturan app, lalu menu Secrets, dan isi `CARTO_KEY = "isi-key-kamu"`.
   - **Colab (notebook):** buka panel Secrets di sebelah kiri, tambah secret bernama `CARTO_KEY`, dan aktifkan akses notebook.
4. Kalau key tidak diisi, peta tetap tampil tanpa peta dasar (hanya lingkaran dan legenda).

## Notebook

Buka `notebook.ipynb` dari folder `submission`, karena path datanya relatif (`data/...`). Di Google Colab, upload folder `data` dan buat folder kosong `dashboard` dulu. Menjalankan notebook akan membuat ulang `dashboard/main_data.csv`.

Peta interaktif (folium) di notebook juga butuh koneksi internet dan `CARTO_KEY` (lihat bagian API key di atas). Kalau output peta tidak tampil, lihat peta hexbin statis di bagian Geospatial Analysis.
