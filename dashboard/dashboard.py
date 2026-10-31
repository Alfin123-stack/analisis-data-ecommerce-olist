from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st
from matplotlib.colors import LogNorm

sns.set_theme(style='whitegrid')
st.set_page_config(page_title='Dashboard E-Commerce', layout='wide')


@st.cache_data
def load_data():
    path = Path(__file__).parent / 'main_data.csv'
    df = pd.read_csv(path, parse_dates=['order_purchase_timestamp'])
    return df


def hitung_rfm(df):
    tanggal_acuan = df['order_purchase_timestamp'].max() + pd.Timedelta(days=1)
    rfm = df.groupby('customer_unique_id').agg(
        terakhir_beli=('order_purchase_timestamp', 'max'),
        frequency=('order_id', 'nunique'),
        monetary=('price', 'sum'),
    ).reset_index()
    rfm['recency'] = (tanggal_acuan - rfm['terakhir_beli']).dt.days
    # rank(method='first') dipakai supaya qcut tidak error saat data sedikit
    rfm['r_score'] = pd.qcut(rfm['recency'].rank(method='first'), 4, labels=[4, 3, 2, 1]).astype(int)
    rfm['m_score'] = pd.qcut(rfm['monetary'].rank(method='first'), 4, labels=[1, 2, 3, 4]).astype(int)

    kondisi = [
        (rfm['frequency'] >= 2) & (rfm['r_score'] >= 3),
        (rfm['frequency'] >= 2) & (rfm['r_score'] < 3),
        (rfm['r_score'] >= 3) & (rfm['m_score'] >= 3),
        (rfm['r_score'] >= 3) & (rfm['m_score'] < 3),
        (rfm['m_score'] >= 3),
    ]
    nama = ['Setia Aktif', 'Setia Pasif', 'Aktif Belanja Besar', 'Aktif Belanja Kecil', 'Pasif Belanja Besar']
    rfm['segmen'] = np.select(kondisi, nama, default='Pasif Belanja Kecil')

    segmen = rfm.groupby('segmen').agg(
        jumlah_customer=('customer_unique_id', 'count'),
        total_revenue=('monetary', 'sum'),
    )
    # semua segmen selalu ditampilkan, yang kosong diisi 0
    segmen = segmen.reindex(nama + ['Pasif Belanja Kecil'], fill_value=0).rename_axis('segmen').reset_index()
    segmen['persen_customer'] = segmen['jumlah_customer'] / segmen['jumlah_customer'].sum() * 100
    segmen['persen_revenue'] = segmen['total_revenue'] / segmen['total_revenue'].sum() * 100
    return segmen.sort_values('jumlah_customer')


def pilih_satuan(nilai):
    # pilih satuan sumbu supaya angka tidak terlalu kecil (misalnya 0.0004 juta)
    if nilai >= 1e6:
        return 1e6, 'juta R$'
    if nilai >= 1e3:
        return 1e3, 'ribu R$'
    return 1, 'R$'


main_df = load_data()

# sidebar
st.sidebar.header('Filter')
tgl_min = main_df['order_purchase_timestamp'].min().date()
tgl_max = main_df['order_purchase_timestamp'].max().date()
rentang = st.sidebar.date_input('Rentang tanggal pesanan', value=(tgl_min, tgl_max),
                                min_value=tgl_min, max_value=tgl_max)
if len(rentang) != 2:
    st.info('Pilih tanggal awal dan tanggal akhir.')
    st.stop()

mulai, selesai = pd.to_datetime(rentang[0]), pd.to_datetime(rentang[1]) + pd.Timedelta(days=1)
df = main_df[(main_df['order_purchase_timestamp'] >= mulai) & (main_df['order_purchase_timestamp'] < selesai)]
if df.empty:
    st.warning('Tidak ada data di rentang tanggal ini.')
    st.stop()

# judul dan ringkasan
st.title('Dashboard E-Commerce Public Dataset')
st.caption('Data pesanan yang sudah terkirim (delivered), Januari 2017 - Agustus 2018. Revenue dihitung dari harga produk saja, tanpa ongkir, dalam R$.')

kol1, kol2, kol3 = st.columns(3)
kol1.metric('Total pesanan', f"{df['order_id'].nunique():,}")
kol2.metric('Total revenue', f"R$ {df['price'].sum():,.0f}")
kol3.metric('Jumlah customer', f"{df['customer_unique_id'].nunique():,}")

