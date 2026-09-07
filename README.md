# Aplikasi QC Digital — Deteksi & Analisis Defect
### Studi Kasus: PT IHI Power Service Indonesia
### Fokus NDT: Ultrasonic Testing (UT) + Magnetic Particle Testing (MT)

Aplikasi berbasis **Streamlit** untuk digitalisasi proses QC fabrikasi baja (welding & pressure part),
mengintegrasikan **SPC (Statistical Process Control)**, **Six Sigma DMAIC**, dan **Machine Learning**
untuk analisis root cause — **tanpa memerlukan foto/gambar plant** (sesuai kebijakan keamanan perusahaan),
cukup berbasis data parameter mesin & hasil pembacaan alat NDT (UT/MT) yang dibaca dari digital display.

## Kenapa UT dan MT?

Kombinasi ini mencerminkan praktik umum QC las: **Ultrasonic Testing (UT)** mendeteksi cacat
*internal/subsurface* (incomplete fusion, slag inclusion), sementara **Magnetic Particle Testing (MT)**
mendeteksi cacat *permukaan* pada material ferromagnetik (crack, undercut). Satu joint dinyatakan
**Reject** jika salah satu dari kedua metode menemukan indikasi yang melebihi acceptance criteria
(ASME Section V).

## Struktur Proyek

```
qc_ihi_app/
├── app.py                          # Halaman utama (Dashboard/Home)
├── requirements.txt                # Daftar library yang dibutuhkan
├── pages/                          # Multi-page Streamlit (otomatis muncul di sidebar)
│   ├── 1_Input_Data.py             # 3 tab form: Proses Las, Hasil UT, Hasil MT
│   ├── 2_SPC_Analysis.py           # Xbar-S (UT Thickness), P-Chart (Reject UT+MT), Cp/Cpk
│   ├── 3_DMAIC_SixSigma.py         # Kalkulator DPMO/Sigma Level (dari data gabungan) + tracker DMAIC
│   ├── 4_Prediksi_Defect.py        # Random Forest: parameter las → prediksi reject UT+MT
│   └── 5_Laporan_Foto_QC.py        # Foto QC -> otomatis tercatat ke Google Sheets (foto tampil langsung, seragam)
├── utils/                          # Modul logika bisnis (dipisah dari tampilan)
│   ├── qc_utils.py                 # Rumus SPC, Cp/Cpk, DPMO, Sigma Level
│   ├── data_handler.py             # Baca/tulis data ke CSV + fungsi gabungan (join UT+MT+proses las)
│   ├── config.py                   # Konfigurasi kredensial Google Sheets/Drive (baca/tulis file .env)
│   └── sheets_handler.py           # Integrasi Google Sheets + Drive (log hasil QC & upload foto)
├── .env.example                    # Contoh variabel environment yang perlu diisi (lihat panduan di bawah)
├── .env                            # (dibuat otomatis, TIDAK di-commit) — isi kredensial asli tersimpan di sini
└── data/                           # Penyimpanan data (CSV sebagai database sederhana)
    ├── weld_process_data.csv       # Parameter proses las (seed 80 baris)
    ├── ut_inspection_data.csv      # Hasil Ultrasonic Testing (seed 80 baris)
    ├── mt_inspection_data.csv      # Hasil Magnetic Particle Testing (seed 80 baris)
    ├── hasil_qc_log.xlsx           # Backup lokal log hasil QC (dibuat otomatis)
    └── photos/                     # Backup file foto resolusi asli hasil QC (dibuat otomatis)
```

## Struktur Data Kunci

**Parameter Proses Las** (fitur/root-cause): arus, tegangan, travel speed, preheat, interpass, gas flow.

**Data UT** (label cacat internal): frekuensi probe, sudut probe, gain, thickness reading, indication
amplitude (%), defect depth/length, hasil Accept/Reject.

**Data MT** (label cacat permukaan): jenis magnetisasi (Yoke AC/DC, Prod), arus magnetisasi, arah medan,
jenis partikel, lifting power test (kg), indikasi (Linear/Rounded), panjang indikasi, hasil Accept/Reject.

Ketiga tabel dihubungkan lewat kolom **`batch_id`** yang sama, digabung otomatis oleh fungsi
`load_combined_data()` di `utils/data_handler.py`.

## Mengapa Struktur Ini?

1. **Tiga tabel terpisah, digabung saat analisis** — mencerminkan alur kerja nyata: welder mencatat
   parameter las, inspector UT dan inspector MT bekerja terpisah, dan datanya baru digabung saat analisis
   DMAIC/ML lewat Nomor Batch yang sama.
