"""
Indonesian Test Data for Benchmark Corpus.

Contains realistic Indonesian:
- Names (various ethnic backgrounds)
- Addresses
- ID numbers (NIK, NPWP, KK, BPJS)
- Phone numbers
- Company names (for negative examples)

All data is synthetic - no real PII.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal


# ============== Indonesian Names ==============

@dataclass
class IndonesianName:
    """Indonesian name with metadata."""
    full_name: str
    ethnicity: str
    has_title: bool = False
    title: str = ""

    @property
    def display_name(self) -> str:
        if self.has_title and self.title:
            return f"{self.title} {self.full_name}"
        return self.full_name


# Javanese names
JAVANESE_NAMES = [
    IndonesianName("Budi Santoso", "javanese"),
    IndonesianName("Siti Rahayu", "javanese"),
    IndonesianName("Agus Wijaya", "javanese"),
    IndonesianName("Sri Wahyuni", "javanese"),
    IndonesianName("Dwi Prasetyo", "javanese"),
    IndonesianName("Tri Handayani", "javanese"),
    IndonesianName("Eko Purnomo", "javanese"),
    IndonesianName("Wati Sulistyowati", "javanese"),
    IndonesianName("Bambang Sudrajat", "javanese"),
    IndonesianName("Endang Kusumawati", "javanese"),
]

# Sundanese names
SUNDANESE_NAMES = [
    IndonesianName("Asep Supriatna", "sundanese"),
    IndonesianName("Neng Komariah", "sundanese"),
    IndonesianName("Dede Kurniawan", "sundanese"),
    IndonesianName("Euis Kartini", "sundanese"),
    IndonesianName("Ujang Hermawan", "sundanese"),
    IndonesianName("Teti Sumiati", "sundanese"),
    IndonesianName("Cecep Hidayat", "sundanese"),
    IndonesianName("Yayah Rohayati", "sundanese"),
]

# Batak names
BATAK_NAMES = [
    IndonesianName("Johannes Sitorus", "batak"),
    IndonesianName("Maria Siahaan", "batak"),
    IndonesianName("Parlindungan Simanjuntak", "batak"),
    IndonesianName("Rosmawati Situmorang", "batak"),
    IndonesianName("Hotman Panjaitan", "batak"),
    IndonesianName("Tiurma Nababan", "batak"),
    IndonesianName("Mangasi Siregar", "batak"),
    IndonesianName("Debora Hutapea", "batak"),
]

# Minangkabau names
MINANG_NAMES = [
    IndonesianName("Rahmad Hidayat", "minang"),
    IndonesianName("Yuliana Putri", "minang"),
    IndonesianName("Darmansyah", "minang"),
    IndonesianName("Nurhasanah", "minang"),
    IndonesianName("Zulkifli Nasution", "minang"),
    IndonesianName("Elvi Sukaesih", "minang"),
]

# Chinese-Indonesian names
CHINESE_INDONESIAN_NAMES = [
    IndonesianName("William Tanujaya", "chinese"),
    IndonesianName("Melissa Wijaya", "chinese"),
    IndonesianName("Steven Halim", "chinese"),
    IndonesianName("Jessica Lim", "chinese"),
    IndonesianName("Anthony Susanto", "chinese"),
    IndonesianName("Natasha Tanuwijaya", "chinese"),
    IndonesianName("Kevin Gunawan", "chinese"),
    IndonesianName("Olivia Salim", "chinese"),
]

# Arabic-influenced names
ARABIC_NAMES = [
    IndonesianName("Muhammad Rizky", "arabic"),
    IndonesianName("Fatimah Azzahra", "arabic"),
    IndonesianName("Ahmad Fauzi", "arabic"),
    IndonesianName("Aisyah Putri", "arabic"),
    IndonesianName("Abdullah Rahman", "arabic"),
    IndonesianName("Khadijah Sari", "arabic"),
]

# Names with titles
TITLED_NAMES = [
    IndonesianName("Sutrisno", "javanese", True, "Dr."),
    IndonesianName("Bambang Suryadi", "javanese", True, "Ir."),
    IndonesianName("Siti Aminah", "javanese", True, "Hj."),
    IndonesianName("Ahmad Basuki", "arabic", True, "H."),
    IndonesianName("Maria Sumarni", "javanese", True, "drg."),
    IndonesianName("Budi Hartono", "javanese", True, "Prof. Dr."),
    IndonesianName("Dewi Anggraini", "javanese", True, "dr."),
]

# All names combined
INDONESIAN_NAMES = (
    JAVANESE_NAMES +
    SUNDANESE_NAMES +
    BATAK_NAMES +
    MINANG_NAMES +
    CHINESE_INDONESIAN_NAMES +
    ARABIC_NAMES +
    TITLED_NAMES
)


# ============== Indonesian Addresses ==============

INDONESIAN_ADDRESSES = [
    "Jl. Sudirman No. 45, Jakarta Pusat",
    "Jl. Gatot Subroto Kav. 12, Jakarta Selatan",
    "Jl. Thamrin No. 10, Jakarta Pusat",
    "Jl. Rasuna Said Blok X-5, Kuningan, Jakarta",
    "Jl. Pahlawan No. 88, Surabaya",
    "Jl. Asia Afrika No. 100, Bandung",
    "Jl. Malioboro No. 52, Yogyakarta",
    "Jl. Diponegoro No. 35, Semarang",
    "Jl. Ahmad Yani No. 77, Medan",
    "Jl. Imam Bonjol No. 21, Denpasar",
    "Perumahan Griya Asri Blok A-15, Bekasi",
    "Komplek Taman Sari No. 8, Tangerang",
    "Apartemen Sudirman Park Tower A Lt. 25, Jakarta",
]


# ============== Company Names (Negative Examples) ==============

COMPANY_NAMES = [
    "PT Budi Makmur Sejahtera",
    "CV Putra Jaya Abadi",
    "PT Sinar Mas Agro",
    "PT Astra International Tbk",
    "PT Bank Central Asia Tbk",
    "CV Maju Bersama",
    "PT Telekomunikasi Indonesia",
    "PT Pertamina (Persero)",
    "PT Indofood Sukses Makmur",
    "PT Unilever Indonesia",
    "Yayasan Budi Luhur",
    "Koperasi Simpan Pinjam Sejahtera",
    "PT Garuda Indonesia (Persero)",
    "PT Wijaya Karya (Persero)",
]


# ============== Province Codes for NIK ==============

PROVINCE_CODES = {
    "11": "Aceh",
    "12": "Sumatera Utara",
    "13": "Sumatera Barat",
    "14": "Riau",
    "15": "Jambi",
    "16": "Sumatera Selatan",
    "17": "Bengkulu",
    "18": "Lampung",
    "19": "Bangka Belitung",
    "21": "Kepulauan Riau",
    "31": "DKI Jakarta",
    "32": "Jawa Barat",
    "33": "Jawa Tengah",
    "34": "DI Yogyakarta",
    "35": "Jawa Timur",
    "36": "Banten",
    "51": "Bali",
    "52": "NTB",
    "53": "NTT",
    "61": "Kalimantan Barat",
    "62": "Kalimantan Tengah",
    "63": "Kalimantan Selatan",
    "64": "Kalimantan Timur",
    "65": "Kalimantan Utara",
    "71": "Sulawesi Utara",
    "72": "Sulawesi Tengah",
    "73": "Sulawesi Selatan",
    "74": "Sulawesi Tenggara",
    "75": "Gorontalo",
    "76": "Sulawesi Barat",
    "81": "Maluku",
    "82": "Maluku Utara",
    "91": "Papua Barat",
    "94": "Papua",
}


# ============== ID Number Generators ==============

def generate_nik(
    province: str | None = None,
    gender: Literal["M", "F"] | None = None,
    seed: int | None = None,
) -> str:
    """
    Generate a synthetic NIK (16 digits).

    Format: PPKKCC-DDMMYY-SSSS
    - PP: Province code
    - KK: City/Regency code
    - CC: District code
    - DDMMYY: Birth date (female adds 40 to DD)
    - SSSS: Sequence number
    """
    if seed is not None:
        random.seed(seed)

    # Province code
    if province:
        prov = province
    else:
        prov = random.choice(list(PROVINCE_CODES.keys()))

    # City and district codes (random valid-looking)
    city = f"{random.randint(1, 99):02d}"
    district = f"{random.randint(1, 99):02d}"

    # Birth date
    day = random.randint(1, 28)
    if gender == "F":
        day += 40  # Female indicator
    elif gender is None and random.random() > 0.5:
        day += 40

    month = random.randint(1, 12)
    year = random.randint(50, 99)  # 1950-1999

    # Sequence number
    seq = random.randint(1, 9999)

    return f"{prov}{city}{district}{day:02d}{month:02d}{year:02d}{seq:04d}"


def generate_npwp(
    format_type: Literal["new", "legacy", "formatted"] = "new",
    seed: int | None = None,
) -> str:
    """
    Generate a synthetic NPWP.

    Formats:
    - new: 16 digits (can be same as NIK)
    - legacy: 15 digits (XX.XXX.XXX.X-XXX.XXX)
    - formatted: With dots and dashes
    """
    if seed is not None:
        random.seed(seed)

    if format_type == "new":
        # 16-digit format (like NIK)
        return generate_nik(seed=seed)
    else:
        # Legacy 15-digit format
        part1 = f"{random.randint(1, 99):02d}"
        part2 = f"{random.randint(0, 999):03d}"
        part3 = f"{random.randint(0, 999):03d}"
        part4 = f"{random.randint(0, 9)}"
        part5 = f"{random.randint(0, 999):03d}"
        part6 = f"{random.randint(0, 999):03d}"

        if format_type == "formatted":
            return f"{part1}.{part2}.{part3}.{part4}-{part5}.{part6}"
        else:
            return f"{part1}{part2}{part3}{part4}{part5}{part6}"


def generate_kk(seed: int | None = None) -> str:
    """Generate a synthetic KK (Kartu Keluarga) number - 16 digits."""
    return generate_nik(seed=seed)  # Same format as NIK


def generate_bpjs(seed: int | None = None) -> str:
    """Generate a synthetic BPJS number - 13 digits."""
    if seed is not None:
        random.seed(seed)
    return f"{random.randint(0, 9999999999999):013d}"


def generate_phone(
    format_type: Literal["local", "intl", "formatted"] = "local",
    seed: int | None = None,
) -> str:
    """
    Generate a synthetic Indonesian phone number.

    Formats:
    - local: 08XXXXXXXXX
    - intl: +628XXXXXXXXX
    - formatted: 0812-3456-7890
    """
    if seed is not None:
        random.seed(seed)

    # Operator prefixes
    prefixes = ["811", "812", "813", "821", "822", "852", "853", "857", "858"]
    prefix = random.choice(prefixes)
    number = f"{random.randint(0, 99999999):08d}"

    if format_type == "intl":
        return f"+62{prefix}{number}"
    elif format_type == "formatted":
        full = f"0{prefix}{number}"
        return f"{full[:4]}-{full[4:8]}-{full[8:]}"
    else:
        return f"0{prefix}{number}"


def generate_email(name: str, domain: str | None = None, seed: int | None = None) -> str:
    """Generate a synthetic email address."""
    if seed is not None:
        random.seed(seed)

    domains = domain or random.choice([
        "gmail.com", "yahoo.co.id", "hotmail.com",
        "email.com", "outlook.com", "company.co.id",
    ])

    # Clean name for email
    clean = name.lower().replace(" ", ".").replace(".", "")
    clean = "".join(c for c in clean if c.isalnum() or c == ".")

    return f"{clean}@{domains}"


# ============== Document Templates ==============

def get_random_name(ethnicity: str | None = None) -> IndonesianName:
    """Get a random Indonesian name, optionally filtered by ethnicity."""
    if ethnicity:
        filtered = [n for n in INDONESIAN_NAMES if n.ethnicity == ethnicity]
        return random.choice(filtered) if filtered else random.choice(INDONESIAN_NAMES)
    return random.choice(INDONESIAN_NAMES)


def get_random_address() -> str:
    """Get a random Indonesian address."""
    return random.choice(INDONESIAN_ADDRESSES)


def get_random_company() -> str:
    """Get a random company name (for negative examples)."""
    return random.choice(COMPANY_NAMES)


__all__ = [
    # Name data
    "IndonesianName",
    "INDONESIAN_NAMES",
    "JAVANESE_NAMES",
    "SUNDANESE_NAMES",
    "BATAK_NAMES",
    "MINANG_NAMES",
    "CHINESE_INDONESIAN_NAMES",
    "ARABIC_NAMES",
    "TITLED_NAMES",
    # Address data
    "INDONESIAN_ADDRESSES",
    # Company names (negatives)
    "COMPANY_NAMES",
    # Province codes
    "PROVINCE_CODES",
    # Generators
    "generate_nik",
    "generate_npwp",
    "generate_kk",
    "generate_bpjs",
    "generate_phone",
    "generate_email",
    # Helpers
    "get_random_name",
    "get_random_address",
    "get_random_company",
]
