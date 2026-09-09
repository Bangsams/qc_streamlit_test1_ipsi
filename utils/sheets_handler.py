"""
sheets_handler.py
Integrasi Google Sheets (+ Google Drive) sebagai penyimpanan utama untuk log
hasil QC — TERMASUK FOTONYA sendiri, bukan cuma nama file. Foto ditampilkan
langsung sebagai gambar di dalam cell Google Sheets, dengan ukuran yang
DISERAGAMKAN (semua foto tampil dengan dimensi sama) supaya tabel rapi tapi
gambarnya tetap jelas/tidak pecah.

Cara kerja:
  1. Foto hasil QC di-standarkan dulu (crop persegi + resize ke resolusi tetap,
     kompresi JPEG kualitas tinggi) lewat `standardize_photo_for_sheets()`.
  2. Foto yang sudah distandarkan diupload ke folder di Google Drive milik
     Service Account yang sama (pakai Google Drive API).
  3. File di-set agar bisa diakses lewat link ("anyone with the link can
     view") — ini WAJIB, karena fungsi IMAGE() di Google Sheets hanya bisa
     menampilkan gambar dari URL yang publik dapat diakses. Data lain (nomor
     seri, hasil QC, dst) TIDAK ikut dipublikasikan — hanya file foto itu.
  4. Baris baru ditambahkan ke sheet dengan kolom foto berisi formula
     `=IMAGE("<link>", 4, <tinggi>, <lebar>)` — mode 4 artinya ukuran gambar
     dipaksa persis sesuai <tinggi> x <lebar> piksel yang kita tentukan,
     jadi SEMUA foto di kolom itu tampil dengan ukuran yang sama (seragam).

Kenapa pakai Service Account, bukan cuma "API Key" polos?
-----------------------------------------------------------
Google Sheets/Drive API murni dengan API Key hanya bisa dipakai untuk MEMBACA
resource publik — API Key saja TIDAK BISA dipakai untuk menulis/upload,
karena Google mewajibkan otentikasi OAuth2/Service Account untuk operasi
tulis. Service Account dipakai untuk Google SHEETS (tulis baris data) — ini
TIDAK bermasalah karena Sheets tidak butuh kuota storage.

PENTING soal UPLOAD FOTO ke Google Drive:
-----------------------------------------------------------
Service Account TIDAK punya kuota storage Drive sendiri (Google akan
menolak dengan error "Service Accounts do not have storage quota") kecuali
filenya diupload ke Shared Drive milik Google Workspace. Karena kebanyakan
akun bukan Google Workspace, foto TIDAK diupload lewat Service Account,
melainkan lewat "jembatan" Google Apps Script (lihat folder `apps_script/`,
file `Code.gs`) yang dijalankan atas nama akun Google pribadi Anda (yang
punya kuota Drive normal). Alurnya:

    Streamlit (Service Account, hanya utk Sheets)
        |
        `-- foto --> HTTP POST --> Apps Script Web App (jalan sbg akun Anda)
                                        |
                                        `--> Google Drive Anda

Setup (SEKALI SAJA, lihat juga README.md):
  1. Google Cloud Console -> aktifkan "Google Sheets API" (Drive API tidak
     wajib lagi untuk foto, tapi boleh tetap aktif).
  2. Buat Service Account -> download file credential .json -> dipakai
     KHUSUS untuk Sheets.
  3. Share Google Spreadsheet tujuan ke email service account tsb (client_email
     di dalam file json), beri akses Editor.
  4. Isi GOOGLE_SHEET_ID dan GOOGLE_SERVICE_ACCOUNT_JSON lewat panel Pengaturan
     di aplikasi, ATAU langsung taruh di file `.env` / environment variable.
  5. Deploy `apps_script/Code.gs` sebagai Web App (ikuti instruksi lengkap di
     dalam file tsb) dengan akun Google pribadi Anda, lalu isi
     GOOGLE_APPS_SCRIPT_URL (URL Web App) dan GOOGLE_APPS_SCRIPT_SECRET
     (token rahasia yang sama dengan di Code.gs) lewat panel Pengaturan.
  6. (Opsional) Isi GOOGLE_DRIVE_FOLDER_ID dengan ID folder Drive Anda
     sendiri (bukan milik service account) tempat foto akan diupload.
     Kosongkan kalau tidak masalah foto masuk ke root "My Drive" Anda.
"""

