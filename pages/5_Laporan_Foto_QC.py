"""
5_Laporan_Foto_QC.py — Ambil foto hasil QC langsung dari aplikasi, otomatis
tercatat ke Google Sheets LENGKAP DENGAN FOTONYA (tampil langsung sebagai
gambar di dalam sheet, ukuran seragam & tetap jelas), plus backup Excel lokal
dan file foto resolusi asli.

Menggantikan alur manual: operator foto -> catat manual di Excel/kirim manual.
Sekarang: operator foto SEKALI di aplikasi -> otomatis tercatat + foto langsung
terlihat di Google Sheets.

Konfigurasi (kredensial Google Sheets & Drive) HANYA perlu diisi SEKALI.
Tersimpan permanen ke file `.env` (lihat utils/config.py), jadi tetap ada
walau aplikasi dimatikan/redeploy. Untuk mengubahnya lagi, gunakan tombol
"✏️ Ubah Konfigurasi" di panel Pengaturan.
"""

import streamlit as st
import sys, os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.data_handler import save_qc_report, save_photo_locally, load_qc_report_log
from utils.qc_utils import check_mt_lifting_power, MT_MIN_LIFTING_POWER_KG
from utils.config import get_config, set_config, is_sheets_configured, is_drive_bridge_configured
from utils import sheets_handler

st.set_page_config(page_title="Laporan Foto QC - QC App", page_icon="📸", layout="wide")
st.title("📸 Laporan Hasil QC — Foto Otomatis Tercatat di Google Sheets")
st.caption("Satu kali foto & isi form di sini, foto + data otomatis tersimpan dan tampil langsung di Google Sheets")

cfg = get_config()

