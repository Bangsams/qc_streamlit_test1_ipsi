"""
app.py — Halaman Utama (Home)
Aplikasi QC Digital untuk Deteksi & Analisis Defect
Fokus NDT: Ultrasonic Testing (UT) dan Magnetic Particle Testing (MT)
Studi Kasus: PT IHI Power Service Indonesia
"""

import streamlit as st
import pandas as pd
import sys, os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.data_handler import load_weld_process_data, load_ut_data, load_mt_data, load_combined_data
from utils.qc_utils import calculate_dpmo, classify_sigma_level
from utils.theme import inject_background

st.set_page_config(page_title="QC App - PT IHI Power Service", page_icon="🔧", layout="wide")
inject_background()

st.title("🔧 Aplikasi QC Digital — Deteksi & Analisis Defect")
st.caption("Studi Kasus: PT IHI Power Service Indonesia — Fabrikasi Boiler & Pressure Part | "
           "NDT: Ultrasonic Testing (UT) + Magnetic Particle Testing (MT)")

st.markdown("---")

weld_df = load_weld_process_data()
ut_df = load_ut_data()
mt_df = load_mt_data()
combined_df = load_combined_data()

col1, col2, col3, col4, col5 = st.columns(5)

total_joint = len(combined_df)
total_reject = (combined_df["final_hasil"] == "Reject").sum() if total_joint > 0 else 0
reject_rate = (total_reject / total_joint * 100) if total_joint > 0 else 0

with col1:
    st.metric("Total Joint Diinspeksi", f"{total_joint}")
with col2:
    st.metric("Reject UT (internal)", f"{(ut_df['ut_hasil']=='Reject').sum() if len(ut_df)>0 else 0}")
with col3:
    st.metric("Reject MT (permukaan)", f"{(mt_df['mt_hasil']=='Reject').sum() if len(mt_df)>0 else 0}")
with col4:
    st.metric("Reject Rate Gabungan", f"{reject_rate:.1f}%")

if total_joint > 0:
    dpmo_result = calculate_dpmo(total_reject, total_joint, opportunities_per_unit=1)
    level_int, dpmo_ref, kategori = classify_sigma_level(dpmo_result["sigma_level"])
    with col5:
        st.metric("Sigma Level Saat Ini", f"{dpmo_result['sigma_level']:.2f} ({kategori})")

st.markdown("---")

st.subheader("📋 Navigasi Aplikasi")
st.markdown("""
Gunakan menu di **sidebar kiri** untuk mengakses modul-modul berikut:

1. **📥 Input Data** — 3 form terpisah: parameter proses las, hasil Ultrasonic Testing (UT), dan hasil
   Magnetic Particle Testing (MT). Ketiganya dihubungkan lewat **Nomor Batch/Joint** yang sama.
2. **📊 SPC Analysis** — Xbar-S Chart dari UT Thickness Reading, P-Chart dari reject rate gabungan UT+MT,
   dan Process Capability (Cp/Cpk)
3. **🎯 DMAIC & Six Sigma** — Perhitungan DPMO & Sigma Level dari data gabungan UT+MT, plus tracker progres DMAIC
4. **🤖 Prediksi Defect (ML)** — Model machine learning memprediksi risiko reject (UT dan/atau MT) berdasarkan
   parameter proses las, plus breakdown kontribusi UT vs MT
5. **📄 Laporan** — Ringkasan otomatis untuk keperluan laporan QC/NCR
""")

st.info("""
**Kenapa dua metode NDT dipisah (UT + MT)?** Keduanya saling melengkapi: **UT** (Ultrasonic Testing)
mendeteksi cacat *internal/subsurface* seperti incomplete fusion atau slag inclusion, sementara **MT**
(Magnetic Particle Testing) mendeteksi cacat *permukaan* seperti crack atau undercut pada material
ferromagnetik. Satu joint dinyatakan **Reject** jika salah satu dari keduanya menemukan cacat yang
melebihi acceptance criteria (ASME Section V).
""")

st.markdown("---")
st.subheader("📈 Ringkasan Data Terkini")

tab1, tab2, tab3 = st.tabs(["Data Proses Las", "Data UT", "Data MT"])
with tab1:
    if len(weld_df) > 0:
        st.dataframe(weld_df.tail(10), use_container_width=True)
    else:
        st.info("Belum ada data. Silakan input data melalui menu 'Input Data'.")
with tab2:
    if len(ut_df) > 0:
        st.dataframe(ut_df.tail(10), use_container_width=True)
    else:
        st.info("Belum ada data UT.")
with tab3:
    if len(mt_df) > 0:
        st.dataframe(mt_df.tail(10), use_container_width=True)
    else:
        st.info("Belum ada data MT.")

st.markdown("---")
st.caption("Catatan: Aplikasi ini berbasis data digital (parameter mesin & hasil pembacaan alat NDT) — "
           "tidak memerlukan foto/gambar plant, sesuai kebijakan keamanan perusahaan.")