import io
import uuid

import pandas as pd
import requests

from .config import get_config, get_service_account_info

SHEET_TAB_NAME = "hasil_qc_log"
QC_REPORT_COLUMNS = [
    "tanggal", "waktu", "nomor_seri_barang", "jenis_ndt", "wilayah_pemeriksaan_face",
    "posisi_x_line_mm", "hasil", "perlu_gerinda", "operator_qc", "catatan", "foto",
]

# Ukuran seragam untuk foto yang ditampilkan di dalam cell Google Sheets (piksel)
SHEET_IMAGE_WIDTH = 160
SHEET_IMAGE_HEIGHT = 160

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_credentials():
    """Mengembalikan (creds, error). error diisi kalau gagal, supaya
    penyebab aslinya tidak disembunyikan (mis. JSON tidak valid, private_key
    salah escape, dsb). Pengambilan & perbaikan otomatis kredensial (termasuk
    fix backslash newline) ditangani terpusat di utils.config.get_service_account_info()."""
    info, error = get_service_account_info()
    if info is None:
        return None, error
    try:
        from google.oauth2.service_account import Credentials
    except ImportError:
        return None, "Library 'google-auth' belum terpasang (pip install google-auth)."
    try:
        return Credentials.from_service_account_info(info, scopes=_SCOPES), None
    except Exception as e:
        return None, f"Gagal membaca kredensial Service Account: {e}"


def _get_client():
    """Buat client gspread dari Service Account JSON yang tersimpan di config.
    Mengembalikan (client, sheet_id, error). error diisi kalau gagal (belum
    dikonfigurasi, library belum terpasang, atau kredensial gagal dipakai
    untuk otentikasi ke Google), supaya penyebab aslinya bisa ditampilkan
    ke user, bukan disembunyikan sebagai 'None' tanpa keterangan."""
    cfg = get_config()
    sheet_id = cfg.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        return None, None, "GOOGLE_SHEET_ID belum diisi di Pengaturan."
    try:
        import gspread
    except ImportError:
        return None, None, "Library 'gspread' belum terpasang (pip install gspread)."
    creds, cred_error = _get_credentials()
    if creds is None:
        return None, None, cred_error
    try:
        client = gspread.authorize(creds)
        return client, sheet_id, None
    except Exception as e:
        return None, None, f"Gagal otentikasi ke Google (cek Google Sheets API sudah aktif di Cloud Console): {e}"


def _get_drive_service():
    """Buat client Google Drive API (fallback upload; jalur utama tetap Apps Script)."""
    creds, _ = _get_credentials()
    if creds is None:
        return None
    try:
        from googleapiclient.discovery import build
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        return None


def _describe_gspread_error(e: Exception) -> str:
    """Terjemahkan error umum gspread/Google API jadi pesan yang actionable
    dalam Bahasa Indonesia, supaya user tahu persis apa yang harus dibetulkan."""
    msg = str(e)
    low = msg.lower()
    if "permission_denied" in low or "403" in low:
        return (f"PERMISSION DENIED (403). Kemungkinan besar Google Spreadsheet BELUM di-share ke "
                f"email Service Account dengan akses Editor, ATAU 'Google Sheets API' belum diaktifkan "
                f"di project Google Cloud tsb. Detail asli: {msg}")
    if "not found" in low or "404" in low:
        return (f"SPREADSHEET TIDAK DITEMUKAN (404). Cek lagi GOOGLE_SHEET_ID sudah benar (dari URL "
                f"spreadsheet), atau spreadsheet-nya sudah dihapus/dipindah. Detail asli: {msg}")
    if "invalid_grant" in low or "invalid_rsa" in low or "jwt" in low:
        return (f"Kredensial Service Account tidak valid/rusak (private key bermasalah, atau jam sistem "
                f"server tidak sinkron). Coba download ulang file JSON key yang baru dari Google Cloud "
                f"Console. Detail asli: {msg}")
    if "has not been used" in low or "is disabled" in low or "accessnotconfigured" in low:
        return (f"API BELUM DIAKTIFKAN di project Google Cloud ini. Buka Google Cloud Console -> APIs & "
                f"Services -> Library -> aktifkan 'Google Sheets API'. Detail asli: {msg}")
    return f"Error tidak terduga saat mengakses Google Sheets: {msg}"