# ============================================================
# Konfigurasi (SEKALI ISI, tersimpan permanen di .env)
# ============================================================
with st.expander("⚙️ Pengaturan Google Sheets & Drive — cukup diisi SEKALI", expanded=not is_sheets_configured()):
    st.markdown("""
    Data hasil QC (baris teks) disimpan otomatis ke **Google Sheets** memakai *Service Account*.
    Foto-nya **TIDAK** diupload lewat Service Account (Service Account tidak punya kuota
    penyimpanan Drive sendiri), melainkan lewat jembatan **Google Apps Script** yang jalan atas
    nama akun Google pribadi Anda. Lihat `apps_script/Code.gs` untuk kode & instruksi deploy
    lengkap, dan `README.md` untuk ringkasannya.
    """)

    if not is_drive_bridge_configured():
        st.warning(
            "⚠️ Jembatan upload foto ke Drive (Apps Script) belum dikonfigurasi. Foto akan gagal "
            "diupload dengan error *'Service Accounts do not have storage quota'* sampai bagian "
            "ini diisi. Deploy `apps_script/Code.gs` terlebih dahulu, lalu isi URL & token di bawah."
        )

    if is_sheets_configured() and is_drive_bridge_configured() and not st.session_state.get("edit_sheets_mode", False):
        from utils.config import mask_secret
        st.success(
            f"✅ Sudah dikonfigurasi.\n\n"
            f"- Google Sheet ID: `{cfg.get('GOOGLE_SHEET_ID','')}`\n"
            f"- Apps Script Web App URL: `{cfg.get('GOOGLE_APPS_SCRIPT_URL','')}`\n"
            f"- Token rahasia Apps Script: `{mask_secret(cfg.get('GOOGLE_APPS_SCRIPT_SECRET',''))}`\n"
            f"- Folder Drive foto: `{cfg.get('GOOGLE_DRIVE_FOLDER_ID','') or '(default - root Drive akun Apps Script)'}`"
        )
        if st.button("✏️ Ubah Konfigurasi"):
            st.session_state["edit_sheets_mode"] = True
            st.rerun()
        if st.button("🧪 Tes Upload Foto ke Google Drive"):
            with st.spinner("Mengupload foto tes ke Google Drive..."):
                ok_test, msg_test = sheets_handler.test_drive_upload()
            if ok_test:
                st.success(msg_test)
            else:
                st.error(f"Gagal: {msg_test}")

        col_test1, col_test2 = st.columns(2)
        with col_test1:
            if st.button("🧪 Tes Koneksi Google Sheets", use_container_width=True):
                with st.spinner("Menghubungi Google Sheets..."):
                    ok_sheet, msg_sheet = sheets_handler.test_sheets_connection()
                if ok_sheet:
                    st.success(msg_sheet)
                else:
                    st.error(f"Gagal: {msg_sheet}")
        with col_test2:
            if st.button("🔄 Perbarui Struktur Kolom Google Sheets", use_container_width=True):
                with st.spinner("Memperbarui struktur kolom..."):
                    ok_struct, msg_struct = sheets_handler.force_update_sheet_structure()
                if ok_struct:
                    st.success(msg_struct)
                else:
                    st.error(f"Gagal: {msg_struct}")
    else:
        with st.form("form_sheets_config"):
            st.markdown("**Google Sheets (data QC)**")
            new_sheet_id = st.text_input(
                "Google Sheet ID",
                value=cfg.get("GOOGLE_SHEET_ID", ""),
                help="Ambil dari URL spreadsheet: docs.google.com/spreadsheets/d/<SHEET_ID>/edit"
            )
            new_sa_json = st.text_area(
                "Isi file JSON Service Account (paste seluruh isi file .json di sini)",
                value=cfg.get("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
                height=120,
                help="Dari Google Cloud Console -> Credentials -> Service Account -> Keys -> Add Key (JSON). "
                     "Cukup aktifkan 'Google Sheets API' untuk service account ini."
            )
            st.markdown("**Jembatan upload foto ke Google Drive (Apps Script)**")
            new_script_url = st.text_input(
                "Web App URL Apps Script",
                value=cfg.get("GOOGLE_APPS_SCRIPT_URL", ""),
                placeholder="https://script.google.com/macros/s/XXXXXXXX/exec",
                help="Didapat setelah deploy apps_script/Code.gs sebagai Web App "
                     "(Execute as: Me, Who has access: Anyone). Lihat komentar di awal file Code.gs."
            )
            new_script_secret = st.text_input(
                "Token rahasia Apps Script",
                value=cfg.get("GOOGLE_APPS_SCRIPT_SECRET", ""),
                type="password",
                help="Harus SAMA PERSIS dengan nilai variabel SHARED_SECRET di dalam apps_script/Code.gs."
            )
            new_drive_folder = st.text_input(
                "ID Folder Google Drive untuk foto (opsional)",
                value=cfg.get("GOOGLE_DRIVE_FOLDER_ID", ""),
                help="ID folder di Drive akun PRIBADI Anda (yang dipakai deploy Apps Script), dari URL: "
                     "drive.google.com/drive/folders/<FOLDER_ID>. Kosongkan kalau tidak masalah foto "
                     "masuk ke root My Drive akun tsb."
            )
            save_sheets = st.form_submit_button("💾 Simpan Konfigurasi", use_container_width=True)
        if save_sheets:
            set_config({
                "GOOGLE_SHEET_ID": new_sheet_id.strip(),
                "GOOGLE_SERVICE_ACCOUNT_JSON": new_sa_json.strip(),
                "GOOGLE_APPS_SCRIPT_URL": new_script_url.strip(),
                "GOOGLE_APPS_SCRIPT_SECRET": new_script_secret.strip(),
                "GOOGLE_DRIVE_FOLDER_ID": new_drive_folder.strip(),
            })
            st.session_state["edit_sheets_mode"] = False
            st.success("Konfigurasi tersimpan permanen. Tidak perlu diisi ulang lagi.")
            st.rerun()
        if is_sheets_configured() and st.button("❌ Batal Ubah"):
            st.session_state["edit_sheets_mode"] = False
            st.rerun()

st.markdown("---")

# ============================================================
# Form Utama: Foto + Data QC
# ============================================================
col_foto, col_form = st.columns([1, 1.3])

with col_foto:
    st.subheader("1️⃣ Ambil / Upload Foto")
    sumber_foto = st.radio(
        "Sumber foto",
        ["📷 Ambil Foto Baru (Kamera)", "🖼️ Upload dari Galeri"],
        horizontal=True,
        key="sumber_foto_radio",
    )

    foto = None
    if sumber_foto == "📷 Ambil Foto Baru (Kamera)":
        foto = st.camera_input("Ambil foto penandaan hasil QC (seperti contoh: UT.Acc, MT.Repair, dll)")
    else:
        foto = st.file_uploader(
            "Pilih foto dari galeri/penyimpanan HP atau komputer",
            type=["jpg", "jpeg", "png"],
        )

    if foto is not None:
        st.image(foto, caption="Preview foto yang akan disimpan", use_container_width=True)

with col_form:
    st.subheader("2️⃣ Isi Data Hasil QC")
    with st.form("qc_report_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            nomor_seri = st.text_input("Nomor Seri Barang / Batch", placeholder="B081")
            jenis_ndt = st.selectbox("Jenis NDT", ["UT", "MT"])
            wilayah_face = st.selectbox("Wilayah Pemeriksaan (Face)", ["Face A", "Face B", "Face C"])
        with c2:
            posisi_x = st.number_input("Posisi X-Line (mm dari titik referensi)", min_value=0.0, value=0.0, step=1.0,
                                        help="Sesuai konvensi penandaan: jarak sepanjang sumbu las, mis. L=6060mm")
            operator_qc = st.text_input("Nama/ID Operator QC", placeholder="QC-13")
            hasil = st.selectbox("Hasil", ["Accept", "Perlu Gerinda (Repair)", "Reject"])

        if jenis_ndt == "MT":
            lifting_check = st.number_input("Lifting Power Yoke Saat Ini (kg)", min_value=0.0, value=5.0, step=0.1)
            ok, min_req = check_mt_lifting_power(lifting_check)
            if not ok:
                st.error(f"⚠️ Lifting power {lifting_check} kg di BAWAH syarat minimum AWS D1.1 ({min_req} kg)! "
                         "Verifikasi ulang yoke sebelum melanjutkan inspeksi.")

        catatan = st.text_area("Catatan Tambahan", placeholder="Contoh: indikasi linear 6mm, sudah digerinda halus")

        submitted = st.form_submit_button("💾 Simpan Laporan (Foto + Data)", use_container_width=True)

    if submitted:
        if foto is None:
            st.error("Foto belum diambil/diupload.")
        elif not nomor_seri or not operator_qc:
            st.error("Nomor Seri Barang dan Operator QC wajib diisi.")
        else:
            now = datetime.now()
            image_bytes = foto.getvalue()
            foto_filename = save_photo_locally(image_bytes, nomor_seri)

            record = {
                "tanggal": now.date().isoformat(), "waktu": now.strftime("%H:%M:%S"),
                "nomor_seri_barang": nomor_seri, "jenis_ndt": jenis_ndt,
                "wilayah_pemeriksaan_face": wilayah_face, "posisi_x_line_mm": posisi_x,
                "hasil": hasil, "perlu_gerinda": "Ya" if "Gerinda" in hasil else "Tidak",
                "operator_qc": operator_qc, "catatan": catatan,
                "foto_path": foto_filename,
            }
            tempat_simpan, foto_error = save_qc_report(record, image_bytes=image_bytes)
            st.success(f"✅ Laporan tersimpan ke: {tempat_simpan}.")
            if "TANPA foto" in tempat_simpan or foto_error:
                st.error(f"⚠️ Foto GAGAL diupload ke Google Drive, sehingga tidak tampil di Google Sheets "
                         f"(data lain tetap tersimpan). Penyebab: {foto_error}")
                st.caption("Coba tombol '🧪 Tes Upload Foto ke Google Drive' di panel Pengaturan di atas "
                           "untuk diagnosa lebih lanjut, atau cek langkah-langkah setup di README.md.")
            if "Google Sheets" not in tempat_simpan:
                sheets_err = sheets_handler.get_last_sheets_error()
                st.warning(f"Google Sheets belum dikonfigurasi/gagal diakses — data untuk sementara "
                           f"hanya tersimpan di Excel lokal. Penyebab: {sheets_err or 'tidak diketahui'}")
                st.caption("Coba tombol '🧪 Tes Koneksi Google Sheets' di panel Pengaturan di atas "
                           "untuk diagnosa lebih lanjut.")

st.markdown("---")
st.subheader("📋 Riwayat Laporan QC")
log_df = load_qc_report_log()
if len(log_df) > 0:
    st.dataframe(log_df, use_container_width=True)
    excel_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hasil_qc_log.xlsx")
    if os.path.exists(excel_path):
        st.download_button("⬇️ Download Backup Excel", open(excel_path, "rb").read(),
                            "hasil_qc_log.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if is_sheets_configured():
        sheet_url = f"https://docs.google.com/spreadsheets/d/{cfg.get('GOOGLE_SHEET_ID','')}/edit"
        st.markdown(f"🔗 [Buka Google Sheets untuk lihat foto langsung di dalam tabel]({sheet_url})")
else:
    st.info("Belum ada laporan. Ambil foto dan isi form di atas untuk mulai mencatat.")

st.markdown("---")
st.info("""
**Kenapa data disimpan ke Google Sheets, bukan cuma Excel lokal?**
Excel lokal hilang setiap kali aplikasi di-redeploy/server direstart (disk sementara).
Google Sheets tersimpan di cloud Google secara permanen dan bisa diakses/dibagikan kapan saja,
tanpa perlu download file.

**Kenapa fotonya tampil langsung di dalam sheet, bukan cuma nama file?**
Foto diupload otomatis ke Google Drive (pakai kredensial yang sama dengan Google Sheets), lalu
ditampilkan langsung di dalam cell memakai formula `IMAGE()` dengan ukuran yang DISERAGAMKAN
(semua foto berukuran sama persis) supaya tabelnya rapi, tapi kualitas gambarnya tetap dijaga
tinggi resolusinya supaya jelas/tidak pecah. File foto resolusi ASLI tetap disimpan sebagai
backup lokal di folder `data/photos/`.
""")
