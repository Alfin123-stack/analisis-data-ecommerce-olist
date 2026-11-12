from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st
import folium
from streamlit_folium import st_folium

sns.set_theme(style='whitegrid')
st.set_page_config(page_title='Dashboard E-Commerce', layout='wide')


@st.cache_data
def load_data():
    path = Path(__file__).parent / 'main_data.csv'
    df = pd.read_csv(path, parse_dates=['order_purchase_timestamp'])
    return df


# batas bin RFM (asumsi analisis, sama dengan notebook)
BATAS_RECENCY = [0, 90, 180, 365, np.inf]   # hari sejak belanja terakhir
BATAS_MONETARY = [0, 50, 100, 200, np.inf]  # total belanja (R$)


def hitung_rfm(df):
    tanggal_acuan = df['order_purchase_timestamp'].max() + pd.Timedelta(days=1)
    rfm = df.groupby('customer_unique_id').agg(
        terakhir_beli=('order_purchase_timestamp', 'max'),
        frequency=('order_id', 'nunique'),
        monetary=('price', 'sum'),
    ).reset_index()
    rfm['recency'] = (tanggal_acuan - rfm['terakhir_beli']).dt.days
    # binning dengan batas tetap (pd.cut), skor 4 = paling bagus
    rfm['r_score'] = pd.cut(rfm['recency'], bins=BATAS_RECENCY, labels=[4, 3, 2, 1], include_lowest=True).astype(int)
    rfm['m_score'] = pd.cut(rfm['monetary'], bins=BATAS_MONETARY, labels=[1, 2, 3, 4], include_lowest=True).astype(int)

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
    return segmen.sort_values('jumlah_customer'), rfm


BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']


def format_tanggal(tgl):
    # nama bulan bahasa Indonesia, tidak bergantung pada pengaturan bahasa komputer
    return f'{tgl.day:02d} {BULAN[tgl.month - 1]} {tgl.year}'


def format_rupiah(nilai, _=None):
    # angka bulat ditampilkan dengan pemisah ribuan, angka kecil diberi desimal
    return f'{nilai:,.0f}' if abs(nilai - round(nilai)) < 1e-9 else f'{nilai:,.2f}'


def pilih_satuan(nilai):
    # pilih satuan sumbu supaya angka tidak terlalu kecil (misalnya 0.0004 juta)
    if nilai >= 1e6:
        return 1e6, 'juta R$'
    if nilai >= 1e3:
        return 1e3, 'ribu R$'
    return 1, 'R$'


# kelas kontribusi revenue per negara bagian (binning dengan batas tetap, pd.cut)
BATAS_KELAS = [0, 1, 3, 6, 15, 101]
LABEL_KELAS = ['< 1%', '1 - 3%', '3 - 6%', '6 - 15%', '>= 15%']
WARNA_KELAS = dict(zip(LABEL_KELAS, ['#ffffb2', '#fecc5c', '#fd8d3c', '#f03b20', '#bd0026']))
BASIS_KECIL = 1000  # negara bagian dengan customer kurang dari ini ditandai basis kecil


CARTO_KEY = 'cb1_53zh_1_e69810704b79cac8c18d7ef8'  # API key peta dasar CARTO, ditulis langsung


def ambil_kunci_carto():
    return CARTO_KEY


def buat_peta(negara, rata_nasional, beda_basis):
    # satu lingkaran per negara bagian, ukuran sama, hanya warna yang membawa kelas kontribusi revenue
    negara = negara.copy()
    negara['kelas'] = pd.cut(negara['persen'], bins=BATAS_KELAS, labels=LABEL_KELAS, right=False)
    kunci_carto = ambil_kunci_carto()
    if kunci_carto:
        peta_folium = folium.Map(
            location=[-14.2, -51.9], zoom_start=4, control_scale=True,
            tiles='https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=' + kunci_carto,
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        )
    else:
        peta_folium = folium.Map(location=[-14.2, -51.9], zoom_start=4, tiles=None, control_scale=True)
    for _, baris in negara.iterrows():
        selisih = baris['revenue_per_customer'] - rata_nasional
        catatan = ''
        if baris['jumlah_customer'] < BASIS_KECIL:
            catatan = f'<br><i>Basis kecil (&lt; {BASIS_KECIL:,} customer), angka belum stabil.</i>'
        popup_html = (
            f"<b>{baris['customer_state']}</b><br>"
            f"Revenue: R$ {baris['revenue']:,.0f} ({baris['persen']:.1f}% dari total)<br>"
            f"Customer: {baris['jumlah_customer']:,}<br>"
            f"Revenue per customer: R$ {baris['revenue_per_customer']:.1f}<br>"
            f"Dibanding rata-rata nasional (R$ {rata_nasional:.1f}): R$ {selisih:+.1f}"
            + catatan
        )
        folium.CircleMarker(
            location=[baris['lat'], baris['lng']], radius=8,
            color='#333333', weight=2, dash_array='4 4' if beda_basis and baris['jumlah_customer'] < BASIS_KECIL else None,
            fill=True, fill_color=WARNA_KELAS[baris['kelas']], fill_opacity=0.9,
            tooltip=baris['customer_state'], popup=folium.Popup(popup_html, max_width=280),
        ).add_to(peta_folium)
    return peta_folium