def _get_worksheet():
    """Mengembalikan (worksheet, error). Kalau gagal, error berisi pesan
    actionable (lihat _describe_gspread_error), bukan cuma None."""
    client, sheet_id, conn_error = _get_client()
    if client is None:
        return None, conn_error
    try:
        sh = client.open_by_key(sheet_id)
    except Exception as e:
        return None, _describe_gspread_error(e)

    try:
        ws = sh.worksheet(SHEET_TAB_NAME)
        sync_error = _sync_header(ws)
        return ws, sync_error
    except Exception:
        # Tab belum ada -> buat baru dengan header sesuai skema terbaru
        try:
            ws = sh.add_worksheet(title=SHEET_TAB_NAME, rows=1000, cols=len(QC_REPORT_COLUMNS))
            ws.append_row(QC_REPORT_COLUMNS)
            return ws, None
        except Exception as e:
            return None, _describe_gspread_error(e)


def _pad_header_for_update(old_header: list) -> list:
    """Kalau skema kolom sekarang lebih PENDEK dari header lama di sheet
    (mis. dulu ada 'link_foto', sekarang dihapus), tetap tulis sel kosong
    ("") di posisi kolom lama itu supaya tidak jadi 'kolom hantu' dengan
    judul basi yang tidak sesuai skema baru."""
    new_header = list(QC_REPORT_COLUMNS)
    if len(old_header) > len(new_header):
        new_header += [""] * (len(old_header) - len(new_header))
    return new_header


def _sync_header(ws) -> str:
    """Pastikan baris header (baris 1) di sheet SELALU sesuai skema kolom
    terbaru (QC_REPORT_COLUMNS) — dipanggil otomatis tiap kali worksheet
    diakses, supaya sheet lama (dibuat versi aplikasi sebelumnya, dengan
    nama kolom lama seperti 'foto_path'/'status_kirim_wa'/'link_foto')
    otomatis diperbarui strukturnya tanpa mengganggu baris data yang sudah
    ada. Mengembalikan None kalau sukses/tidak perlu diubah, atau pesan error."""
    try:
        header = ws.row_values(1)
        if header != QC_REPORT_COLUMNS:
            ws.update("A1", [_pad_header_for_update(header)])
        return None
    except Exception as e:
        return _describe_gspread_error(e)


def force_update_sheet_structure() -> tuple:
    """Paksa perbarui struktur kolom Google Sheets sekarang juga (dipanggil
    dari tombol '🔄 Perbarui Struktur Google Sheets' di UI) — berguna kalau
    sheet dibuat manual atau dari versi aplikasi lama dengan kolom berbeda
    (termasuk membersihkan kolom lama seperti 'link_foto' yang sudah tidak
    dipakai lagi).
    Mengembalikan (sukses: bool, pesan: str)."""
    client, sheet_id, conn_error = _get_client()
    if client is None:
        return False, conn_error
    try:
        sh = client.open_by_key(sheet_id)
    except Exception as e:
        return False, _describe_gspread_error(e)

    try:
        try:
            ws = sh.worksheet(SHEET_TAB_NAME)
        except Exception:
            ws = sh.add_worksheet(title=SHEET_TAB_NAME, rows=1000, cols=len(QC_REPORT_COLUMNS))
            ws.append_row(QC_REPORT_COLUMNS)
            return True, f"Tab '{SHEET_TAB_NAME}' belum ada, berhasil dibuat baru dengan struktur kolom terbaru."

        header = ws.row_values(1)
        if header == QC_REPORT_COLUMNS:
            return True, "Struktur kolom sudah sesuai skema terbaru, tidak ada yang diubah."
        padded = _pad_header_for_update(header)
        ws.update("A1", [padded])
        note = ""
        if len(header) > len(QC_REPORT_COLUMNS):
            extra_cols = header[len(QC_REPORT_COLUMNS):]
            note = (f"\nKolom lama yang sudah tidak dipakai ({', '.join(c for c in extra_cols if c)}) "
                     f"judulnya sudah dikosongkan. Kalau mau, hapus kolomnya juga secara manual "
                     f"(klik kanan header kolom -> 'Delete column') supaya sheet lebih rapi — "
                     f"data yang sudah ada TIDAK dihapus otomatis demi keamanan.")
        return True, (f"Header baris 1 diperbarui.\nSebelum: {header}\nSesudah: {QC_REPORT_COLUMNS}"
                       f"{note}")
    except Exception as e:
        return False, _describe_gspread_error(e)


