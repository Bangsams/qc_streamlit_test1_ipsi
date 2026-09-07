"""
config.py
Konfigurasi terpusat aplikasi: kredensial Google Sheets & Google Drive.
SEMUA disimpan di file `.env` (bukan di session Streamlit), sehingga:

  * Cukup diisi SEKALI lewat UI (halaman Laporan Foto -> tombol "Ubah").
  * Tetap tersimpan walau aplikasi dimatikan/restart, lokal maupun setelah
    di-deploy (selama file `.env` ikut ter-deploy / disk persist).
  * Bisa juga diisi langsung lewat environment variable saat deploy
    (contoh: AWS, Streamlit Cloud "Secrets", Docker env) — environment
    variable dari platform SELALU diprioritaskan di atas isi file `.env`,
    jadi aman untuk production.

Cara pakai singkat:
    from utils.config import get_config, set_config
    cfg = get_config()
    cfg["GOOGLE_SHEET_ID"]
    set_config({"GOOGLE_SHEET_ID": "xxxx", "GOOGLE_SERVICE_ACCOUNT_JSON": "..."})
"""

import os
from pathlib import Path

from dotenv import load_dotenv, set_key, dotenv_values

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Kunci konfigurasi yang dikelola aplikasi ini
CONFIG_KEYS = [
    "GOOGLE_SHEET_ID",      # ID Google Spreadsheet tujuan (dari URL sheet)
    "GOOGLE_SERVICE_ACCOUNT_JSON",  # Isi JSON service account (satu baris) ATAU path file .json
    "GOOGLE_DRIVE_FOLDER_ID",  # (Opsional) ID folder Drive tempat foto diupload
    # --- Jembatan upload Drive lewat Google Apps Script (lihat apps_script/Code.gs) ---
    # Dipakai karena Service Account TIDAK punya kuota storage Drive sendiri.
    "GOOGLE_APPS_SCRIPT_URL",     # URL Web App hasil deploy Apps Script (.../exec)
    "GOOGLE_APPS_SCRIPT_SECRET",  # Token rahasia, harus sama dengan SHARED_SECRET di Code.gs
]

# Pastikan file .env ada supaya bisa ditulisi (kalau belum ada, buat kosong)
if not ENV_PATH.exists():
    ENV_PATH.touch()

# Muat .env ke os.environ SEKALI saat modul pertama kali diimpor.
# override=False -> kalau environment variable sudah di-set oleh platform
# deploy (AWS/Streamlit Secrets/Docker), nilai itu yang menang, bukan .env.
load_dotenv(dotenv_path=ENV_PATH, override=False)


def get_config() -> dict:
    """Ambil konfigurasi aktif saat ini (gabungan: environment variable
    platform deploy + isi file .env), tanpa perlu isi ulang tiap sesi."""
    cfg = {}
    for key in CONFIG_KEYS:
        cfg[key] = os.environ.get(key, "")
    return cfg


def is_sheets_configured() -> bool:
    cfg = get_config()
    return bool(cfg.get("GOOGLE_SHEET_ID")) and bool(cfg.get("GOOGLE_SERVICE_ACCOUNT_JSON"))


def is_drive_bridge_configured() -> bool:
    """True kalau jembatan upload Drive lewat Apps Script sudah diisi
    (URL Web App + token rahasia). Ini jalur upload foto yang dipakai
    supaya tidak kena error 'Service Accounts do not have storage quota'."""
    cfg = get_config()
    return bool(cfg.get("GOOGLE_APPS_SCRIPT_URL")) and bool(cfg.get("GOOGLE_APPS_SCRIPT_SECRET"))


def set_config(values: dict):
    """Simpan konfigurasi baru ke file `.env` (persist permanen di disk) DAN
    langsung update os.environ supaya berlaku seketika tanpa restart app.

    Dipanggil hanya saat user menekan tombol "Simpan Perubahan" di UI —
    bukan otomatis tiap kali form dirender — supaya token tidak berulang
    kali ditulis ke disk.
    """
    for key, value in values.items():
        if key not in CONFIG_KEYS:
            continue
        if value is None:
            value = ""
        os.environ[key] = str(value)
        set_key(str(ENV_PATH), key, str(value))


def mask_secret(value: str, show: int = 4) -> str:
    """Tampilkan sebagian kecil saja dari token/secret untuk konfirmasi visual
    tanpa membocorkan seluruh nilai di layar."""
    if not value:
        return "(belum diisi)"
    if len(value) <= show:
        return "*" * len(value)
    return f"{'*' * (len(value) - show)}{value[-show:]}"
