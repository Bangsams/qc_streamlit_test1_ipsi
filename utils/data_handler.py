"""
data_handler.py
Modul untuk membaca dan menyimpan data QC (parameter las & hasil inspeksi NDT)
ke file CSV lokal, berfungsi sebagai "database" sederhana untuk aplikasi.

Update: fokus NDT disesuaikan menjadi Ultrasonic Testing (UT) dan
Magnetic Particle Testing (MT), plus field tambahan (material, joint,
kalibrasi alat, dan data lingkungan) untuk meningkatkan akurasi model ML.
"""

import os
import uuid
import pandas as pd
from datetime import date

from . import sheets_handler
from .config import get_config

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
WELD_PROCESS_PATH = os.path.join(DATA_DIR, "weld_process_data.csv")
UT_DATA_PATH = os.path.join(DATA_DIR, "ut_inspection_data.csv")
MT_DATA_PATH = os.path.join(DATA_DIR, "mt_inspection_data.csv")

# Parameter proses las + material + joint + lingkungan (root cause / fitur prediksi)
WELD_PROCESS_COLUMNS = [
    "tanggal", "batch_id", "shift", "operator", "jenis_proses",
    "arus_A", "tegangan_V", "travel_speed_cm_min", "preheat_C", "interpass_C", "gas_flow_L_min",
    "material_grade", "heat_number", "joint_type", "welding_position",
    "suhu_ambient_C", "kelembaban_persen",
]

# Data hasil Ultrasonic Testing (deteksi cacat internal/subsurface)
UT_COLUMNS = [
    "tanggal", "batch_id", "operator_ut", "probe_freq_MHz", "probe_angle_deg",
    "gain_dB", "thickness_reading_mm", "indication_amplitude_pct",
    "defect_depth_mm", "defect_length_mm", "ut_hasil", "tanggal_kalibrasi_ut",
]

# Data hasil Magnetic Particle Testing (deteksi cacat permukaan)
MT_COLUMNS = [
    "tanggal", "batch_id", "operator_mt", "jenis_magnetisasi", "arus_magnetisasi_A",
    "arah_medan", "jenis_partikel", "lifting_power_kg",
    "indikasi_ditemukan", "panjang_indikasi_mm", "mt_hasil", "tanggal_kalibrasi_mt",
]