def test_sheets_connection() -> tuple:
    """Fungsi diagnostik: coba buka spreadsheet & pastikan tab + header
    sudah benar, TANPA menulis baris data. Dipanggil dari tombol '🧪 Tes
    Koneksi Google Sheets' di UI. Mengembalikan (sukses, pesan)."""
    ws, error = _get_worksheet()
    if ws is None:
        return False, error or "Gagal terhubung ke Google Sheets tanpa keterangan error."
    try:
        title = ws.spreadsheet.title
        header = ws.row_values(1)
        return True, (f"Berhasil terhubung ke spreadsheet '{title}', tab '{SHEET_TAB_NAME}'.\n"
                       f"Header saat ini: {header}")
    except Exception as e:
        return False, _describe_gspread_error(e)


def is_available() -> bool:
    ws, _ = _get_worksheet()
    return ws is not None


def get_last_sheets_error() -> str:
    """Ambil pesan error terakhir dari percobaan koneksi ke Google Sheets,
    dipakai UI untuk menampilkan alasan asli kalau is_available() == False."""
    _, error = _get_worksheet()
    return error or ""


def standardize_photo_for_sheets(image_bytes: bytes) -> bytes:
    """Standarkan foto sebelum diupload ke Drive/ditampilkan di Sheets:
    crop jadi persegi (square) di bagian tengah, lalu resize ke resolusi
    tetap, dan re-encode JPEG kualitas tinggi. Hasilnya: semua foto di
    kolom Google Sheets punya bentuk & ukuran yang SAMA (rapi/seragam),
    tapi tetap tajam/jelas karena resolusi & kualitas kompresi dijaga tinggi."""
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)  # perbaiki orientasi dari kamera HP
        img = img.convert("RGB")

        # Crop jadi persegi (ambil bagian tengah) sebelum resize, supaya
        # subjek foto tidak gepeng/distorsi saat dipaksa jadi persegi.
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))

        # Resolusi disimpan lebih tinggi dari ukuran tampil di sheet (2x)
        # supaya tetap tajam walau di-scale ke kotak kecil oleh IMAGE().
        target_px = max(SHEET_IMAGE_WIDTH, SHEET_IMAGE_HEIGHT) * 2
        img = img.resize((target_px, target_px), Image.LANCZOS)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=90, optimize=True)
        return out.getvalue()
    except Exception:
        return image_bytes


def _upload_photo_via_apps_script(image_bytes: bytes, filename: str):
    """Upload foto lewat jembatan Google Apps Script Web App (apps_script/Code.gs),
    yang dijalankan atas nama akun Google pribadi (punya kuota Drive normal) —
    ini jalur upload UTAMA supaya tidak kena error 'Service Accounts do not
    have storage quota'.

    Mengembalikan (embed_url, view_url, error):
      - embed_url: link endpoint "thumbnail" Google (stabil untuk ditanam di
        formula IMAGE() Sheets — beda dari "uc?export=view" yang sering
        diblokir Google untuk hotlink eksternal, penyebab foto tidak tampil).
      - view_url: link biasa untuk DIBUKA LANGSUNG (klik) di tab baru.
    """
    import base64

    cfg = get_config()
    script_url = cfg.get("GOOGLE_APPS_SCRIPT_URL", "").strip()
    secret = cfg.get("GOOGLE_APPS_SCRIPT_SECRET", "").strip()
    folder_id = cfg.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()

    payload = {
        "secret": secret,
        "fileData": base64.b64encode(image_bytes).decode("ascii"),
        "filename": filename,
        "mimeType": "image/jpeg",
        "folderId": folder_id,
    }

    try:
        resp = requests.post(script_url, json=payload, timeout=60)
    except requests.exceptions.RequestException as e:
        return None, None, f"Gagal menghubungi Apps Script Web App: {e}"

    # Apps Script kadang mengembalikan halaman HTML (redirect otorisasi dsb)
    # kalau URL/deployment-nya salah -> deteksi supaya errornya jelas.
    try:
        data = resp.json()
    except ValueError:
        snippet = resp.text[:200].replace("\n", " ")
        return None, None, (
            f"Respons dari Apps Script bukan JSON (HTTP {resp.status_code}). "
            f"Kemungkinan URL Web App salah, deployment belum 'Anyone' akses, "
            f"atau belum di-deploy ulang setelah edit kode. Cuplikan respons: {snippet}"
        )

    if not data.get("success"):
        return None, None, data.get("error", "Apps Script mengembalikan error tanpa keterangan.")

    # embedUrl/viewUrl = field baru (Code.gs versi terbaru). Fallback ke
    # field lama "url" kalau Apps Script belum di-redeploy ke versi baru
    # (supaya tetap jalan, walau embed-nya bisa saja masih kena blokir Google).
    embed_url = data.get("embedUrl") or data.get("url")
    view_url = data.get("viewUrl") or data.get("url")

    if data.get("warning"):
        return embed_url, view_url, data.get("warning")

    return embed_url, view_url, None


