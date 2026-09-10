"""
qc_utils.py
Kumpulan fungsi perhitungan QC: SPC (Xbar-S, P-Chart), Process Capability (Cp/Cpk),
dan Six Sigma (DPMO, Sigma Level) untuk aplikasi QC PT IHI Power Service Indonesia.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

# ---------------------------------------------------------------------------
# Konstanta SPC (Montgomery, Introduction to Statistical Quality Control)
# Key: ukuran subgroup (n) -> (A3, B3, B4)
# ---------------------------------------------------------------------------
SPC_CONSTANTS = {
    2: (2.659, 0, 3.267),
    3: (1.954, 0, 2.568),
    4: (1.628, 0, 2.266),
    5: (1.427, 0, 2.089),
    6: (1.287, 0.030, 1.970),
    7: (1.182, 0.118, 1.882),
    8: (1.099, 0.185, 1.815),
    9: (1.032, 0.239, 1.761),
    10: (0.975, 0.284, 1.716),
}

# Tabel acuan Sigma Level vs DPMO (long-term, sudah termasuk shift 1.5 sigma)
SIGMA_BENCHMARK = [
    (1, 691462, "Sangat Buruk"),
    (2, 308538, "Buruk"),
    (3, 66807, "Cukup / Rata-rata Industri"),
    (4, 6210, "Baik"),
    (5, 233, "Sangat Baik"),
    (6, 3.4, "World Class"),
]


# ---------------------------------------------------------------------------
# Ambang batas acuan AWS D1.1 (dari prosedur internal PT IHI Power Service
# Indonesia: A2-0195 UT Procedure & A2-0196 MT Procedure, based on AWS D1.1
# Structural Welding Code - Steel, 25th Edition 2025)
# ---------------------------------------------------------------------------
MT_MIN_LIFTING_POWER_KG = 4.5  # AC Yoke, min 10 lb (4.5 kg), verifikasi tiap shift (Sec 6.2)
UT_CALIBRATION_MAX_INTERVAL_HOURS = 2   # Zero reference level, tiap 2 jam kerja (Sec 6.2.6)
UT_INTERNAL_REFLECTION_MAX_HOURS = 40   # Internal reflection check, maks interval 40 jam (Sec 6.2.5)
UT_PERSONNEL_MIN_LEVEL = "UT Level II - Manual Contact Testing Technique"
MT_EQUIPMENT_OPTIONS = ["AC Yoke", "DC Yoke", "Prod", "Coil"]
UT_EQUIPMENT_OPTIONS = ["GE USM 35XDAC", "GE USM 36", "GE USM Go", "GE USM 100", "Sonatest WAVE"]

# ---------------------------------------------------------------------------
# Ambang batas acuan Liquid Penetrant Testing / PT (ASME Section V Article 6,
# ASTM E165 "Standard Practice for Liquid Penetrant Testing", dan ISO 3452
# series). Nilai di bawah adalah AMBANG UMUM/MINIMUM yang paling sering
# dipakai industri manufaktur baja — tabel ASME V T-672 punya angka spesifik
# per jenis material/cacat, jadi tetap CEK prosedur/WPS internal PT IHI untuk
# kasus khusus (mis. casting kompleks butuh dwell time lebih lama).
# ---------------------------------------------------------------------------
PT_MIN_DWELL_TIME_PENETRANT_MIN = 10    # Waktu tinggal (dwell) penetrant minimum, umum utk weld/casting
PT_MIN_DWELL_TIME_DEVELOPER_MIN = 10    # Waktu tinggal developer minimum sebelum boleh diinspeksi
PT_MIN_SURFACE_TEMP_C = 5.0             # 40°F — batas bawah suhu permukaan standard technique (ASME V T-652)
PT_MAX_SURFACE_TEMP_C = 52.0            # 125°F — batas atas suhu permukaan standard technique
PT_MIN_UV_INTENSITY_UWCM2 = 1000        # Intensitas UV-A minimum di permukaan utk fluorescent (ASTM E165)
PT_MAX_AMBIENT_LIGHT_FOR_FLUORESCENT_LUX = 20   # Cahaya tampak maksimum saat inspeksi fluorescent (harus gelap)
PT_MIN_VISIBLE_LIGHT_INTENSITY_LUX = 1000       # Intensitas cahaya tampak minimum utk visible dye penetrant
PT_PENETRANT_TYPE_OPTIONS = ["Visible Dye (Merah)", "Fluorescent"]
PT_CLEANING_METHOD_OPTIONS = ["Water Washable", "Post-Emulsifiable Lipophilic", "Post-Emulsifiable Hydrophilic", "Solvent Removable"]
PT_DEVELOPER_TYPE_OPTIONS = ["Dry Powder", "Wet Developer - Aqueous", "Wet Developer - Non-Aqueous (Solvent-Based)"]
PT_LIGHTING_METHOD_OPTIONS = ["UV-A (Black Light) - untuk Fluorescent", "Cahaya Putih (White Light) - untuk Visible Dye"]
PT_JOINT_TYPE_OPTIONS = ["Butt Joint", "Fillet Joint", "Tee Joint", "Corner Joint", "Lap Joint"]


def check_mt_lifting_power(lifting_power_kg: float):
    """Cek apakah lifting power yoke memenuhi syarat minimum AWS D1.1 (4.5 kg)."""
    ok = lifting_power_kg >= MT_MIN_LIFTING_POWER_KG
    return ok, MT_MIN_LIFTING_POWER_KG


def check_pt_dwell_time(dwell_penetrant_min: float, dwell_developer_min: float):
    """Cek apakah waktu tinggal (dwell time) penetrant & developer memenuhi
    minimum acuan ASME V / ASTM E165. Mengembalikan (ok_penetrant, ok_developer,
    min_penetrant, min_developer)."""
    ok_penetrant = dwell_penetrant_min >= PT_MIN_DWELL_TIME_PENETRANT_MIN
    ok_developer = dwell_developer_min >= PT_MIN_DWELL_TIME_DEVELOPER_MIN
    return ok_penetrant, ok_developer, PT_MIN_DWELL_TIME_PENETRANT_MIN, PT_MIN_DWELL_TIME_DEVELOPER_MIN


def check_pt_surface_temp(temp_c: float):
    """Cek apakah suhu permukaan saat tes PT dalam rentang standard technique
    ASME V (5°C - 52°C / 40°F - 125°F). Di luar rentang ini butuh teknik
    khusus (non-standard technique) yang harus dikualifikasi terpisah."""
    ok = PT_MIN_SURFACE_TEMP_C <= temp_c <= PT_MAX_SURFACE_TEMP_C
    return ok, PT_MIN_SURFACE_TEMP_C, PT_MAX_SURFACE_TEMP_C


def check_pt_light_intensity(jenis_penetrant: str, intensitas: float):
    """Cek apakah intensitas cahaya pemeriksaan memenuhi minimum acuan,
    tergantung jenis penetrant-nya (Fluorescent butuh UV-A min 1000 µW/cm²,
    Visible Dye butuh cahaya putih min 1000 lux). Mengembalikan
    (ok, min_required, satuan)."""
    if jenis_penetrant == "Fluorescent":
        return intensitas >= PT_MIN_UV_INTENSITY_UWCM2, PT_MIN_UV_INTENSITY_UWCM2, "µW/cm²"
    return intensitas >= PT_MIN_VISIBLE_LIGHT_INTENSITY_LUX, PT_MIN_VISIBLE_LIGHT_INTENSITY_LUX, "lux"


def get_spc_constants(n: int):
    """Ambil konstanta A3, B3, B4 untuk ukuran subgroup n. Fallback ke n terdekat jika tidak ada di tabel."""
    if n in SPC_CONSTANTS:
        return SPC_CONSTANTS[n]
    nearest = min(SPC_CONSTANTS.keys(), key=lambda k: abs(k - n))
    return SPC_CONSTANTS[nearest]


def xbar_s_chart(df: pd.DataFrame, sample_cols: list):
    """
    Hitung Xbar, S per baris (batch), serta UCL/LCL/CL untuk Xbar Chart dan S Chart.
    df: dataframe dengan kolom-kolom sampel numerik (mis. Sampel_1..Sampel_5)
    """
    n = len(sample_cols)
    A3, B3, B4 = get_spc_constants(n)

    xbar = df[sample_cols].mean(axis=1)
    s = df[sample_cols].std(axis=1, ddof=1)

    xbarbar = xbar.mean()
    sbar = s.mean()

    ucl_xbar = xbarbar + A3 * sbar
    lcl_xbar = xbarbar - A3 * sbar
    ucl_s = B4 * sbar
    lcl_s = B3 * sbar

    result = pd.DataFrame({
        "Xbar": xbar,
        "S": s,
    })
    limits = {
        "xbarbar": xbarbar, "sbar": sbar,
        "ucl_xbar": ucl_xbar, "lcl_xbar": lcl_xbar,
        "ucl_s": ucl_s, "lcl_s": lcl_s,
        "A3": A3, "B3": B3, "B4": B4, "n": n,
    }
    return result, limits


def p_chart(n_inspected: pd.Series, n_defect: pd.Series):
    """Hitung proporsi cacat (p) dan UCL/LCL dinamis per batch (n bisa berbeda-beda)."""
    p = n_defect / n_inspected
    pbar = n_defect.sum() / n_inspected.sum()
    ucl = pbar + 3 * np.sqrt(pbar * (1 - pbar) / n_inspected)
    lcl = (pbar - 3 * np.sqrt(pbar * (1 - pbar) / n_inspected)).clip(lower=0)

    result = pd.DataFrame({
        "p": p, "UCL": ucl, "LCL": lcl,
    })
    return result, pbar


def process_capability(values: pd.Series, lsl: float, usl: float):
    """Hitung Cp, Cpk, dan status kapabilitas proses."""
    mean = values.mean()
    sigma = values.std(ddof=1)

    cp = (usl - lsl) / (6 * sigma) if sigma > 0 else np.nan
    cpu = (usl - mean) / (3 * sigma) if sigma > 0 else np.nan
    cpl = (mean - lsl) / (3 * sigma) if sigma > 0 else np.nan
    cpk = min(cpu, cpl) if sigma > 0 else np.nan

    if cpk >= 1.33:
        status = "CAPABLE (Baik)"
    elif cpk >= 1.0:
        status = "MARGINAL (Perlu Perhatian)"
    else:
        status = "TIDAK CAPABLE (Perlu Perbaikan Segera)"

    return {
        "mean": mean, "sigma": sigma, "cp": cp, "cpu": cpu, "cpl": cpl,
        "cpk": cpk, "status": status,
    }


def calculate_dpmo(total_defect: int, total_unit: int, opportunities_per_unit: int = 1):
    """Hitung DPU, DPMO, dan Sigma Level (dengan shift 1.5 sigma)."""
    dpu = total_defect / total_unit
    dpmo = (total_defect / (total_unit * opportunities_per_unit)) * 1_000_000
    # Sigma level = Z(1 - DPMO/1e6) + 1.5 (konvensi long-term shift)
    p_good = max(min(1 - dpmo / 1_000_000, 0.9999999), 0.0000001)
    sigma_level = norm.ppf(p_good) + 1.5
    return {"dpu": dpu, "dpmo": dpmo, "sigma_level": sigma_level}


def classify_sigma_level(sigma_level: float):
    """Klasifikasikan sigma level ke kategori kualitas berdasarkan tabel acuan."""
    level_int = int(np.floor(sigma_level))
    level_int = max(1, min(level_int, 6))
    for lvl, dpmo_ref, kategori in SIGMA_BENCHMARK:
        if lvl == level_int:
            return level_int, dpmo_ref, kategori
    return level_int, None, "Tidak diketahui"