# tren pesanan dan revenue
# rentang pendek (<= 62 hari) ditampilkan per hari, rentang panjang per bulan
harian = (selesai - mulai).days <= 62
if harian:
    st.subheader('Tren pesanan dan revenue per hari')
    waktu = df['order_purchase_timestamp'].dt.normalize()
    satuan_waktu = 'hari'
else:
    st.subheader('Tren pesanan dan revenue per bulan')
    waktu = df['order_purchase_timestamp'].dt.to_period('M')
    satuan_waktu = 'bulan'

tren = df.groupby(waktu).agg(jumlah_order=('order_id', 'nunique'), revenue=('price', 'sum')).reset_index()
tren.columns = ['waktu', 'jumlah_order', 'revenue']
sumbu_x = tren['waktu'] if harian else tren['waktu'].astype(str)
pembagi_rev, label_rev = pilih_satuan(tren['revenue'].max())

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
axes[0].plot(sumbu_x, tren['jumlah_order'], marker='o', color='#1f77b4')
axes[0].set_title(f'Jumlah pesanan per {satuan_waktu}')
axes[0].set_ylabel('Jumlah pesanan')
axes[0].yaxis.set_major_locator(MaxNLocator(integer=True, steps=[1, 2, 5, 10]))
axes[1].plot(sumbu_x, tren['revenue'] / pembagi_rev, marker='o', color='#2ca02c')
axes[1].set_title(f'Revenue per {satuan_waktu}')
axes[1].set_ylabel(f'Revenue ({label_rev})')
for ax in axes:
    ax.set_ylim(bottom=0)
    if harian:
        if len(tren) <= 10:
            ax.set_xticks(list(tren['waktu']))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b %Y'))
    ax.tick_params(axis='x', rotation=60)
plt.tight_layout()
st.pyplot(fig)
plt.close(fig)

if not harian:
    awal_sebagian = mulai.date() > tgl_min and mulai.day != 1
    akhir_sebagian = (selesai - pd.Timedelta(days=1)).date() < tgl_max and selesai.day != 1
    if awal_sebagian or akhir_sebagian:
        st.caption('Catatan: bulan pertama atau terakhir tidak penuh sebulan, jadi angkanya bisa terlihat lebih rendah.')

puncak = tren.loc[tren['jumlah_order'].idxmax()]
nama_puncak = puncak['waktu'].strftime('%Y-%m-%d') if harian else str(puncak['waktu'])
st.write(f"{satuan_waktu.capitalize()} dengan pesanan terbanyak: **{nama_puncak}** ({int(puncak['jumlah_order']):,} pesanan).")

# kategori produk
st.subheader('Kategori produk dengan revenue tertinggi dan terendah')
total_revenue = df['price'].sum()
kategori = (df[df['category'] != 'Unknown'].groupby('category')['price'].sum()
            .sort_values(ascending=False).reset_index(name='revenue'))
kategori['persen'] = kategori['revenue'] / total_revenue * 100
if len(kategori) < 10:
    st.info(f'Rentang ini hanya punya {len(kategori)} kategori, jadi grafik teratas dan terendah bisa berisi kategori yang sama.')
top5 = kategori.head(5).sort_values('revenue')
bottom5 = kategori.tail(5).sort_values('revenue')

pembagi_atas, label_atas = pilih_satuan(top5['revenue'].max())
pembagi_bawah, label_bawah = pilih_satuan(bottom5['revenue'].max())

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
axes[0].barh(top5['category'], top5['revenue'] / pembagi_atas, color=['#9ecae1'] * 4 + ['#08519c'])
axes[0].set_title('5 kategori revenue tertinggi')
axes[0].set_xlabel(f'Revenue ({label_atas})')
for i, (rev, pct) in enumerate(zip(top5['revenue'], top5['persen'])):
    axes[0].text(rev / pembagi_atas, i, f'  {pct:.1f}%', va='center')
axes[0].set_xlim(0, top5['revenue'].max() / pembagi_atas * 1.2)
axes[1].barh(bottom5['category'], bottom5['revenue'] / pembagi_bawah, color=['#a50f15'] + ['#fcae91'] * 4)
axes[1].set_title('5 kategori revenue terendah')
axes[1].set_xlabel(f'Revenue ({label_bawah})')
for i, (rev, pct) in enumerate(zip(bottom5['revenue'], bottom5['persen'])):
    axes[1].text(rev / pembagi_bawah, i, f'  {pct:.3f}%', va='center')
