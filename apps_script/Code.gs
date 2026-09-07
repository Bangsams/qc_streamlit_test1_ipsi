/**
 * ======================================================================
 * QC App PT IHI — Drive Upload Bridge (Google Apps Script Web App)
 * ======================================================================
 *
 * MASALAH YANG DISELESAIKAN:
 * Service Account TIDAK punya kuota penyimpanan sendiri di Google Drive
 * (error: "Service Accounts do not have storage quota"). Google Drive API
 * murni via Service Account hanya bisa dipakai untuk menulis ke:
 *   a) Shared Drive (butuh Google Workspace), atau
 *   b) Domain dengan Domain-Wide Delegation (butuh Google Workspace juga).
 *
 * Untuk akun Google biasa (bukan Workspace), solusinya adalah script ini:
 * sebuah Web App Apps Script yang dijalankan ATAS NAMA AKUN GOOGLE ANDA
 * SENDIRI (yang punya kuota Drive normal, 15GB gratis dst), lalu aplikasi
 * Python (Streamlit) mengirim foto ke Web App ini lewat HTTP POST. Jadi:
 *
 *   Streamlit App (Service Account) --HTTP POST--> Apps Script Web App
 *   (jalan sebagai akun Google Anda) --DriveApp--> Google Drive Anda
 *
 * Service Account tetap dipakai untuk Google SHEETS (menulis baris data),
 * karena itu TIDAK bermasalah dengan kuota. Hanya upload FILE ke Drive
 * yang dialihkan lewat jembatan ini.
 *
 * ======================================================================
 * CARA DEPLOY (lakukan sekali saja):
 * ======================================================================
 * 1. Buka https://script.google.com -> "New project".
 * 2. Hapus semua kode default, lalu paste seluruh isi file Code.gs ini.
 * 3. Ganti nilai SHARED_SECRET di bawah dengan token rahasia buatan Anda
 *    sendiri (string acak, panjang, jangan mudah ditebak). Token ini
 *    mencegah orang lain memakai Web App Anda untuk upload sembarangan
 *    ke Drive Anda.
 * 4. (Opsional tapi disarankan) Buat folder khusus di Google Drive Anda
 *    untuk foto QC, buka folder itu, salin ID folder dari URL-nya:
 *    drive.google.com/drive/folders/<FOLDER_ID_ADA_DI_SINI>
 *    ID ini nanti diisi dari sisi aplikasi Python (GOOGLE_DRIVE_FOLDER_ID),
 *    bukan di sini — script ini otomatis memakai folder yang dikirim oleh
 *    aplikasi Python setiap kali upload.
 * 5. Klik "Deploy" -> "New deployment".
 * 6. Pilih tipe "Web app".
 *      - Description: bebas, misalnya "QC App Drive Bridge"
 *      - Execute as: "Me (email Anda)"  <-- WAJIB, ini kuncinya
 *      - Who has access: "Anyone"  <-- perlu ini supaya server Streamlit
 *        (tanpa login Google) bisa memanggilnya. Keamanan dijaga lewat
 *        SHARED_SECRET di atas, BUKAN lewat access control Google.
 * 7. Klik "Deploy". Google akan minta otorisasi (izinkan akses ke Drive
 *    Anda) — ikuti saja prosesnya (klik "Advanced" -> "Go to project
 *    (unsafe)" kalau muncul warning, ini normal untuk script buatan
 *    sendiri).
 * 8. Setelah deploy sukses, salin "Web app URL" yang muncul (format:
 *    https://script.google.com/macros/s/XXXXXXXX/exec).
 * 9. Masukkan Web app URL tsb + SHARED_SECRET yang sama ke pengaturan
 *    aplikasi Streamlit (GOOGLE_APPS_SCRIPT_URL & GOOGLE_APPS_SCRIPT_SECRET
 *    di panel Pengaturan halaman "Laporan Foto QC", atau file .env).
 *
 * CATATAN UPDATE KODE:
 * Kalau nanti mengubah kode ini lagi, gunakan "Deploy" -> "Manage
 * deployments" -> ikon pensil -> ganti "Version" ke "New version" ->
 * Deploy, supaya URL Web App yang sudah dipakai di Streamlit tetap sama
 * (tidak perlu ganti URL di aplikasi Python setiap kali update).
 * ======================================================================
 */

// GANTI dengan token rahasia buatan Anda sendiri (contoh: gabungan huruf/
// angka acak yang panjang). JANGAN dibagikan ke orang lain, dan gunakan
// nilai yang SAMA persis di pengaturan aplikasi Streamlit.
var SHARED_SECRET = "12345678";

// Batas ukuran file yang diterima (bytes). 15MB cukup untuk foto standar.
var MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024;


