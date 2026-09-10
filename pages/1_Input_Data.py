"""
1_Input_Data.py — Formulir input parameter proses las, hasil UT, dan hasil MT
Update: tambah field material/joint/lingkungan (untuk akurasi model ML) dan
tanggal kalibrasi alat NDT (proxy risiko drift pengukuran).
"""

import streamlit as st
import sys, os
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.theme import inject_background
from utils.data_handler import (
    save_weld_process_record, load_weld_process_data,
    save_ut_record, load_ut_data,
    save_mt_record, load_mt_data,
    save_pt_record, load_pt_data,
    fetch_weather_data,
)
from utils.qc_utils import (
    check_pt_dwell_time, check_pt_surface_temp, check_pt_light_intensity,
    PT_PENETRANT_TYPE_OPTIONS, PT_CLEANING_METHOD_OPTIONS, PT_DEVELOPER_TYPE_OPTIONS,
    PT_LIGHTING_METHOD_OPTIONS, PT_JOINT_TYPE_OPTIONS,
)

st.set_page_config(page_title="Input Data - QC App", page_icon="📥", layout="wide")
inject_background()
st.title("📥 Input Data QC")
st.caption("Catat parameter dari display digital mesin las & alat NDT (UT/MT) ke form ini")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔩 Parameter Proses Las", "📡 Hasil Ultrasonic Testing (UT)",
    "🧲 Hasil Magnetic Particle Testing (MT)", "🔴 Hasil Liquid Penetrant Testing (PT)",
])

# ============================================================
# TAB 1: Weld Process Parameters (+ Material, Joint, Lingkungan)
# ============================================================
with tab1:
    st.subheader("Form Parameter Proses Las")
    st.caption("Data ini menjadi fitur root-cause analysis — dihubungkan ke hasil UT/MT lewat Nomor Batch")

    # --- Ambil data cuaca di LUAR form (form Streamlit tidak bisa trigger aksi sebelum submit) ---
    st.markdown("**🌦️ Data Lingkungan**")
    wcol1, wcol2, wcol3 = st.columns([1, 1, 1])
    with wcol1:
        tgl_cuaca = st.date_input("Tanggal (untuk tarik data cuaca)", value=date.today(), key="tgl_cuaca_helper")
    with wcol2:
        if st.button("🌐 Tarik Otomatis dari API Cuaca (Open-Meteo)"):
            suhu_auto, kelembaban_auto = fetch_weather_data(tgl_cuaca)
            if suhu_auto is not None:
                st.session_state["suhu_auto"] = round(suhu_auto, 1)
                st.session_state["kelembaban_auto"] = round(kelembaban_auto, 1)
                st.success(f"Berhasil: {suhu_auto:.1f}°C, {kelembaban_auto:.1f}% RH")
            else:
                st.warning("Gagal mengambil data (cek koneksi internet plant). Silakan isi manual.")
    with wcol3:
        st.caption("Butuh koneksi internet. Jika plant hanya intranet, isi manual dari termometer/higrometer ruangan.")

    with st.form("weld_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            tanggal = st.date_input("Tanggal", value=date.today())
            batch_id = st.text_input("Nomor Batch/Joint", placeholder="B081")
            shift = st.selectbox("Shift", ["Shift 1", "Shift 2", "Shift 3"])
        with c2:
            operator = st.text_input("Operator Las (ID)", placeholder="OP-01")
            jenis_proses = st.selectbox("Jenis Proses Las", ["SMAW", "GTAW", "GMAW", "SAW"])
        with c3:
            welding_position = st.selectbox("Posisi Pengelasan", ["1G", "2G", "3G", "4G", "5G", "6G"])

        st.markdown("**Data Material & Joint**")
        m1, m2, m3 = st.columns(3)
        with m1:
            material_grade = st.selectbox("Grade Material", ["SS400", "A36", "A516 Gr.70", "A387 Gr.11", "SS304", "SS316"])
        with m2:
            heat_number = st.text_input("Heat Number (dari MTC/MTR)", placeholder="HT-2026-001")
        with m3:
            joint_type = st.selectbox("Tipe Sambungan", ["Butt Joint", "Fillet Joint", "Tee Joint"])

        st.markdown("**Parameter Mesin Las (baca dari digital display mesin)**")
        d1, d2, d3 = st.columns(3)
        with d1:
            arus = st.number_input("Arus Las (Ampere)", min_value=0.0, value=145.0, step=1.0)
            preheat = st.number_input("Preheat Temperature (°C)", min_value=0.0, value=120.0, step=1.0)
        with d2:
            tegangan = st.number_input("Tegangan Busur (Volt)", min_value=0.0, value=24.0, step=0.5)
            interpass = st.number_input("Interpass Temperature (°C)", min_value=0.0, value=180.0, step=1.0)
        with d3:
            travel_speed = st.number_input("Travel Speed (cm/menit)", min_value=0.0, value=12.0, step=0.5)
            gas_flow = st.number_input("Gas Flow Rate (L/menit)", min_value=0.0, value=15.0, step=0.5)

        st.markdown("**Data Lingkungan (isi manual, atau otomatis terisi dari tombol di atas)**")
        e1, e2 = st.columns(2)
        with e1:
            suhu_ambient = st.number_input("Suhu Ruangan (°C)", min_value=0.0,
                                            value=float(st.session_state.get("suhu_auto", 28.0)), step=0.1)
        with e2:
            kelembaban = st.number_input("Kelembaban (%RH)", min_value=0.0, max_value=100.0,
                                          value=float(st.session_state.get("kelembaban_auto", 75.0)), step=0.1)

        submitted = st.form_submit_button("💾 Simpan Data Proses Las", use_container_width=True)
        if submitted:
            if not batch_id or not operator:
                st.error("Nomor Batch dan Operator wajib diisi.")
            else:
                record = {
                    "tanggal": tanggal.isoformat(), "batch_id": batch_id, "shift": shift,
                    "operator": operator, "jenis_proses": jenis_proses,
                    "arus_A": arus, "tegangan_V": tegangan, "travel_speed_cm_min": travel_speed,
                    "preheat_C": preheat, "interpass_C": interpass, "gas_flow_L_min": gas_flow,
                    "material_grade": material_grade, "heat_number": heat_number,
                    "joint_type": joint_type, "welding_position": welding_position,
                    "suhu_ambient_C": suhu_ambient, "kelembaban_persen": kelembaban,
                }
                save_weld_process_record(record)
                st.success(f"Data proses las batch {batch_id} berhasil disimpan!")

    with st.expander("📄 Lihat Semua Data Proses Las"):
        df = load_weld_process_data()
        st.dataframe(df, use_container_width=True)
        st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode("utf-8"),
                            "weld_process_data.csv", "text/csv")