axes[1].set_xlim(0, bottom5['revenue'].max() / pembagi_bawah * 1.4)
for ax in axes:
    ax.set_ylabel('')
plt.tight_layout()
st.pyplot(fig)
plt.close(fig)
st.caption('Angka di ujung batang adalah persen dari total revenue di rentang yang dipilih. Satuan sumbu kiri dan kanan bisa beda, jadi panjang batangnya tidak bisa dibandingkan langsung. Produk tanpa kategori tidak ikut diperingkat.')

# segmentasi RFM
st.subheader('Segmentasi customer (RFM)')
if df['customer_unique_id'].nunique() >= 4:
    segmen = hitung_rfm(df)
    fig, axes = plt.subplots(1, 2, figsize=(14, 4), sharey=True)
    axes[0].barh(segmen['segmen'], segmen['persen_customer'], color='#1f77b4')
    axes[0].set_title('Persentase customer')
    axes[0].set_xlabel('% dari total customer')
    axes[1].barh(segmen['segmen'], segmen['persen_revenue'], color='#2ca02c')
    axes[1].set_title('Persentase revenue')
    axes[1].set_xlabel('% dari total revenue')
    for ax, kolom in zip(axes, ['persen_customer', 'persen_revenue']):
        for i, nilai in enumerate(segmen[kolom]):
            ax.text(nilai, i, f' {nilai:.1f}%', va='center')
        ax.set_xlim(0, segmen[kolom].max() * 1.2)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)
    st.caption('Aktif = belanja terakhir masuk 50% terbaru. Belanja Besar = total belanja masuk 50% teratas. Setia = belanja 2 kali atau lebih. RFM hanya dihitung dari rentang tanggal yang dipilih.')
else:
    st.info('Data terlalu sedikit untuk segmentasi RFM.')

# peta
st.subheader('Sebaran revenue per negara bagian')
negara = df.groupby('customer_state').agg(
    revenue=('price', 'sum'), lat=('customer_lat', 'mean'), lng=('customer_lng', 'mean'),
).sort_values('revenue', ascending=False).reset_index()
negara['persen'] = negara['revenue'] / negara['revenue'].sum() * 100
peta = negara.dropna(subset=['lat', 'lng'])
titik = (df.dropna(subset=['customer_lat', 'customer_lng'])
         .groupby('customer_zip_code_prefix')
         .agg(revenue=('price', 'sum'), lat=('customer_lat', 'mean'), lng=('customer_lng', 'mean'))
         .sort_values('revenue').reset_index())

fig, axes = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [1.3, 1]})
if titik.empty:
    axes[0].axis('off')
    axes[0].text(0.5, 0.5, 'Tidak ada data koordinat\nuntuk rentang tanggal ini', ha='center', va='center', fontsize=12)
else:
    sebar = axes[0].scatter(titik['lng'], titik['lat'], s=10 + titik['revenue'] / 400, c=titik['revenue'],
                            cmap='YlOrRd', norm=LogNorm(), alpha=0.8, edgecolors='gray', linewidths=0.2)
    for _, baris in peta.head(5).iterrows():
        # label digeser sedikit supaya tidak menutupi titik di bawahnya
        axes[0].annotate(baris['customer_state'], (baris['lng'], baris['lat']), xytext=(8, 8), textcoords='offset points',
                         fontsize=11, fontweight='bold', bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.7, lw=0))
    axes[0].margins(0.1)
    axes[0].set_title('Revenue per kode pos (1 titik = 1 kode pos)')
    axes[0].set_xlabel('Longitude')
    axes[0].set_ylabel('Latitude')
    axes[0].set_aspect('equal')
    bar_warna = plt.colorbar(sebar, ax=axes[0], shrink=0.7, label='Revenue per kode pos (R$, skala log)')
    bar_warna.solids.set_alpha(1)
top10 = negara.head(10).sort_values('revenue')
axes[1].barh(top10['customer_state'], top10['persen'], color=['#9ecae1'] * (len(top10) - 1) + ['#08519c'])
for i, nilai in enumerate(top10['persen']):
    axes[1].text(nilai, i, f' {nilai:.1f}%', va='center')
axes[1].set_title('10 negara bagian revenue tertinggi')
axes[1].set_xlabel('% dari total revenue')
axes[1].set_xlim(0, top10['persen'].max() * 1.2)
plt.tight_layout()
st.pyplot(fig)
plt.close(fig)