def upload_photo_to_drive(image_bytes: bytes, filename: str):
    """Upload foto ke Google Drive, lalu set permission supaya bisa diakses
    lewat link (dibutuhkan agar IMAGE() di Sheets bisa memuat gambarnya).

    Jalur upload (urutan prioritas):
      1. Google Apps Script Web App (GOOGLE_APPS_SCRIPT_URL +
         GOOGLE_APPS_SCRIPT_SECRET) — jalur UTAMA yang direkomendasikan,
         karena upload dilakukan atas nama akun Google pribadi (punya
         kuota Drive), bukan Service Account. Ini yang mengatasi error
         'Service Accounts do not have storage quota'.
      2. Kalau jembatan Apps Script belum dikonfigurasi, fallback ke Drive
         API langsung pakai Service Account (hanya akan berhasil kalau
         foto diupload ke Shared Drive Google Workspace tempat service
         account jadi member — lihat dokumentasi
         https://developers.google.com/workspace/drive/api/guides/about-shareddrives).

    Mengembalikan (embed_url, view_url, error):
      - embed_url: link endpoint "thumbnail" Google, dipakai untuk formula
        IMAGE() di Sheets (stabil untuk hotlink, beda dari "uc?export=view"
        yang sering diblokir Google -> penyebab foto tidak tampil/error).
      - view_url: link untuk DIBUKA LANGSUNG (klik) di tab baru, lihat foto
        resolusi penuh di Drive.
      - error diisi kalau gagal, supaya penyebabnya jelas (bukan disembunyikan)."""
    cfg = get_config()

    # --- Jalur 1: Apps Script bridge (direkomendasikan) ---
    if cfg.get("GOOGLE_APPS_SCRIPT_URL") and cfg.get("GOOGLE_APPS_SCRIPT_SECRET"):
        return _upload_photo_via_apps_script(image_bytes, filename)

    # --- Jalur 2: fallback ke Service Account + Drive API langsung ---
    service = _get_drive_service()
    if service is None:
        return None, None, (
            "Belum ada jalur upload Drive yang terkonfigurasi. Isi "
            "GOOGLE_APPS_SCRIPT_URL + GOOGLE_APPS_SCRIPT_SECRET di panel "
            "Pengaturan (rekomendasi, lihat apps_script/Code.gs), ATAU pakai "
            "Shared Drive Google Workspace kalau tetap ingin lewat Service Account."
        )
    try:
        from googleapiclient.http import MediaIoBaseUpload
        from googleapiclient.errors import HttpError

        folder_id = cfg.get("GOOGLE_DRIVE_FOLDER_ID", "")

        file_metadata = {"name": filename}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype="image/jpeg", resumable=False)
        try:
            uploaded = service.files().create(
                body=file_metadata, media_body=media, fields="id", supportsAllDrives=True
            ).execute()
        except HttpError as e:
            reason = e._get_reason()
            hint = ""
            if e.resp.status == 403 and "storage quota" in reason.lower():
                hint = (" -> Gunakan jembatan Google Apps Script (isi "
                        "GOOGLE_APPS_SCRIPT_URL & GOOGLE_APPS_SCRIPT_SECRET di "
                        "Pengaturan) supaya tidak kena batas kuota Service Account.")
            return None, None, f"Gagal upload ke Drive (HTTP {e.resp.status}): {reason}{hint}"

        file_id = uploaded.get("id")
        if not file_id:
            return None, None, f"Upload sukses tapi tidak ada file id di respons: {uploaded}"

        # Beri akses publik "anyone with the link" khusus untuk file foto ini
        # (bukan seluruh Drive), supaya Google Sheets bisa memuat gambarnya
        # lewat IMAGE(). Data lain (Sheets) TIDAK ikut menjadi publik.
        try:
            service.permissions().create(
                fileId=file_id, body={"role": "reader", "type": "anyone"}, supportsAllDrives=True
            ).execute()
        except HttpError as e:
            return None, None, f"Foto terupload tapi gagal diset publik (HTTP {e.resp.status}): {e._get_reason()}"

        embed_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"
        view_url = f"https://drive.google.com/file/d/{file_id}/view"
        return embed_url, view_url, None
    except Exception as e:
        return None, None, f"Gagal upload ke Google Drive: {e}"


