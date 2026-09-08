"""
2_SPC_Analysis.py — Statistical Process Control
Xbar-S Chart pakai UT Thickness Reading, P-Chart pakai gabungan hasil UT+MT,
Process Capability (Cp/Cpk) dari data UT thickness reading.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.theme import inject_background
from utils.data_handler import load_ut_data, load_mt_data
from utils.qc_utils import xbar_s_chart, p_chart, process_capability

st.set_page_config(page_title="SPC Analysis - QC App", page_icon="📊", layout="wide")
inject_background()
st.title("📊 Statistical Process Control (SPC)")
st.caption("Berbasis data digital dari alat UT (Ultrasonic Testing) & MT (Magnetic Particle Testing)")

ut_df = load_ut_data()
mt_df = load_mt_data()

tab1, tab2, tab3 = st.tabs([
    "Xbar-S Chart (UT Thickness Reading)",
    "P-Chart (Reject Rate UT + MT)",
    "Process Capability (Cp/Cpk)",
])

# ============================================================
# TAB 1: Xbar-S Chart dari UT Thickness Reading
# ============================================================
with tab1:
    st.markdown("Data ketebalan diperoleh dari **pembacaan digital UT flaw detector** (thickness reading), "
                 "dikelompokkan per 5 pembacaan berurutan sebagai satu subgroup (rational subgrouping).")

    if len(ut_df) < 10:
        st.warning("Minimal 10 baris data UT diperlukan (2 subgroup x 5) untuk membuat control chart.")
    else:
        n_sub = len(ut_df) // 5
        sub_data = ut_df["thickness_reading_mm"].iloc[: n_sub * 5].values.reshape(n_sub, 5)
        sub_df = pd.DataFrame(sub_data, columns=[f"sampel_{i+1}" for i in range(5)])
        sub_df["batch_group"] = [f"G{i+1}" for i in range(n_sub)]

        sample_cols = [f"sampel_{i+1}" for i in range(5)]
        result, limits = xbar_s_chart(sub_df, sample_cols)
        batch_labels = sub_df["batch_group"]

        st.markdown(f"**Konstanta SPC (n={limits['n']}):** A3 = {limits['A3']:.3f} | B3 = {limits['B3']:.3f} | B4 = {limits['B4']:.3f}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("X̄-bar (rata-rata)", f"{limits['xbarbar']:.3f} mm")
        c2.metric("S-bar", f"{limits['sbar']:.3f} mm")
        c3.metric("UCL X̄", f"{limits['ucl_xbar']:.3f} mm")
        c4.metric("LCL X̄", f"{limits['lcl_xbar']:.3f} mm")

        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=batch_labels, y=result["Xbar"], mode="lines+markers", name="X̄ (Xbar)"))
        fig1.add_hline(y=limits["ucl_xbar"], line_dash="dash", line_color="red", annotation_text="UCL")
        fig1.add_hline(y=limits["xbarbar"], line_color="green", annotation_text="CL")
        fig1.add_hline(y=limits["lcl_xbar"], line_dash="dash", line_color="red", annotation_text="LCL")
        fig1.update_layout(title="Xbar Chart — UT Thickness Reading", xaxis_title="Grup Subgroup", yaxis_title="Rata-rata Ketebalan (mm)")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=batch_labels, y=result["S"], mode="lines+markers", name="S", line_color="orange"))
        fig2.add_hline(y=limits["ucl_s"], line_dash="dash", line_color="red", annotation_text="UCL")
        fig2.add_hline(y=limits["sbar"], line_color="green", annotation_text="CL")
        fig2.add_hline(y=limits["lcl_s"], line_dash="dash", line_color="red", annotation_text="LCL")
        fig2.update_layout(title="S Chart — Standar Deviasi UT Thickness Reading", xaxis_title="Grup Subgroup", yaxis_title="Std Dev (mm)")
        st.plotly_chart(fig2, use_container_width=True)

# ============================================================
# TAB 2: P-Chart dari gabungan reject rate UT + MT
# ============================================================
with tab2:
    st.markdown("Proporsi reject dihitung per hari, digabung dari **hasil UT** (cacat internal) dan "
                 "**hasil MT** (cacat permukaan) — satu joint dianggap reject jika salah satu metode menyatakan Reject.")

    if len(ut_df) == 0 or len(mt_df) == 0:
        st.warning("Data UT dan/atau MT belum tersedia.")
    else:
        merged = ut_df[["tanggal", "batch_id", "ut_hasil"]].merge(
            mt_df[["tanggal", "batch_id", "mt_hasil"]], on=["tanggal", "batch_id"], how="inner"
        )
        merged["final_hasil"] = np.where(
            (merged["ut_hasil"] == "Reject") | (merged["mt_hasil"] == "Reject"), "Reject", "Accept"
        )
        grouped = merged.groupby("tanggal").agg(
            n_inspeksi=("final_hasil", "count"),
            n_defect=("final_hasil", lambda x: (x == "Reject").sum()),
        ).reset_index()

        if len(grouped) < 2:
            st.warning("Minimal 2 hari data diperlukan untuk P-Chart.")
        else:
            result, pbar = p_chart(grouped["n_inspeksi"], grouped["n_defect"])
            st.metric("p-bar (proporsi reject rata-rata)", f"{pbar:.3%}")

            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=grouped["tanggal"], y=result["p"], mode="lines+markers", name="p"))
            fig3.add_trace(go.Scatter(x=grouped["tanggal"], y=result["UCL"], mode="lines", name="UCL", line=dict(dash="dash", color="red")))
            fig3.add_trace(go.Scatter(x=grouped["tanggal"], y=result["LCL"], mode="lines", name="LCL", line=dict(dash="dash", color="red")))
            fig3.add_hline(y=pbar, line_color="green", annotation_text="CL (p-bar)")
            fig3.update_layout(title="P-Chart — Reject Rate Gabungan UT + MT", xaxis_title="Tanggal", yaxis_title="Proporsi Reject")
            st.plotly_chart(fig3, use_container_width=True)

            st.dataframe(pd.concat([grouped, result], axis=1), use_container_width=True)

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Reject dari UT saja", f"{(merged['ut_hasil']=='Reject').sum()}")
            with c2:
                st.metric("Reject dari MT saja", f"{(merged['mt_hasil']=='Reject').sum()}")

# ============================================================
# TAB 3: Process Capability dari UT Thickness Reading
# ============================================================
with tab3:
    if len(ut_df) < 10:
        st.warning("Minimal 10 baris data UT diperlukan.")
    else:
        st.markdown("**Spesifikasi Desain (Ketebalan Boiler Pressure Part)**")
        c1, c2, c3 = st.columns(3)
        with c1: target = st.number_input("Target (mm)", value=10.0, step=0.1)
        with c2: lsl = st.number_input("LSL (mm)", value=9.5, step=0.1)
        with c3: usl = st.number_input("USL (mm)", value=10.5, step=0.1)

        cap = process_capability(ut_df["thickness_reading_mm"], lsl, usl)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Grand Mean", f"{cap['mean']:.3f} mm")
        c2.metric("Sigma (σ)", f"{cap['sigma']:.3f} mm")
        c3.metric("Cp", f"{cap['cp']:.2f}")
        c4.metric("Cpk", f"{cap['cpk']:.2f}")

        if cap["cpk"] >= 1.33:
            st.success(f"Status: {cap['status']}")
        elif cap["cpk"] >= 1.0:
            st.warning(f"Status: {cap['status']}")
        else:
            st.error(f"Status: {cap['status']}")

        fig4 = go.Figure()
        fig4.add_trace(go.Histogram(x=ut_df["thickness_reading_mm"], nbinsx=20, name="Distribusi Thickness Reading"))
        fig4.add_vline(x=lsl, line_dash="dash", line_color="red", annotation_text="LSL")
        fig4.add_vline(x=usl, line_dash="dash", line_color="red", annotation_text="USL")
        fig4.add_vline(x=cap["mean"], line_color="green", annotation_text="Mean")
        fig4.update_layout(title="Distribusi UT Thickness Reading vs Spesifikasi", xaxis_title="Ketebalan (mm)", yaxis_title="Frekuensi")
        st.plotly_chart(fig4, use_container_width=True)