2. **Pemisahan logika dan tampilan (`utils/` vs `pages/`)** — rumus SPC/DMAIC ditulis sekali di `qc_utils.py`.
3. **Multi-page Streamlit bawaan** — navigasi sidebar otomatis dari folder `pages/`.
4. **CSV sebagai "database" sementara** — cukup untuk skala data QC harian/mingguan.
5. **Berbasis parameter mesin & hasil NDT, bukan gambar** — foto plant tidak diizinkan, sehingga model ML
   memprediksi hasil UT/MT dari parameter proses las, bukan dari computer vision.

## Cara Menjalankan

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Jalankan aplikasi
streamlit run app.py
```

Aplikasi akan terbuka otomatis di browser (biasanya `http://localhost:8501`).

## Alur Penggunaan

1. **Input Data** — welder/operator mencatat parameter las (tab 1), inspector UT mencatat hasil UT (tab 2),
   inspector MT mencatat hasil MT (tab 3) — semua pakai Nomor Batch/Joint yang sama.
2. **SPC Analysis** — QC Engineer memonitor Xbar-S Chart (dari UT thickness reading) dan P-Chart (reject
   rate gabungan UT+MT) secara berkala.
3. **DMAIC & Six Sigma** — dipakai saat menjalankan proyek perbaikan mutu terstruktur berbasis data
   gabungan UT+MT, melacak progres tiap fase.
4. **Prediksi Defect** — sebelum eksekusi las dengan parameter tertentu, cek prediksi risiko reject
   (gabungan UT+MT); juga melihat parameter proses mana yang paling berpengaruh (feature importance) dan
   breakdown kontribusi UT vs MT terhadap total reject.

## Data Contoh (Seed Data)

Ketiga file CSV di folder `data/` sudah diisi 80 baris data simulasi (termasuk korelasi buatan: preheat
rendah/arus rendah → risiko reject UT lebih tinggi; travel speed tinggi/arus tinggi → risiko reject MT
lebih tinggi) untuk keperluan demo/latihan model ML. Ganti/hapus isinya dan mulai input data asli melalui
halaman "Input Data" untuk pemakaian nyata.

## Fitur: Foto Otomatis → Google Sheets (konfigurasi SEKALI ISI & permanen)

Halaman **"Laporan Foto QC"** menggantikan alur manual (foto → catat manual di Excel) menjadi
satu alur digital:

1. Operator QC ambil foto langsung dari aplikasi (kamera device/laptop)
2. Isi form singkat: Nomor Seri Barang, Jenis NDT (UT/MT), Wilayah (Face A/B/C), Posisi X-Line,
   Hasil (Accept/Perlu Gerinda/Reject), Operator QC
3. Klik satu tombol → foto + data otomatis tercatat ke **Google Sheets** — **fotonya tampil
   langsung sebagai gambar di dalam sheet** (bukan cuma nama file), dengan ukuran yang
   **diseragamkan** (semua foto berdimensi sama, rapi) tapi tetap tajam/jelas. Ada juga backup
   `data/hasil_qc_log.xlsx` dan file foto resolusi asli di `data/photos/`.

### Kenapa fotonya bisa tampil langsung di dalam sheet?

Google Sheets tidak bisa menyimpan file gambar langsung di dalam sel, tapi bisa **menampilkan**
gambar dari URL memakai formula `IMAGE()`. Jadi alurnya:

1. Foto distandarkan dulu (dipotong jadi persegi, diresize ke resolusi tetap, dikompres JPEG
   kualitas tinggi) — supaya semua foto di kolom itu terlihat rapi berukuran sama.
2. Foto yang sudah distandarkan diupload ke **Google Drive** LEWAT JEMBATAN **Google Apps
   Script** (`apps_script/Code.gs`, jalan atas nama akun Google pribadi — BUKAN Service Account,
   karena Service Account tidak punya kuota storage Drive sendiri), lalu diberi izin akses
   "siapa saja yang punya link" **khusus file foto itu saja** (bukan seluruh Drive/data lain),
   supaya Google Sheets bisa memuatnya.
3. Baris baru di sheet berisi formula `=IMAGE("<link foto>",4,160,160)` di kolom `foto` — mode 4
   artinya ukuran dipaksa 160x160 piksel persis, jadi semua foto di kolom itu seragam.
