"""
3_DMAIC_SixSigma.py — Kalkulator DPMO/Sigma Level + Tracker Progres DMAIC
"""

import streamlit as st
import pandas as pd
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.theme import inject_background
from utils.data_handler import load_combined_data
from utils.qc_utils import calculate_dpmo, classify_sigma_level, SIGMA_BENCHMARK

st.set_page_config(page_title="DMAIC & Six Sigma - QC App", page_icon="🎯", layout="wide")
inject_background()
st.title("🎯 Six Sigma DMAIC")
st.caption("Berbasis data gabungan hasil Ultrasonic Testing (UT) dan Magnetic Particle Testing (MT)")

combined_df = load_combined_data()

st.subheader("1️⃣ Kalkulator DPMO & Sigma Level")

col1, col2 = st.columns(2)
with col1:
    total_unit = len(combined_df) if len(combined_df) > 0 else st.number_input("Total Unit Diinspeksi", min_value=1, value=100)
    if len(combined_df) > 0:
        st.info(f"Otomatis dari data gabungan UT+MT: {total_unit} joint diinspeksi")
with col2:
    total_defect = (combined_df["final_hasil"] == "Reject").sum() if len(combined_df) > 0 else st.number_input("Total Reject", min_value=0, value=10)
    if len(combined_df) > 0:
        st.info(f"Otomatis dari data: {total_defect} joint Reject (UT dan/atau MT)")

opportunities = st.number_input("Peluang Cacat per Unit (Opportunities)", min_value=1, value=1,
                                  help="Jumlah jenis cacat potensial per satu weld joint")

if total_unit > 0:
    result = calculate_dpmo(total_defect, total_unit, opportunities)
    level_int, dpmo_ref, kategori = classify_sigma_level(result["sigma_level"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("DPU", f"{result['dpu']:.4f}")
    c2.metric("DPMO", f"{result['dpmo']:,.0f}")
    c3.metric("Sigma Level", f"{result['sigma_level']:.2f}")
    c4.metric("Kategori", kategori)

    st.markdown("**Tabel Acuan Sigma Level (Long-term, shift 1.5σ)**")
    bench_df = pd.DataFrame(SIGMA_BENCHMARK, columns=["Sigma Level", "DPMO Acuan", "Kategori"])
    bench_df["Tercapai"] = bench_df["Sigma Level"].apply(lambda x: "✅" if x == level_int else "")
    st.dataframe(bench_df, use_container_width=True, hide_index=True)

    next_level = [b for b in SIGMA_BENCHMARK if b[0] == level_int + 1]
    if next_level:
        st.info(f"💡 Untuk naik ke Sigma Level {level_int+1}, DPMO perlu diturunkan hingga di bawah **{next_level[0][1]:,.1f}** (saat ini: {result['dpmo']:,.0f})")

st.markdown("---")
st.subheader("2️⃣ Tracker Progres Fase DMAIC")
st.caption("Isi status dan catatan tiap fase — tersimpan selama sesi aplikasi berjalan")

if "dmaic_status" not in st.session_state:
    st.session_state.dmaic_status = {
        "Define": {"status": "Belum Mulai", "catatan": ""},
        "Measure": {"status": "Belum Mulai", "catatan": ""},
        "Analyze": {"status": "Belum Mulai", "catatan": ""},
        "Improve": {"status": "Belum Mulai", "catatan": ""},
        "Control": {"status": "Belum Mulai", "catatan": ""},
    }

phase_info = {
    "Define": "Definisikan masalah, tujuan proyek, dan ruang lingkup (Project Charter, SIPOC)",
    "Measure": "Kumpulkan data baseline & validasi sistem pengukuran (Gage R&R, Control Chart)",
    "Analyze": "Cari akar penyebab masalah (Fishbone, 5 Whys, Pareto Chart)",
    "Improve": "Rancang & terapkan solusi (FMEA, DOE, Pilot Test)",
    "Control": "Pastikan perbaikan bertahan (Control Plan, SPC Monitoring, SOP)",
}

for phase, info in phase_info.items():
    with st.expander(f"**{phase}** — {info}"):
        status = st.selectbox(
            "Status", ["Belum Mulai", "Sedang Berjalan", "Selesai"],
            key=f"status_{phase}",
            index=["Belum Mulai", "Sedang Berjalan", "Selesai"].index(st.session_state.dmaic_status[phase]["status"]),
        )
        catatan = st.text_area("Catatan / Temuan", value=st.session_state.dmaic_status[phase]["catatan"], key=f"catatan_{phase}")
        st.session_state.dmaic_status[phase]["status"] = status
        st.session_state.dmaic_status[phase]["catatan"] = catatan

progress_map = {"Belum Mulai": 0, "Sedang Berjalan": 0.5, "Selesai": 1}
overall_progress = sum(progress_map[v["status"]] for v in st.session_state.dmaic_status.values()) / 5
st.progress(overall_progress, text=f"Progres Keseluruhan Proyek DMAIC: {overall_progress*100:.0f}%")
