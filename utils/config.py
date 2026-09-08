"""
config.py
Konfigurasi terpusat aplikasi: kredensial Google Sheets & Google Drive.

Dua cara mengisi kredensial Service Account (keduanya didukung):

  A) CARA BARU (DIREKOMENDASIKAN, terutama untuk Streamlit Cloud "Secrets"):
     Isi tiap field JSON sebagai key TERPISAH (GOOGLE_SA_PRIVATE_KEY, dst).
     Tidak perlu menempel seluruh isi file .json sekaligus, sehingga tidak
     ada risiko salah escape backslash (dua-karakter backslash+n) yang bikin error:
         "Unable to load PEM file ... Invalid symbol 92, offset 0"
     (simbol 92 = kode ASCII karakter backslash, salah tempat/dobel escape).
     Lihat GOOGLE_SA_* di CONFIG_KEYS di bawah, dan secrets.toml.example.

  B) CARA LAMA: satu blob GOOGLE_SERVICE_ACCOUNT_JSON berisi seluruh isi
     file .json. Tetap didukung untuk kompatibilitas, dan sekarang otomatis
     "diperbaiki" (`_fix_private_key_newlines`) kalau private_key-nya kena
     masalah escape ganda seperti di atas.

SEMUA nilai config dibaca dari (urutan prioritas, yang duluan ketemu dipakai):
  1. Streamlit Secrets (`st.secrets`) — otomatis tersedia di Streamlit Cloud.
  2. Environment variable (AWS/Docker/dsb).
  3. File `.env` lokal (untuk development di komputer sendiri).

Cara pakai singkat:
    from utils.config import get_config, set_config, get_service_account_info
    cfg = get_config()
    cfg["GOOGLE_SHEET_ID"]
    info = get_service_account_info()  # dict siap pakai untuk Credentials
"""

import os
from pathlib import Path

from dotenv import load_dotenv, set_key, dotenv_values

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Kunci konfigurasi flat (non-kredensial) yang dikelola aplikasi ini
CONFIG_KEYS = [
    "GOOGLE_SHEET_ID",      # ID Google Spreadsheet tujuan (dari URL sheet)
    "GOOGLE_SERVICE_ACCOUNT_JSON",  # CARA LAMA: isi JSON service account (satu blob) ATAU path file .json
    "GOOGLE_DRIVE_FOLDER_ID",  # (Opsional) ID folder Drive tempat foto diupload
    # --- Jembatan upload Drive lewat Google Apps Script (lihat apps_script/Code.gs) ---
    # Dipakai karena Service Account TIDAK punya kuota storage Drive sendiri.
    "GOOGLE_APPS_SCRIPT_URL",     # URL Web App hasil deploy Apps Script (.../exec)
    "GOOGLE_APPS_SCRIPT_SECRET",  # Token rahasia, harus sama dengan SHARED_SECRET di Code.gs
]

# CARA BARU (direkomendasikan): field Service Account terpisah satu-satu,
# supaya tidak perlu tempel JSON mentah & tidak ada risiko salah escape.
SERVICE_ACCOUNT_FIELD_KEYS = [
    "GOOGLE_SA_TYPE",                        # selalu "service_account"
    "GOOGLE_SA_PROJECT_ID",
    "GOOGLE_SA_PRIVATE_KEY_ID",
    "GOOGLE_SA_PRIVATE_KEY",                 # isi PERSIS dari file .json, termasuk "\n"-nya
    "GOOGLE_SA_CLIENT_EMAIL",
    "GOOGLE_SA_CLIENT_ID",
    "GOOGLE_SA_CLIENT_X509_CERT_URL",
]

CONFIG_KEYS = CONFIG_KEYS + SERVICE_ACCOUNT_FIELD_KEYS

# Pastikan file .env ada supaya bisa ditulisi (kalau belum ada, buat kosong)
if not ENV_PATH.exists():
    ENV_PATH.touch()

# Muat .env ke os.environ SEKALI saat modul pertama kali diimpor.
# override=False -> kalau environment variable sudah di-set oleh platform
# deploy (AWS/Streamlit Secrets/Docker), nilai itu yang menang, bukan .env.
load_dotenv(dotenv_path=ENV_PATH, override=False)


def _get_st_secrets():
    """Ambil st.secrets kalau aplikasi jalan di dalam Streamlit & secrets
    sudah dikonfigurasi. Mengembalikan None kalau tidak tersedia (mis. saat
    dites di luar konteks Streamlit, atau belum ada secrets sama sekali) —
    supaya tidak melempar error dan tetap fallback ke .env/environment."""
    try:
        import streamlit as st
        # Mengakses st.secrets bisa melempar error kalau file secrets.toml
        # sama sekali tidak ada (bukan cuma kosong) — pada beberapa environment.
        try:
            return st.secrets
        except Exception:
            return None
    except ImportError:
        return None


def get_config() -> dict:
    """Ambil konfigurasi aktif saat ini (gabungan: Streamlit Secrets +
    environment variable platform deploy + isi file .env), tanpa perlu isi
    ulang tiap sesi. Streamlit Secrets diprioritaskan kalau key-nya ada di
    sana (nilai top-level/flat, BUKAN table/section)."""
    secrets = _get_st_secrets()
    cfg = {}
    for key in CONFIG_KEYS:
        value = ""
        if secrets is not None and key in secrets:
            value = secrets[key]
        else:
            value = os.environ.get(key, "")
        cfg[key] = value
    return cfg