def append_qc_report(record: dict, image_bytes: bytes = None) -> tuple:
    """Tambahkan satu baris hasil QC ke Google Sheets. Kalau image_bytes
    diberikan, foto diupload dulu ke Google Drive, lalu kolom 'foto' diisi
    LINK KLIK LANGSUNG (formula HYPERLINK()) ke foto tsb di Drive.

    Sengaja TIDAK pakai formula IMAGE() lagi: IMAGE() perlu Google
    men-fetch & me-render gambarnya di server Sheets, dan itu sering gagal
    (muncul '#ERROR!' di cell) karena kebijakan Google yang berubah-ubah
    soal hotlink dari Drive. HYPERLINK() jauh lebih andal — cuma teks biasa
    yang bisa diklik, tidak pernah gagal 'fetch gambar'.

    Mengembalikan (sukses: bool, foto_view_url: str atau None, error: str atau None).
    'error' diisi kalau ada bagian yang gagal (mis. upload foto gagal, atau
    Sheets sendiri gagal diakses), supaya penyebabnya terlihat jelas di UI,
    bukan disembunyikan."""
    ws, ws_error = _get_worksheet()
    if ws is None:
        return False, None, ws_error or "Google Sheets belum terhubung."

    view_url = None
    foto_error = None
    foto_cell_value = ""
    if image_bytes:
        std_bytes = standardize_photo_for_sheets(image_bytes)
        filename = f"{record.get('nomor_seri_barang', 'foto')}_{uuid.uuid4().hex[:8]}.jpg"
        _embed_url_unused, view_url, foto_error = upload_photo_to_drive(std_bytes, filename)
        if view_url:
            foto_cell_value = f'=HYPERLINK("{view_url}","Lihat Foto")'

    try:
        row = [record.get(col, "") for col in QC_REPORT_COLUMNS if col != "foto"]
        row.append(foto_cell_value)
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True, view_url, foto_error
    except Exception as e:
        return False, view_url, f"Gagal menulis baris ke Sheets: {_describe_gspread_error(e)}"


def test_drive_upload() -> tuple:
    """Fungsi diagnostik: coba upload 1 foto kecil dummy ke Drive, untuk
    memastikan kredensial/scope/folder ID sudah benar. Dipanggil dari tombol
    'Tes Upload ke Google Drive' di UI. Mengembalikan (sukses, pesan)."""
    try:
        from PIL import Image
        img = Image.new("RGB", (100, 100), (0, 150, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        embed_url, view_url, error = upload_photo_to_drive(buf.getvalue(), f"tes_koneksi_{uuid.uuid4().hex[:6]}.jpg")
        if view_url:
            return True, f"Berhasil upload. Link foto: {view_url}"
        return False, error or "Gagal upload tanpa keterangan error."
    except Exception as e:
        return False, f"Gagal menjalankan tes: {e}"


def load_qc_report_log() -> pd.DataFrame:
    """Ambil seluruh log hasil QC dari Google Sheets sebagai DataFrame.
    Mengembalikan DataFrame kosong kalau Sheets belum/tidak bisa diakses."""
    ws, _ = _get_worksheet()
    if ws is None:
        return pd.DataFrame(columns=QC_REPORT_COLUMNS)
    try:
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame(columns=QC_REPORT_COLUMNS)
        return pd.DataFrame(records)
    except Exception:
        return pd.DataFrame(columns=QC_REPORT_COLUMNS)