def legenda_peta(beda_basis):
    # legenda dibuat di sisi Streamlit supaya pasti tampil
    kotak = ''.join(
        f'<span style="display:inline-block;width:12px;height:12px;background:{warna};border:1px solid #333333;'
        f'margin:0 4px 0 12px;vertical-align:middle;"></span>{nama}'
        for nama, warna in WARNA_KELAS.items()
    )
    basis_kecil = ('<span style="display:inline-block;width:10px;height:10px;border:2px dashed #333333;border-radius:50%;'
                   'margin:0 4px 0 16px;vertical-align:middle;"></span>Garis putus-putus: basis kecil (&lt; 1,000 customer)')
    keterangan = f'<br>{basis_kecil}' if beda_basis else ''
    return f'<div style="font-size:0.85rem;"><b>Kontribusi revenue (% dari total):</b>{kotak}{keterangan}</div>'


main_df = load_data()
jumlah_negara_total = main_df['customer_state'].nunique()

# sidebar
st.sidebar.markdown('### Muhammad Alfin Alfarizi')
st.sidebar.caption('ID Dicoding: muhammad-alfin')
st.sidebar.header('Filter')
tgl_min = main_df['order_purchase_timestamp'].min().date()
tgl_max = main_df['order_purchase_timestamp'].max().date()
rentang = st.sidebar.date_input('Rentang tanggal pesanan', value=(tgl_min, tgl_max),
                                min_value=tgl_min, max_value=tgl_max,
                                help='Semua angka dan grafik di halaman ini mengikuti rentang tanggal ini.')
if len(rentang) != 2:
    st.info('Pilih tanggal awal dan tanggal akhir.')
    st.stop()

mulai, selesai = pd.to_datetime(rentang[0]), pd.to_datetime(rentang[1]) + pd.Timedelta(days=1)
df = main_df[(main_df['order_purchase_timestamp'] >= mulai) & (main_df['order_purchase_timestamp'] < selesai)]
if df.empty:
    st.warning('Tidak ada data di rentang tanggal ini.')
    st.stop()

periode = f"{format_tanggal(rentang[0])} - {format_tanggal(rentang[1])}"

# judul dan ringkasan
st.title('Dashboard E-Commerce Public Dataset')
st.caption('Data pesanan yang sudah terkirim (delivered), Januari 2017 - Agustus 2018. Revenue dihitung dari harga produk saja, tanpa ongkir, dalam R\\$.')

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
axes[0].plot(sumbu_x, tren['jumlah_order'], marker='o', color='#08519c')
axes[0].set_title(f'Jumlah pesanan per {satuan_waktu}')
axes[0].set_ylabel('Jumlah pesanan')
axes[0].yaxis.set_major_locator(MaxNLocator(integer=True, steps=[1, 2, 5, 10]))
axes[1].plot(sumbu_x, tren['revenue'] / pembagi_rev, marker='o', color='#e6550d')
axes[1].set_title(f'Revenue per {satuan_waktu}')
axes[1].set_ylabel(f'Revenue ({label_rev})')
for ax in axes:
    ax.set_ylim(bottom=0)
    ax.set_xlabel('Tanggal' if harian else 'Bulan')
    ax.grid(axis='x', visible=False)
    if harian:
        if len(tren) <= 10:
            ax.set_xticks(list(tren['waktu']))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: format_tanggal(mdates.num2date(v))))
    ax.tick_params(axis='x', rotation=60)
sns.despine(fig=fig)
fig.suptitle(f'Periode {periode}', fontsize=12)
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


def format_persen(nilai):
    # persen yang sangat kecil diberi 3 desimal supaya tidak terbaca 0.0%
    return f'{nilai:.1f}%' if nilai >= 0.1 else f'{nilai:.3f}%'


if kategori.empty:
    st.info('Tidak ada produk berkategori di rentang tanggal ini.')