def _fix_private_key_newlines(private_key: str) -> str:
    """Perbaiki otomatis kasus paling umum: private_key hasil copy-paste ke
    Streamlit Secrets / .env kena ESCAPE GANDA, sehingga karakter newline
    "\\n" (2 karakter: backslash + n) yang seharusnya jadi baris baru malah
    tetap literal 2 karakter tsb (atau lebih parah, jadi "\\\\n"). Ini
    penyebab persis error:
        "Unable to load PEM file ... Invalid symbol 92, offset 0"
    (92 = kode ASCII karakter backslash).

    Fungsi ini AMAN dipanggil pada private_key yang sudah benar sekalipun
    (sudah punya newline asli) — tidak akan mengubah apa-apa kalau memang
    sudah benar, karena py hanya mengganti pola yang tersisa."""
    if not private_key:
        return private_key
    # Kasus escape berlebih (3-4 backslash beruntun sebelum n) -> rapikan dulu
    while "\\\\n" in private_key:
        private_key = private_key.replace("\\\\n", "\\n")
    # Kasus normal yang masih literal backslash+n -> ubah jadi newline asli
    if "\n" not in private_key and "\\n" in private_key:
        private_key = private_key.replace("\\n", "\n")
    return private_key


def get_service_account_info():
    """Mengembalikan (info: dict atau None, error: str atau None) — dict
    kredensial Service Account yang siap dipakai langsung ke
    `Credentials.from_service_account_info(info)`, TANPA perlu json.loads
    manual di tempat lain (menghindari duplikasi & inkonsistensi perbaikan
    backslash).

    Urutan prioritas sumber:
      1. Streamlit Secrets, table `[gcp_service_account]` (CARA BARU,
         paling aman: private_key ditulis dengan baris baru ASLI langsung
         di secrets.toml, jadi TIDAK ADA proses escape/unescape sama sekali).
      2. Field terpisah GOOGLE_SA_* (CARA BARU, flat key per field).
      3. Blob lama GOOGLE_SERVICE_ACCOUNT_JSON (CARA LAMA), dengan
         perbaikan otomatis newline via _fix_private_key_newlines().
    """
    import json

    secrets = _get_st_secrets()

    # --- Sumber 1: table [gcp_service_account] di Streamlit Secrets ---
    if secrets is not None and "gcp_service_account" in secrets:
        try:
            info = dict(secrets["gcp_service_account"])
            if not info.get("private_key"):
                return None, "Table [gcp_service_account] di Secrets ada, tapi field 'private_key' kosong."
            info["private_key"] = _fix_private_key_newlines(info["private_key"])
            return info, None
        except Exception as e:
            return None, f"Gagal membaca table [gcp_service_account] di Secrets: {e}"

    # --- Sumber 2: field terpisah GOOGLE_SA_* ---
    cfg = get_config()
    if cfg.get("GOOGLE_SA_PRIVATE_KEY") and cfg.get("GOOGLE_SA_CLIENT_EMAIL"):
        info = {
            "type": cfg.get("GOOGLE_SA_TYPE") or "service_account",
            "project_id": cfg.get("GOOGLE_SA_PROJECT_ID", ""),
            "private_key_id": cfg.get("GOOGLE_SA_PRIVATE_KEY_ID", ""),
            "private_key": _fix_private_key_newlines(cfg.get("GOOGLE_SA_PRIVATE_KEY", "")),
            "client_email": cfg.get("GOOGLE_SA_CLIENT_EMAIL", ""),
            "client_id": cfg.get("GOOGLE_SA_CLIENT_ID", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": cfg.get("GOOGLE_SA_CLIENT_X509_CERT_URL", ""),
            "universe_domain": "googleapis.com",
        }
        return info, None

    # --- Sumber 3 (fallback lama): satu blob GOOGLE_SERVICE_ACCOUNT_JSON ---
    sa_raw = cfg.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_raw:
        return None, (
            "Kredensial Service Account belum diisi. Isi salah satu: table "
            "[gcp_service_account] di Secrets (direkomendasikan), field "
            "GOOGLE_SA_* satu-satu, atau GOOGLE_SERVICE_ACCOUNT_JSON (cara lama)."
        )
    try:
        if os.path.exists(sa_raw):
            with open(sa_raw, "r", encoding="utf-8") as f:
                info = json.load(f)
        else:
            info = json.loads(sa_raw)
        info["private_key"] = _fix_private_key_newlines(info.get("private_key", ""))
        return info, None
    except json.JSONDecodeError as e:
        return None, f"Isi GOOGLE_SERVICE_ACCOUNT_JSON bukan JSON yang valid: {e}"
    except Exception as e:
        return None, f"Gagal membaca GOOGLE_SERVICE_ACCOUNT_JSON: {e}"


def is_sheets_configured() -> bool:
    cfg = get_config()
    info, _ = get_service_account_info()
    return bool(cfg.get("GOOGLE_SHEET_ID")) and info is not None


def is_drive_bridge_configured() -> bool:
    """True kalau jembatan upload Drive lewat Apps Script sudah diisi
    (URL Web App + token rahasia). Ini jalur upload foto yang dipakai
    supaya tidak kena error 'Service Accounts do not have storage quota'."""
    cfg = get_config()
    return bool(cfg.get("GOOGLE_APPS_SCRIPT_URL")) and bool(cfg.get("GOOGLE_APPS_SCRIPT_SECRET"))


def set_config(values: dict):
    """Simpan konfigurasi baru ke file `.env` (persist permanen di disk,
    untuk development LOKAL) DAN langsung update os.environ supaya berlaku
    seketika tanpa restart app. Di Streamlit Cloud, gunakan menu "Secrets"
    di dashboard aplikasi, BUKAN tombol ini (perubahan lewat .env tidak
    akan tersimpan permanen di Streamlit Cloud karena disknya sementara).

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