4. File foto resolusi ASLI (belum di-crop/kompres) tetap disimpan sebagai backup lokal di
   `data/photos/`, sedangkan link foto di Drive juga dicatat sebagai backup teks di Excel lokal.

### Konfigurasi Google Sheets & Drive — cukup SEKALI ISI, tersimpan permanen

Semua kredensial disimpan di file `.env` (lihat `utils/config.py`), **bukan** di session
browser — jadi tidak hilang saat aplikasi dimatikan/restart, baik dijalankan lokal maupun setelah
di-deploy (AWS, Streamlit Cloud, dsb, selama disk/volume `.env`-nya persist).

Google Sheets/Drive API murni dengan "API Key" saja hanya bisa **membaca** resource publik, tidak
bisa menulis/upload otomatis. Supaya app ini bisa **otomatis menulis data** dipakai **Service
Account**. Tapi Service Account **TIDAK punya kuota storage Drive sendiri** — kalau dipakai
langsung untuk upload foto, akan muncul error:

```
Gagal upload ke Drive (HTTP 403): Service Accounts do not have storage quota.
```

Karena itu, upload **foto** dialihkan lewat **Google Apps Script Web App** (`apps_script/Code.gs`)
yang jalan atas nama akun Google pribadi (punya kuota Drive normal). Service Account tetap dipakai
untuk **Google Sheets saja** (tidak bermasalah, karena Sheets tidak butuh kuota storage).

**A) Setup Google Sheets (Service Account):**

1. Buka [Google Cloud Console](https://console.cloud.google.com/) → buat/pilih Project →
   aktifkan **"Google Sheets API"**.
2. Menu **"APIs & Services" → "Credentials"** → **Create Credentials → Service Account** →
   buat, lalu buka tab **Keys → Add Key → JSON** untuk download file credential `.json`.
3. Buka Google Spreadsheet tujuan → klik **Share** → tempel email service account (ada di dalam
   file json, field `client_email`) → beri akses **Editor**.

**B) Setup jembatan upload foto (Google Apps Script):**

4. Buka [script.google.com](https://script.google.com) dengan akun Google pribadi Anda → **New
   project** → hapus kode default → paste seluruh isi `apps_script/Code.gs`.
5. Ganti nilai `SHARED_SECRET` di baris atas kode dengan token rahasia buatan sendiri.
6. **Deploy → New deployment → Web app** dengan **Execute as: Me**, **Who has access: Anyone**.
   Ikuti proses otorisasi yang muncul (izinkan akses ke Drive Anda).
7. Salin **Web app URL** hasil deploy (format `.../macros/s/XXXX/exec`).
8. *(Opsional)* Buat folder khusus di Drive akun tsb untuk foto QC, catat ID-nya dari URL
   (`drive.google.com/drive/folders/<FOLDER_ID>`).

Instruksi lebih detail (termasuk cara update kode tanpa ganti URL) ada di dalam komentar
`apps_script/Code.gs` itu sendiri.

**C) Isi semuanya di aplikasi:**

9. Buka halaman **"Laporan Foto QC"** → panel **"⚙️ Pengaturan"** → isi **Google Sheet ID**,
   **Service Account JSON**, **Web App URL Apps Script**, **Token rahasia Apps Script** (harus
   sama dengan `SHARED_SECRET` di langkah 5), dan opsional **Folder Drive ID** → klik
   **"💾 Simpan"**.
10. Setelah tersimpan, tidak perlu isi ulang lagi. Klik **"✏️ Ubah Konfigurasi"** kalau perlu
    ganti sheet/folder/kredensial lain.
11. Alternatif saat deploy: isi environment variable `GOOGLE_SHEET_ID`,
    `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_APPS_SCRIPT_URL`, `GOOGLE_APPS_SCRIPT_SECRET`, dan
    `GOOGLE_DRIVE_FOLDER_ID` (boleh isi JSON langsung, atau path ke file `.json` yang di-mount
    sebagai secret file) — otomatis diprioritaskan di atas isi file `.env`.

Kalau Google Sheets belum dikonfigurasi, aplikasi otomatis fallback menyimpan hanya ke Excel
lokal (`data/hasil_qc_log.xlsx`) supaya data tidak pernah hilang.