else:
    if len(kategori) < 10:
        st.info(f'Rentang ini hanya punya {len(kategori)} kategori, jadi kelompok terendah hanya berisi kategori di luar 5 teratas (bisa kurang dari 5).')
    top5 = kategori.head(5)
    bottom5 = kategori.iloc[5:].tail(5)  # tidak mengulang kategori yang sudah ada di 5 teratas

    def panel_kategori(ax, data, judul, sorot_terakhir):
        # satu panel = satu sumbu. Biru tua menyorot yang paling ekstrem di panel itu.
        warna = ['#9ecae1'] * len(data)
        warna[-1 if sorot_terakhir else 0] = '#08519c'
        ax.barh(range(len(data)), data['revenue'], color=warna, height=0.7)
        ax.set_yticks(range(len(data)))
        ax.set_yticklabels(data['category'])
        ax.invert_yaxis()  # urutan dari revenue terbesar di atas
        for i, (rev, pct) in enumerate(zip(data['revenue'], data['persen'])):
            ax.text(rev, i, f'  R$ {rev:,.0f} ({format_persen(pct)})', va='center')
        ax.set_xlim(0, data['revenue'].max() * 1.5)  # ruang untuk label angka
        ax.set_title(judul)
        ax.set_xlabel('Revenue (R$)')
        ax.grid(False)  # nilai sudah ditulis di ujung batang, gridline tidak perlu
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5))  # batasi jumlah tick supaya label tidak bertumpuk
        ax.xaxis.set_major_formatter(FuncFormatter(format_rupiah))

    jumlah_panel = 2 if len(bottom5) else 1
    fig, axes = plt.subplots(1, jumlah_panel, figsize=(14, 4.5))
    axes = np.atleast_1d(axes)
    panel_kategori(axes[0], top5, f'{len(top5)} kategori tertinggi', sorot_terakhir=False)
    if len(bottom5):
        panel_kategori(axes[1], bottom5, f'{len(bottom5)} kategori terendah (skala sumbu berbeda)', sorot_terakhir=True)
    sns.despine(fig=fig)
    fig.suptitle(f'Revenue per kategori produk, periode {periode}', fontsize=12)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)
    st.caption('Kedua panel memakai skala sumbu yang berbeda supaya batang kategori terendah terlihat. Bandingkan angkanya, bukan panjang batangnya. '
               'Angka di ujung batang: revenue dalam R\\$ dan persen dari total revenue di rentang yang dipilih. Produk tanpa kategori tidak ikut diperingkat.')
    teks_temuan = (f"**Temuan:** kategori teratas adalah **{top5.iloc[0]['category']}** (R\\$ {top5.iloc[0]['revenue']:,.0f}, {format_persen(top5.iloc[0]['persen'])} dari revenue). "
                   f"{len(top5)} kategori teratas menyumbang {top5['persen'].sum():.1f}% revenue")
    if len(bottom5):
        teks_temuan += f", sedangkan {len(bottom5)} kategori terendah hanya {bottom5['persen'].sum():.2f}%."
    else:
        teks_temuan += '.'
    st.markdown(teks_temuan)

# segmentasi RFM
st.subheader('Segmentasi customer (RFM)')
segmen, rfm_tabel = hitung_rfm(df)
# segmen Belanja Besar disorot dengan warna tua, segmen lain dengan warna muda
warna_segmen = ['#08519c' if 'Besar' in nama_segmen else '#9ecae1' for nama_segmen in segmen['segmen']]
besar = segmen[segmen['segmen'].str.contains('Besar')]
# kedua panel memakai skala sumbu yang sama supaya panjang batang bisa dibandingkan
batas = max(segmen['persen_customer'].max(), segmen['persen_revenue'].max()) * 1.75  # ruang untuk label angka
# label: persen, lalu angka aslinya dalam kurung
label_customer = [f' {p:.1f}% ({n:,})' for p, n in zip(segmen['persen_customer'], segmen['jumlah_customer'])]
label_revenue = [f' {p:.1f}% (R$ {r:,.0f})' for p, r in zip(segmen['persen_revenue'], segmen['total_revenue'])]
# tidak memakai sharey: nama segmen tampil di kedua panel
fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))
panel_rfm = [
    (axes[0], 'persen_customer', label_customer, 'Persentase customer', '% dari total customer'),
    (axes[1], 'persen_revenue', label_revenue, 'Persentase revenue', '% dari total revenue'),
]
for ax, kolom, label, judul, label_x in panel_rfm:
    ax.barh(segmen['segmen'], segmen[kolom], color=warna_segmen)
    for i, teks in enumerate(label):
        ax.text(segmen[kolom].iloc[i], i, teks, va='center')
    ax.set_title(judul)
    ax.set_xlabel(label_x)
    ax.set_xlim(0, batas)
    ax.set_xticks([t for t in ax.get_xticks() if 0 <= t <= 100])  # sumbu persen tidak boleh menunjukkan angka di atas 100
    ax.grid(False)  # nilai sudah ditulis di ujung batang, gridline tidak perlu
