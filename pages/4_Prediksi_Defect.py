"""
4_Prediksi_Defect.py — Machine Learning untuk Prediksi Risiko Reject (UT + MT)
Fitur: parameter proses las. Label: hasil akhir gabungan UT (internal defect)
dan MT (surface defect) — Reject jika salah satu metode NDT menyatakan Reject.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.theme import inject_background
from utils.data_handler import load_combined_data

st.set_page_config(page_title="Prediksi Defect - QC App", page_icon="🤖", layout="wide")
inject_background()
st.title("🤖 Prediksi Risiko Reject (UT + MT)")
st.caption("Model Random Forest: parameter proses las → prediksi hasil gabungan Ultrasonic Testing (UT) & Magnetic Particle Testing (MT)")

df = load_combined_data()

FEATURES = ["arus_A", "tegangan_V", "travel_speed_cm_min", "preheat_C", "interpass_C", "gas_flow_L_min"]

if len(df) < 20:
    st.warning(f"Data gabungan (proses las + UT + MT) belum cukup untuk melatih model (minimal ±20 baris, "
               f"saat ini: {len(df)}). Pastikan Nomor Batch pada ketiga form Input Data konsisten agar bisa digabungkan.")
else:
    df["label"] = (df["final_hasil"] == "Reject").astype(int)
    X = df[FEATURES]
    y = df["label"]

    if y.nunique() < 2:
        st.warning("Data hasil hanya berisi satu kelas (semua Accept atau semua Reject). Model butuh variasi data untuk belajar.")
    else:
        test_size = st.slider("Proporsi Data Testing", 0.1, 0.4, 0.2, 0.05)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42, stratify=y)

        model = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42, class_weight="balanced")
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)

        st.subheader("1️⃣ Performa Model")
        c1, c2, c3 = st.columns(3)
        c1.metric("Akurasi Model (Data Testing)", f"{acc:.1%}")
        c2.metric("Jumlah Data Training", f"{len(X_train)} baris")
        c3.metric("Reject dari UT+MT", f"{df['label'].sum()} / {len(df)}")

        cm = confusion_matrix(y_test, y_pred)
        fig_cm = go.Figure(data=go.Heatmap(
            z=cm, x=["Prediksi: Accept", "Prediksi: Reject"], y=["Aktual: Accept", "Aktual: Reject"],
            colorscale="Blues", text=cm, texttemplate="%{text}",
        ))
        fig_cm.update_layout(title="Confusion Matrix")
        st.plotly_chart(fig_cm, use_container_width=True)

        st.subheader("2️⃣ Feature Importance — Parameter Proses Paling Berpengaruh terhadap Reject (UT+MT)")
        st.caption("Menjawab fase Analyze DMAIC: parameter proses las mana yang paling menentukan hasil NDT?")
        importance = pd.DataFrame({
            "Parameter": FEATURES, "Importance": model.feature_importances_,
        }).sort_values("Importance", ascending=True)

        fig_imp = go.Figure(go.Bar(x=importance["Importance"], y=importance["Parameter"], orientation="h"))
        fig_imp.update_layout(title="Feature Importance (Random Forest)", xaxis_title="Tingkat Pengaruh")
        st.plotly_chart(fig_imp, use_container_width=True)

        st.subheader("3️⃣ Breakdown: Kontribusi UT vs MT terhadap Reject")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Reject Terdeteksi via UT (cacat internal)", f"{(df['ut_hasil']=='Reject').sum()}")
        with c2:
            st.metric("Reject Terdeteksi via MT (cacat permukaan)", f"{(df['mt_hasil']=='Reject').sum()}")
        st.caption("Jika satu jenis NDT jauh lebih dominan, ini mengarahkan fokus perbaikan proses "
                   "(mis. dominan UT → fokus ke parameter yang pengaruhi cacat internal seperti preheat/arus; "
                   "dominan MT → fokus ke parameter yang pengaruhi cacat permukaan seperti travel speed).")

        st.markdown("---")
        st.subheader("4️⃣ Simulasi Prediksi — Coba Parameter Baru")
        st.caption("Masukkan rencana parameter las untuk memprediksi risiko reject (gabungan UT+MT) sebelum eksekusi")

        c1, c2, c3 = st.columns(3)
        with c1:
            arus_in = st.number_input("Arus Las (A)", value=float(df["arus_A"].mean()))
            preheat_in = st.number_input("Preheat (°C)", value=float(df["preheat_C"].mean()))
        with c2:
            tegangan_in = st.number_input("Tegangan (V)", value=float(df["tegangan_V"].mean()))
            interpass_in = st.number_input("Interpass (°C)", value=float(df["interpass_C"].mean()))
        with c3:
            travel_in = st.number_input("Travel Speed (cm/menit)", value=float(df["travel_speed_cm_min"].mean()))
            gas_in = st.number_input("Gas Flow (L/menit)", value=float(df["gas_flow_L_min"].mean()))

        if st.button("🔮 Prediksi Risiko Reject", use_container_width=True):
            input_df = pd.DataFrame([[arus_in, tegangan_in, travel_in, preheat_in, interpass_in, gas_in]], columns=FEATURES)
            proba = model.predict_proba(input_df)[0][1]

            if proba >= 0.5:
                st.error(f"⚠️ Risiko Reject Tinggi (UT/MT): {proba:.1%} — pertimbangkan penyesuaian parameter sebelum eksekusi")
            elif proba >= 0.25:
                st.warning(f"⚡ Risiko Reject Sedang: {proba:.1%} — perlu pengawasan ekstra saat UT/MT")
            else:
                st.success(f"✅ Risiko Reject Rendah: {proba:.1%}")

    with st.expander("📄 Lihat Data Gabungan (Proses Las + UT + MT)"):
        st.dataframe(df, use_container_width=True)

st.markdown("---")
st.info("**Catatan:** Model ini adalah *decision support*, bukan pengganti keputusan inspector bersertifikat "
        "(ASNT Level II untuk UT/MT). Untuk pressure part/boiler yang safety-critical, keputusan akhir tetap "
        "harus divalidasi manusia sesuai ASME Section V.")