⚠️ **Catatan privasi**: agar `IMAGE()` di Google Sheets bisa memuat foto, setiap file foto yang
diupload diberi izin "siapa saja dengan link dapat melihat" **satu per satu file**, bukan seluruh
folder/Drive. Artinya siapa pun yang tahu/menebak link filenya bisa melihat foto itu (link-nya
acak/panjang, jadi praktis tidak bisa ditebak, tapi tetap bukan "private" dalam arti mutlak).
Data teks lain (nomor seri, hasil QC, dst) di Google Sheets tetap privat sesuai siapa yang
di-share aksesnya.

### Semua kredensial aman di `.env` (siap deploy)

- Semua kredensial (`GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_APPS_SCRIPT_URL`,
  `GOOGLE_APPS_SCRIPT_SECRET`, `GOOGLE_DRIVE_FOLDER_ID`) tersimpan di file **`.env`** di root
  folder aplikasi — lihat contoh strukturnya di `.env.example`.
- File `.env` **tidak** ikut ke Git (sudah masuk `.gitignore`), jadi kredensial tidak bocor saat
  push ke repository publik/privat.
- Saat deploy ke platform apa pun (AWS EC2/ECS, Streamlit Community Cloud, Docker, dsb), cukup:
  - Salin file `.env` (berisi kredensial asli) ke server/container tujuan, **atau**
  - Set nilai yang sama sebagai *environment variable*/*secrets* bawaan platform tsb — nilai ini
    otomatis lebih diprioritaskan dibanding isi file `.env` (lihat `utils/config.py`).
- Tidak perlu mengubah kode program sama sekali untuk ganti kredensial — cukup lewat UI
  Pengaturan atau langsung edit `.env`/environment variable.


## Acuan AWS D1.1 yang Sudah Diintegrasikan

Berdasarkan prosedur internal PT IHI Power Service Indonesia (A2-0195 UT Procedure & A2-0196 MT
Procedure, keduanya "Based on AWS D1.1 Structural Welding Code – Steel"):

- **Lifting Power Yoke MT minimum 4.5 kg (10 lb)** — divalidasi otomatis di form Input Data,
  muncul peringatan jika di bawah syarat (`utils/qc_utils.py: check_mt_lifting_power`)
- **Kalibrasi UT**: field tanggal kalibrasi alat ditambahkan di form UT (acuan: zero reference
  tiap 2 jam kerja, internal reflection check maks interval 40 jam)
- **Equipment options** UT (GE USM 35XDAC/36/Go/USM100, Sonatest WAVE) dan MT (Yoke AC/DC, Prod, Coil)
  sesuai daftar alat yang diizinkan pada prosedur
- **Personnel minimum UT Level II** (Manual Contact Testing Technique) — sebagai catatan kualifikasi

## Rencana Bertahap (Roadmap)

- **Minggu ini**: fokus aplikasi digital (Streamlit) — sudah mencakup Input Data, SPC, DMAIC,
  Prediksi ML, dan Laporan Foto ke Google Sheets seperti di proyek ini.
- **Minggu depan**: integrasi microcontroller murah untuk membantu QC di lapangan. Beberapa opsi
  yang bisa dipertimbangkan (akan dibahas lebih detail saat itu):
  - **ESP32-CAM** — modul kamera murah (~Rp50-80rb) untuk otomatisasi capture foto tanpa perlu HP,
    bisa dikirim langsung ke server aplikasi via WiFi
  - **RFID/NFC reader + ESP32** — tag RFID ditempel di setiap batch/joint untuk auto-identifikasi
    Nomor Seri, mengurangi human error saat input manual
  - **ESP32 + tombol fisik** — tombol cepat "Accept/Reject" di meja kerja inspector yang langsung
    terhubung ke aplikasi lewat WiFi/HTTP request, tanpa perlu buka form di HP/laptop setiap kali



- **Autentikasi login** — tambahkan `streamlit-authenticator` agar tiap operator/inspector punya akun sendiri.
- **Database sungguhan** — migrasi dari CSV ke SQLite/PostgreSQL jika data sudah ribuan baris.
- **Integrasi API cuaca** — tarik data suhu/kelembaban otomatis (BMKG/OpenWeatherMap) untuk fitur tambahan.
- **Model klasifikasi jenis defect** — kembangkan model terpisah untuk memprediksi jenis indikasi MT
  (Linear vs Rounded) atau severity UT (berdasarkan amplitude), tidak hanya Accept/Reject biner.
- **Ekspor laporan otomatis** — tambah tombol "Generate Laporan PDF/Word" memakai `python-docx`/`reportlab`.
- **Deploy online** — pakai [Streamlit Community Cloud](https://streamlit.io/cloud) (gratis) atau hosting
  internal perusahaan.