/**
 * Endpoint utama: menerima POST berisi JSON:
 * {
 *   "secret":   "<harus sama dengan SHARED_SECRET>",
 *   "fileData": "<isi file dalam base64, TANPA prefix data:...;base64,>",
 *   "filename": "nama_file.jpg",
 *   "mimeType": "image/jpeg",
 *   "folderId": "<ID folder Drive tujuan, opsional>"
 * }
 *
 * Mengembalikan JSON:
 *   sukses -> {"success": true, "fileId": "...", "url": "..."}
 *   gagal  -> {"success": false, "error": "pesan error"}
 */
function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse({ success: false, error: "Request kosong / tidak ada body JSON." });
    }

    var params;
    try {
      params = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      return jsonResponse({ success: false, error: "Body request bukan JSON yang valid." });
    }

    // --- Verifikasi token rahasia ---
    if (!params.secret || params.secret !== SHARED_SECRET) {
      return jsonResponse({ success: false, error: "Unauthorized: token rahasia salah/tidak ada." });
    }

    // --- Validasi input ---
    if (!params.fileData) {
      return jsonResponse({ success: false, error: "Field 'fileData' (base64) wajib diisi." });
    }

    var filename = params.filename || ("foto_qc_" + new Date().getTime() + ".jpg");
    var mimeType = params.mimeType || "image/jpeg";
    var folderId = params.folderId || "";

    // --- Decode base64 -> blob ---
    var decodedBytes;
    try {
      decodedBytes = Utilities.base64Decode(params.fileData);
    } catch (decodeErr) {
      return jsonResponse({ success: false, error: "Gagal decode base64: " + decodeErr.message });
    }

    if (decodedBytes.length > MAX_FILE_SIZE_BYTES) {
      return jsonResponse({
        success: false,
        error: "File terlalu besar (" + decodedBytes.length + " bytes). Maksimum " + MAX_FILE_SIZE_BYTES + " bytes."
      });
    }

    var blob = Utilities.newBlob(decodedBytes, mimeType, filename);

    // --- Tentukan folder tujuan ---
    var folder;
    if (folderId) {
      try {
        folder = DriveApp.getFolderById(folderId);
      } catch (folderErr) {
        return jsonResponse({
          success: false,
          error: "Folder ID '" + folderId + "' tidak ditemukan / tidak bisa diakses akun ini: " + folderErr.message
        });
      }
    } else {
      folder = DriveApp.getRootFolder();
    }

    // --- Upload file ---
    var file;
    try {
      file = folder.createFile(blob);
    } catch (uploadErr) {
      return jsonResponse({ success: false, error: "Gagal membuat file di Drive: " + uploadErr.message });
    }

    // --- Set izin akses: siapapun yang punya link bisa melihat (VIEW) ---
    // Ini WAJIB supaya fungsi IMAGE() di Google Sheets bisa memuat gambarnya.
    try {
      file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    } catch (shareErr) {
      // File sudah terupload walau gagal set sharing -> tetap laporkan
      // sukses, tapi beri catatan di error supaya kelihatan di UI Python.
      return jsonResponse({
        success: true,
        fileId: file.getId(),
        url: "https://lh3.googleusercontent.com/d/" + file.getId(),
        warning: "File terupload tapi gagal diset publik: " + shareErr.message
      });
    }

    var fileId = file.getId();
    var url = "https://lh3.googleusercontent.com/d/" + fileId;

    return jsonResponse({
      success: true,
      fileId: fileId,
      url: url
    });

  } catch (err) {
    return jsonResponse({ success: false, error: "Error tidak terduga: " + err.message });
  }
}


/**
 * doGet dipakai hanya untuk cek cepat apakah Web App sudah aktif & bisa
 * diakses (buka URL Web App langsung di browser -> harus muncul pesan ini,
 * bukan error 404/403). Tidak dipakai untuk upload (upload lewat POST).
 */
function doGet(e) {
  return jsonResponse({
    success: false,
    error: "Web App aktif. Endpoint ini hanya menerima method POST untuk upload foto, bukan GET."
  });
}


function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}


/**
 * Fungsi bantu untuk TES MANUAL dari dalam editor Apps Script sendiri
 * (pilih fungsi "testUploadManual" di dropdown atas editor, lalu klik Run).
 * Berguna untuk memastikan izin Drive & folder ID sudah benar SEBELUM
 * disambungkan ke aplikasi Python.
 */
function testUploadManual() {
  var dummyText = "Ini file tes dari QC App Drive Bridge";
  var blob = Utilities.newBlob(dummyText, "text/plain", "tes_koneksi_apps_script.txt");
  var file = DriveApp.getRootFolder().createFile(blob);
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  Logger.log("Sukses! File ID: " + file.getId());
  Logger.log("URL: https://drive.google.com/uc?export=view&id=" + file.getId());
}