def _ensure_file(path: str, columns: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(path):
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def load_weld_process_data() -> pd.DataFrame:
    _ensure_file(WELD_PROCESS_PATH, WELD_PROCESS_COLUMNS)
    return pd.read_csv(WELD_PROCESS_PATH)


def save_weld_process_record(record: dict):
    df = load_weld_process_data()
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    df.to_csv(WELD_PROCESS_PATH, index=False)
    return df


def load_ut_data() -> pd.DataFrame:
    _ensure_file(UT_DATA_PATH, UT_COLUMNS)
    return pd.read_csv(UT_DATA_PATH)


def save_ut_record(record: dict):
    df = load_ut_data()
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    df.to_csv(UT_DATA_PATH, index=False)
    return df


def load_mt_data() -> pd.DataFrame:
    _ensure_file(MT_DATA_PATH, MT_COLUMNS)
    return pd.read_csv(MT_DATA_PATH)


def save_mt_record(record: dict):
    df = load_mt_data()
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    df.to_csv(MT_DATA_PATH, index=False)
    return df


def load_combined_data() -> pd.DataFrame:
    """Gabungkan data proses las + hasil UT + hasil MT per batch_id.
    Hasil akhir (final_hasil) = Reject jika UT ATAU MT reject.
    Turunan tambahan: umur kalibrasi alat (hari) sejak tanggal kalibrasi terakhir."""
    weld = load_weld_process_data()
    ut = load_ut_data()[[
        "batch_id", "ut_hasil", "indication_amplitude_pct", "defect_depth_mm",
        "defect_length_mm", "tanggal_kalibrasi_ut",
    ]]
    mt = load_mt_data()[[
        "batch_id", "mt_hasil", "arus_magnetisasi_A", "panjang_indikasi_mm", "tanggal_kalibrasi_mt",
    ]]

    df = weld.merge(ut, on="batch_id", how="inner").merge(mt, on="batch_id", how="inner")
    df["final_hasil"] = df.apply(
        lambda r: "Reject" if (r["ut_hasil"] == "Reject" or r["mt_hasil"] == "Reject") else "Accept",
        axis=1,
    )

    # Hitung umur kalibrasi alat (hari) pada tanggal inspeksi — proxy risiko drift alat
    try:
        tgl = pd.to_datetime(df["tanggal"])
        df["umur_kalibrasi_ut_hari"] = (tgl - pd.to_datetime(df["tanggal_kalibrasi_ut"])).dt.days
        df["umur_kalibrasi_mt_hari"] = (tgl - pd.to_datetime(df["tanggal_kalibrasi_mt"])).dt.days
    except Exception:
        df["umur_kalibrasi_ut_hari"] = 0
        df["umur_kalibrasi_mt_hari"] = 0

    return df


# ---------------------------------------------------------------------------
# Integrasi data cuaca (opsional) — Open-Meteo Archive API, gratis tanpa API key
# Lokasi default: Bojonegara, Serang, Banten (area PT IHI Power Service Indonesia)
# ---------------------------------------------------------------------------
DEFAULT_LAT = -5.99
DEFAULT_LON = 106.11


def fetch_weather_data(tanggal: date, lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON):
    """Tarik suhu rata-rata (C) & kelembaban rata-rata (%) dari Open-Meteo Archive API
    untuk tanggal tertentu. Mengembalikan (suhu, kelembaban) atau (None, None) jika gagal
    (misal tidak ada koneksi internet di jaringan intranet plant)."""
    try:
        import requests
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat, "longitude": lon,
            "start_date": tanggal.isoformat(), "end_date": tanggal.isoformat(),
            "daily": "temperature_2m_mean,relative_humidity_2m_mean",
            "timezone": "Asia/Jakarta",
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        suhu = data["daily"]["temperature_2m_mean"][0]
        kelembaban = data["daily"]["relative_humidity_2m_mean"][0]
        return suhu, kelembaban
    except Exception:
        return None, None



# ---------------------------------------------------------------------------
# Laporan hasil QC: foto + data tersimpan otomatis ke Google Sheets (foto
# ditampilkan langsung sebagai gambar di sheet, seragam & jelas — lihat
# utils/sheets_handler.py) dengan backup Excel lokal + file foto asli.
# ---------------------------------------------------------------------------
QC_REPORT_LOG_PATH = os.path.join(DATA_DIR, "hasil_qc_log.xlsx")
QC_REPORT_COLUMNS = [
    "tanggal", "waktu", "nomor_seri_barang", "jenis_ndt", "wilayah_pemeriksaan_face",
    "posisi_x_line_mm", "hasil", "perlu_gerinda", "operator_qc", "catatan",
    "foto_path", "foto_url",
]


def save_photo_locally(image_bytes: bytes, nomor_seri: str, ext: str = "jpg") -> str:
    """Simpan file foto ASLI (resolusi penuh) ke data/photos/ sebagai backup
    lokal. Mengembalikan nama file yang dibuat, dicatat ke kolom 'foto_path'
    pada log. Foto yang tampil di Google Sheets adalah versi yang sudah
    distandarkan (lihat sheets_handler.standardize_photo_for_sheets) dan
    diupload terpisah ke Google Drive — file lokal ini tetap resolusi asli."""
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    safe_nomor = "".join(c for c in str(nomor_seri) if c.isalnum() or c in ("-", "_")) or "foto"
    filename = f"{safe_nomor}_{datetime_str()}_{uuid.uuid4().hex[:6]}.{ext}"
    path = os.path.join(PHOTOS_DIR, filename)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return filename


def datetime_str() -> str:
    return now_wib().strftime("%Y%m%d_%H%M%S")


def now_wib():
    """Waktu saat ini di zona WIB (Asia/Jakarta), BUKAN waktu server.

    PENTING: server Streamlit Cloud berjalan di zona UTC. Kalau pakai
    `datetime.now()` polos, timestamp yang tercatat akan MELESET 7 JAM dari
    waktu Indonesia (WIB = UTC+7) — itu penyebab kolom 'tanggal'/'waktu' di
    laporan QC selama ini salah. Gunakan fungsi ini di semua tempat yang
    mencatat waktu kejadian (laporan QC, nama file foto, dst), JANGAN pakai
    `datetime.now()` langsung."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Jakarta"))


def save_qc_report_to_excel(record: dict):
    """Simpan satu baris hasil QC ke file Excel log (dibuat otomatis jika belum ada).
    Ini dipakai sebagai FALLBACK/backup lokal — penyimpanan utama ada di Google
    Sheets (lihat save_qc_report) supaya data tidak hilang saat app di-redeploy."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(QC_REPORT_LOG_PATH):
        df_init = pd.DataFrame(columns=QC_REPORT_COLUMNS)
        df_init.to_excel(QC_REPORT_LOG_PATH, index=False)

    df = pd.read_excel(QC_REPORT_LOG_PATH)
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    df.to_excel(QC_REPORT_LOG_PATH, index=False)
    return df


def save_qc_report(record: dict, image_bytes: bytes = None) -> tuple:
    """Simpan satu baris hasil QC ke penyimpanan utama.

    Kalau image_bytes diberikan, foto diupload ke Google Drive lalu
    ditampilkan langsung sebagai gambar seragam di kolom 'foto' pada Google
    Sheets (lihat sheets_handler.append_qc_report). Prioritas: Google Sheets
    (kalau sudah dikonfigurasi) -> selalu tulis juga ke Excel lokal sebagai
    backup (dengan link foto Drive, bukan gambarnya, karena Excel tidak
    mendukung formula IMAGE() Google Sheets).

    Mengembalikan (keterangan tempat tersimpan: str, pesan_error_foto: str atau None)
    supaya UI bisa menampilkan alasan asli kalau upload foto ke Drive gagal
    (bukan disembunyikan)."""
    ok_sheets = False
    foto_url = None
    foto_error = None
    if sheets_handler.is_available():
        ok_sheets, foto_url, foto_error = sheets_handler.append_qc_report(record, image_bytes=image_bytes)

    record_for_excel = dict(record)
    record_for_excel["foto_url"] = foto_url or ""
    save_qc_report_to_excel(record_for_excel)

    if ok_sheets:
        keterangan = "Google Sheets (dengan foto)" if foto_url else "Google Sheets (TANPA foto, lihat keterangan error)"
        keterangan += " + Excel lokal (backup)"
    else:
        keterangan = "Excel lokal saja (Google Sheets belum dikonfigurasi/gagal diakses)"

    return keterangan, foto_error


def load_qc_report_log() -> pd.DataFrame:
    """Baca log hasil QC. Utamakan Google Sheets kalau tersedia & berisi data,
    kalau tidak fallback ke Excel lokal."""
    if sheets_handler.is_available():
        df = sheets_handler.load_qc_report_log()
        if len(df) > 0:
            return df
    if not os.path.exists(QC_REPORT_LOG_PATH):
        return pd.DataFrame(columns=QC_REPORT_COLUMNS)
    return pd.read_excel(QC_REPORT_LOG_PATH)