# ============================================================
# TAB 2: Ultrasonic Testing (UT)
# ============================================================
with tab2:
    st.subheader("Form Hasil Ultrasonic Testing (UT)")
    st.caption("Deteksi cacat internal/subsurface (incomplete fusion, slag inclusion, dll) — baca dari digital flaw detector")
    with st.form("ut_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            tgl_ut = st.date_input("Tanggal", value=date.today(), key="tgl_ut")
            batch_ut = st.text_input("Nomor Batch/Joint", placeholder="B081", key="batch_ut")
            operator_ut = st.text_input("Operator UT (ID)", placeholder="UT-01")
        with c2:
            probe_freq = st.selectbox("Frekuensi Probe (MHz)", [2.25, 4.0, 5.0])
            probe_angle = st.selectbox("Sudut Probe (derajat)", [0, 45, 60, 70])
            gain = st.number_input("Gain (dB)", min_value=0.0, value=40.0, step=0.5)
        with c3:
            thickness = st.number_input("Thickness Reading (mm)", min_value=0.0, value=10.0, step=0.01, format="%.3f")
            amplitude = st.slider("Indication Amplitude (% screen height)", 0, 100, 25)
            tgl_kalibrasi_ut = st.date_input("Tanggal Kalibrasi Alat UT Terakhir", value=date(2026, 6, 1))

        st.markdown("**Jika Ditemukan Indikasi Cacat**")
        d1, d2 = st.columns(2)
        with d1:
            defect_depth = st.number_input("Defect Depth (mm)", min_value=0.0, value=0.0, step=0.1)
        with d2:
            defect_length = st.number_input("Defect Length (mm)", min_value=0.0, value=0.0, step=0.1)

        ut_hasil = st.radio("Hasil Akhir UT (sesuai Acceptance Criteria ASME V)", ["Accept", "Reject"], horizontal=True)

        submitted_ut = st.form_submit_button("💾 Simpan Data UT", use_container_width=True)
        if submitted_ut:
            if not batch_ut or not operator_ut:
                st.error("Nomor Batch dan Operator UT wajib diisi.")
            else:
                record = {
                    "tanggal": tgl_ut.isoformat(), "batch_id": batch_ut, "operator_ut": operator_ut,
                    "probe_freq_MHz": probe_freq, "probe_angle_deg": probe_angle, "gain_dB": gain,
                    "thickness_reading_mm": thickness, "indication_amplitude_pct": amplitude,
                    "defect_depth_mm": defect_depth, "defect_length_mm": defect_length, "ut_hasil": ut_hasil,
                    "tanggal_kalibrasi_ut": tgl_kalibrasi_ut.isoformat(),
                }
                save_ut_record(record)
                st.success(f"Data UT batch {batch_ut} berhasil disimpan!")

    with st.expander("📄 Lihat Semua Data UT"):
        df_ut = load_ut_data()
        st.dataframe(df_ut, use_container_width=True)
        st.download_button("⬇️ Download CSV", df_ut.to_csv(index=False).encode("utf-8"),
                            "ut_inspection_data.csv", "text/csv")

# ============================================================
# TAB 3: Magnetic Particle Testing (MT)
# ============================================================
with tab3:
    st.subheader("Form Hasil Magnetic Particle Testing (MT)")
    st.caption("Deteksi cacat permukaan (crack, undercut) — baca dari alat yoke/prod & hasil visual indikasi partikel")
    with st.form("mt_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            tgl_mt = st.date_input("Tanggal", value=date.today(), key="tgl_mt")
            batch_mt = st.text_input("Nomor Batch/Joint", placeholder="B081", key="batch_mt")
            operator_mt = st.text_input("Operator MT (ID)", placeholder="MT-01")
        with c2:
            jenis_magnetisasi = st.selectbox("Jenis Magnetisasi", ["Yoke AC", "Yoke DC", "Prod", "Coil"])
            arus_magnetisasi = st.number_input("Arus Magnetisasi (Ampere)", min_value=0.0, value=110.0, step=1.0)
            arah_medan = st.selectbox("Arah Medan Magnet", ["Longitudinal", "Circular"])
        with c3:
            jenis_partikel = st.selectbox("Jenis Partikel", ["Wet Fluorescent", "Wet Visible", "Dry"])
            lifting_power = st.number_input("Lifting Power Test (kg)", min_value=0.0, value=5.0, step=0.1,
                                             help="Syarat minimum umumnya 4.5 kg untuk Yoke AC sesuai ASME V")
            tgl_kalibrasi_mt = st.date_input("Tanggal Kalibrasi/Verifikasi Alat MT Terakhir", value=date(2026, 6, 1))

        st.markdown("**Hasil Indikasi**")
        d1, d2 = st.columns(2)
        with d1:
            indikasi = st.selectbox("Indikasi Ditemukan", ["Tidak Ada", "Linear", "Rounded"])
        with d2:
            panjang_indikasi = st.number_input("Panjang Indikasi (mm)", min_value=0.0, value=0.0, step=0.5)

        mt_hasil = st.radio("Hasil Akhir MT (sesuai Acceptance Criteria)", ["Accept", "Reject"], horizontal=True)

        submitted_mt = st.form_submit_button("💾 Simpan Data MT", use_container_width=True)
        if submitted_mt:
            if not batch_mt or not operator_mt:
                st.error("Nomor Batch dan Operator MT wajib diisi.")
            else:
                record = {
                    "tanggal": tgl_mt.isoformat(), "batch_id": batch_mt, "operator_mt": operator_mt,
                    "jenis_magnetisasi": jenis_magnetisasi, "arus_magnetisasi_A": arus_magnetisasi,
                    "arah_medan": arah_medan, "jenis_partikel": jenis_partikel,
                    "lifting_power_kg": lifting_power, "indikasi_ditemukan": indikasi,
                    "panjang_indikasi_mm": panjang_indikasi, "mt_hasil": mt_hasil,
                    "tanggal_kalibrasi_mt": tgl_kalibrasi_mt.isoformat(),
                }
                save_mt_record(record)
                st.success(f"Data MT batch {batch_mt} berhasil disimpan!")

    with st.expander("📄 Lihat Semua Data MT"):
        df_mt = load_mt_data()
        st.dataframe(df_mt, use_container_width=True)
        st.download_button("⬇️ Download CSV", df_mt.to_csv(index=False).encode("utf-8"),
                            "mt_inspection_data.csv", "text/csv")

# ============================================================
# TAB 4: Liquid Penetrant Testing (PT)
# ============================================================
with tab4:
    st.subheader("Form Hasil Liquid Penetrant Testing (PT)")
    st.caption("Deteksi cacat permukaan TERBUKA (crack, porosity, lap) — terutama untuk material "
               "non-ferromagnetik (stainless steel austenitik, aluminium) yang tidak bisa dites MT. "
               "Acuan: ASME Section V Article 6, ASTM E165, ISO 3452.")
    with st.form("pt_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            tgl_pt = st.date_input("Tanggal", value=date.today(), key="tgl_pt")
            batch_pt = st.text_input("Nomor Batch/Joint", placeholder="B081", key="batch_pt")
            operator_pt = st.text_input("Operator PT (ID)", placeholder="PT-01")
        with c2:
            joint_type_pt = st.selectbox("Tipe Sambungan (Joint)", PT_JOINT_TYPE_OPTIONS, key="joint_pt")
            jenis_penetrant = st.selectbox("Jenis Penetrant", PT_PENETRANT_TYPE_OPTIONS)
            metode_pembersihan = st.selectbox("Metode Pembersihan Kelebihan Penetrant", PT_CLEANING_METHOD_OPTIONS)
        with c3:
            jenis_developer = st.selectbox("Jenis Developer", PT_DEVELOPER_TYPE_OPTIONS)
            nomor_batch_consumable = st.text_input("Nomor Batch/Lot Penetrant-Developer",
                                                     placeholder="LOT-2026-045",
                                                     help="Untuk traceability consumable sesuai sertifikat COC")
            tgl_kalibrasi_pt = st.date_input("Tanggal Kalibrasi/Verifikasi Alat Ukur Cahaya Terakhir",
                                              value=date(2026, 6, 1))

        st.markdown("**Parameter Proses (baca dari termometer/timer/light meter)**")
        d1, d2, d3 = st.columns(3)
        with d1:
            suhu_permukaan = st.number_input("Suhu Permukaan Benda Uji (°C)", min_value=-20.0,
                                              value=25.0, step=0.5,
                                              help="Standard technique ASME V: harus 5°C - 52°C (40°F - 125°F)")
        with d2:
            dwell_penetrant = st.number_input("Waktu Dwell Penetrant (menit)", min_value=0.0,
                                               value=15.0, step=1.0,
                                               help="Minimum umum 10 menit — cek tabel T-672 utk kasus spesifik")
        with d3:
            dwell_developer = st.number_input("Waktu Dwell Developer (menit)", min_value=0.0,
                                               value=10.0, step=1.0,
                                               help="Minimum umum 10 menit sebelum boleh diinspeksi")

        st.markdown("**Pencahayaan Inspeksi**")
        l1, l2 = st.columns(2)
        with l1:
            metode_pencahayaan = st.selectbox("Metode Pencahayaan", PT_LIGHTING_METHOD_OPTIONS)
        with l2:
            satuan_default = "µW/cm²" if jenis_penetrant == "Fluorescent" else "lux"
            intensitas_cahaya = st.number_input(
                f"Intensitas Cahaya Terukur ({satuan_default})", min_value=0.0,
                value=1200.0 if jenis_penetrant == "Fluorescent" else 1100.0, step=10.0,
                help="Fluorescent: UV-A min 1000 µW/cm² di permukaan. Visible Dye: cahaya putih min 1000 lux."
            )

        st.markdown("**Hasil Indikasi**")
        e1, e2, e3 = st.columns(3)
        with e1:
            indikasi_pt = st.selectbox("Indikasi Ditemukan", ["Tidak Ada", "Linear", "Rounded"], key="indikasi_pt")
        with e2:
            panjang_indikasi_pt = st.number_input("Panjang Indikasi (mm)", min_value=0.0, value=0.0,
                                                    step=0.5, key="panjang_pt")
        with e3:
            klasifikasi_indikasi = st.selectbox(
                "Klasifikasi Indikasi", ["Tidak Ada", "Non-Relevant", "Relevant"],
                help="Relevant = indikasi linear >1.5mm atau rounded >5mm (acuan umum ASME) — cek acceptance "
                     "criteria spesifik proyek/WPS untuk angka pastinya"
            )

        pt_hasil = st.radio("Hasil Akhir PT (sesuai Acceptance Criteria)", ["Accept", "Reject"], horizontal=True)

        submitted_pt = st.form_submit_button("💾 Simpan Data PT", use_container_width=True)
        if submitted_pt:
            if not batch_pt or not operator_pt:
                st.error("Nomor Batch dan Operator PT wajib diisi.")
            else:
                ok_dwell_p, ok_dwell_d, min_p, min_d = check_pt_dwell_time(dwell_penetrant, dwell_developer)
                ok_temp, min_temp, max_temp = check_pt_surface_temp(suhu_permukaan)
                ok_light, min_light, satuan_light = check_pt_light_intensity(jenis_penetrant, intensitas_cahaya)

                peringatan = []
                if not ok_dwell_p:
                    peringatan.append(f"Waktu dwell penetrant ({dwell_penetrant} menit) di bawah minimum acuan ({min_p} menit).")
                if not ok_dwell_d:
                    peringatan.append(f"Waktu dwell developer ({dwell_developer} menit) di bawah minimum acuan ({min_d} menit).")
                if not ok_temp:
                    peringatan.append(f"Suhu permukaan ({suhu_permukaan}°C) di luar rentang standard technique ({min_temp}-{max_temp}°C). Perlu kualifikasi teknik khusus.")
                if not ok_light:
                    peringatan.append(f"Intensitas cahaya ({intensitas_cahaya} {satuan_light}) di bawah minimum acuan ({min_light} {satuan_light}).")

                record = {
                    "tanggal": tgl_pt.isoformat(), "batch_id": batch_pt, "operator_pt": operator_pt,
                    "joint_type_pt": joint_type_pt, "jenis_penetrant": jenis_penetrant,
                    "metode_pembersihan": metode_pembersihan, "jenis_developer": jenis_developer,
                    "nomor_batch_consumable": nomor_batch_consumable, "suhu_permukaan_C": suhu_permukaan,
                    "waktu_dwell_penetrant_menit": dwell_penetrant, "waktu_dwell_developer_menit": dwell_developer,
                    "metode_pencahayaan": metode_pencahayaan, "intensitas_cahaya_terukur": intensitas_cahaya,
                    "satuan_intensitas": satuan_light, "indikasi_ditemukan": indikasi_pt,
                    "panjang_indikasi_mm": panjang_indikasi_pt, "klasifikasi_indikasi": klasifikasi_indikasi,
                    "pt_hasil": pt_hasil, "tanggal_kalibrasi_pt": tgl_kalibrasi_pt.isoformat(),
                }
                save_pt_record(record)
                if peringatan:
                    st.warning("Data PT batch " + batch_pt + " tersimpan, TAPI ada parameter di bawah "
                               "standar acuan (tetap dicatat apa adanya, tinjau ulang prosedur):\n\n- "
                               + "\n- ".join(peringatan))
                else:
                    st.success(f"Data PT batch {batch_pt} berhasil disimpan! Semua parameter sesuai acuan standar.")

    with st.expander("📄 Lihat Semua Data PT"):
        df_pt = load_pt_data()
        st.dataframe(df_pt, use_container_width=True)
        st.download_button("⬇️ Download CSV", df_pt.to_csv(index=False).encode("utf-8"),
                            "pt_inspection_data.csv", "text/csv")
