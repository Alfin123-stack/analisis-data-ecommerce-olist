# Proyek Analisis Data: E-Commerce Public Dataset

Analisis data pesanan toko online Olist (Januari 2017 - Agustus 2018) dan dashboard sederhana pakai Streamlit.

## Isi Folder

```
submission
├───dashboard
│   ├───main_data.csv
│   └───dashboard.py
├───data
│   ├───olist_customers_dataset.csv
│   ├───olist_geolocation_dataset.csv
│   ├───olist_order_items_dataset.csv
│   ├───olist_orders_dataset.csv
│   ├───olist_products_dataset.csv
│   └───product_category_name_translation.csv
├───notebook.ipynb
├───README.md
├───requirements.txt
└───url.txt                (link dashboard, kalau sudah deploy)
```

## Setup Environment

Jalankan dari folder `submission`:

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

## Menjalankan Dashboard

```
streamlit run dashboard/dashboard.py
```

Dashboard terbuka di `http://localhost:8501`.

## Notebook

Buka `notebook.ipynb` dari folder `submission`, karena path datanya relatif (`data/...`). Di Google Colab, upload folder `data` dan buat folder kosong `dashboard` dulu. Menjalankan notebook akan membuat ulang `dashboard/main_data.csv`.