# legenda arti warna di dalam grafik
fig.legend(handles=[Patch(color='#08519c', label='Segmen Belanja Besar (Aktif dan Pasif)'),
                    Patch(color='#9ecae1', label='Segmen lainnya')],
           loc='lower center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.0))
sns.despine(fig=fig)
fig.suptitle(f'Segmentasi customer, periode {periode}\n'
             f'Segmen Belanja Besar: {besar["persen_customer"].sum():.1f}% customer, {besar["persen_revenue"].sum():.1f}% revenue', fontsize=12)
plt.tight_layout(rect=[0, 0.07, 1, 0.92])
st.pyplot(fig)
plt.close(fig)
st.caption('Aktif = belanja terakhir dalam 180 hari sebelum tanggal akhir rentang yang dipilih. Belanja Besar = total belanja di atas R\\$ 100, hanya untuk customer yang belanja sekali. Setia = belanja 2 kali atau lebih, dihitung lebih dulu. Batas ini asumsi analisis, bukan ketentuan bisnis. Pada rentang sekitar 6 bulan atau kurang, hampir semua customer otomatis berstatus Aktif. Warna tua = segmen Belanja Besar, bukan nilai tertinggi. Kedua grafik memakai skala sumbu yang sama. Angka dalam kurung: jumlah customer dan total revenue (R\\$). RFM hanya dihitung dari rentang tanggal yang dipilih.')

# customer terbaik per parameter RFM
st.subheader('Customer terbaik per parameter RFM')
# kalau nilainya seri, dipilih customer yang total belanjanya lebih besar
top_recency = rfm_tabel.sort_values(['recency', 'monetary'], ascending=[True, False]).head(5)
top_frequency = rfm_tabel.sort_values(['frequency', 'monetary'], ascending=[False, False]).head(5)
top_monetary = rfm_tabel.sort_values('monetary', ascending=False).head(5)
panel_terbaik = [
    (top_recency, 'recency', 'Recency terkecil (hari)', lambda v: f' {v:,.0f} hari', 'Hari sejak belanja terakhir'),
    (top_frequency, 'frequency', 'Frequency terbanyak (pesanan)', lambda v: f' {v:,.0f} pesanan', 'Jumlah pesanan'),
    (top_monetary, 'monetary', 'Monetary terbesar (R$)', lambda v: f' R$ {v:,.0f}', 'Total belanja (R$)'),
]
fig, axes = plt.subplots(1, 3, figsize=(16, 4))
for ax, (data, kolom, judul, format_label, label_x) in zip(axes, panel_terbaik):
    data = data.iloc[::-1]  # customer terbaik ada di paling atas
    warna = ['#9ecae1'] * (len(data) - 1) + ['#08519c']
    if len(data) > 1 and data[kolom].iloc[-1] == data[kolom].iloc[-2]:
        warna = ['#9ecae1'] * len(data)  # posisi teratas seri, jadi tidak ada yang disorot
    ax.barh(data['customer_unique_id'].str[:8], data[kolom], color=warna)
    for i, nilai in enumerate(data[kolom]):
        ax.text(nilai, i, format_label(nilai), va='center')
    ax.set_xlim(0, data[kolom].max() * 1.45)  # ruang untuk label angka
    ax.set_title(judul)
    ax.set_xlabel(label_x)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.grid(False)  # nilai sudah ditulis di ujung batang
sns.despine(fig=fig)
fig.suptitle(f'Customer terbaik tiap parameter RFM, periode {periode}', fontsize=12)
plt.tight_layout()
st.pyplot(fig)
plt.close(fig)
n_seri = int((rfm_tabel['recency'] == rfm_tabel['recency'].min()).sum())
catatan_seri = ''
if n_seri > 5:
    catatan_seri = f' Pada rentang ini, {n_seri:,} customer sama-sama punya recency {int(rfm_tabel["recency"].min())} hari, jadi Recency tidak bisa menunjuk satu customer paling baru.'
st.caption('ID customer disingkat jadi 8 karakter pertama. Kalau nilainya seri, dipilih customer yang total belanjanya lebih besar. Warna tua = customer teratas di panel itu (tidak ada yang diberi warna tua kalau nilainya seri).' + catatan_seri + ' Dihitung dari rentang tanggal yang dipilih.')

terbaik_m = top_monetary.iloc[0]
terbaik_f = top_frequency.iloc[0]
st.markdown(f"**Temuan:** customer dengan belanja terbesar menghabiskan R\\$ {terbaik_m['monetary']:,.0f} (ID {terbaik_m['customer_unique_id'][:8]}). "
            f"Pesanan terbanyak oleh satu customer adalah {int(terbaik_f['frequency'])} pesanan.")

# peta
st.subheader('Sebaran revenue per negara bagian')
negara = df.groupby('customer_state').agg(
    revenue=('price', 'sum'), jumlah_customer=('customer_unique_id', 'nunique'),
    lat=('customer_lat', 'mean'), lng=('customer_lng', 'mean'),
).sort_values('revenue', ascending=False).reset_index()
negara['persen'] = negara['revenue'] / negara['revenue'].sum() * 100
negara['revenue_per_customer'] = negara['revenue'] / negara['jumlah_customer']
rata_nasional = df['price'].sum() / df['customer_unique_id'].nunique()
negara_peta = negara.dropna(subset=['lat', 'lng'])

kol_peta, kol_bar = st.columns([1.3, 1])
with kol_peta:
    if negara_peta.empty:
        st.info('Tidak ada data koordinat untuk rentang tanggal ini.')
    else:
        jumlah_kecil = int((negara_peta['jumlah_customer'] < BASIS_KECIL).sum())
        beda_basis = 0 < jumlah_kecil < len(negara_peta)  # garis putus-putus hanya berguna kalau ada yang berbeda
        st_folium(buat_peta(negara_peta, rata_nasional, beda_basis), key='peta_negara', height=520,
                  use_container_width=True, returned_objects=[])
        st.markdown(legenda_peta(beda_basis), unsafe_allow_html=True)
        if len(negara_peta) < jumlah_negara_total:
            st.caption(f'{len(negara_peta)} dari {jumlah_negara_total} negara bagian tergambar di peta (punya pesanan dan koordinat) di rentang ini. Negara bagian lainnya tidak digambar.')
        if jumlah_kecil == len(negara_peta):
            batas_teks = f'{BASIS_KECIL:,}'
            st.caption(f'Semua negara bagian punya kurang dari {batas_teks} customer di rentang ini, jadi angka per customer di popup kurang stabil.')
        if not ambil_kunci_carto():
            st.caption('Peta dasar tidak tampil karena CARTO_KEY belum diisi di Secrets. Lingkaran dan legenda tetap benar.')

with kol_bar:
    top10 = negara.head(10).sort_values('revenue')
    kelas_top10 = pd.cut(top10['persen'], bins=BATAS_KELAS, labels=LABEL_KELAS, right=False)
    fig, ax = plt.subplots(figsize=(6, 5.2))
    # warna batang sama dengan warna lingkaran di peta (kelas kontribusi revenue)
    ax.barh(top10['customer_state'], top10['persen'], color=[WARNA_KELAS[k] for k in kelas_top10],
            edgecolor='#333333', linewidth=0.8)
    for i, nilai in enumerate(top10['persen']):
        ax.text(nilai, i, f' {nilai:.1f}%', va='center')
    ax.set_title(f'10 negara bagian revenue tertinggi\n(periode {periode})', fontsize=11)
    ax.set_xlabel('% dari total revenue')
    ax.set_xlim(0, top10['persen'].max() * 1.2)
    ax.grid(False)  # nilai sudah ditulis di ujung batang
    sns.despine(fig=fig)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

tiga_teratas = negara.head(3)
st.markdown(f"**Temuan:** {negara.iloc[0]['customer_state']} menyumbang {negara.iloc[0]['persen']:.1f}% revenue. "
            f"{len(tiga_teratas)} negara bagian teratas ({', '.join(tiga_teratas['customer_state'])}) bersama-sama menyumbang {tiga_teratas['persen'].sum():.1f}%.")

st.caption('Peta: satu lingkaran per negara bagian, ukuran sama, hanya warna yang menunjukkan kelas kontribusi revenue (batas kelas tetap). '
           'Klik lingkaran untuk melihat revenue, jumlah customer, dan revenue per customer dibanding rata-rata nasional. '
           'Negara bagian dengan kurang dari 1,000 customer ditandai basis kecil di popup, dan diberi garis tepi putus-putus kalau hanya sebagian negara bagian yang berbasis kecil, karena angkanya mudah bergeser. '
           'Warna batang di grafik kanan sama dengan warna lingkaran di peta. Posisi memakai rata-rata koordinat customer, jadi hanya perkiraan.')
