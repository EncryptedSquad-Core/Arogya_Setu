import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "arogya_setu.db")

def _ensure_valid_sqlite():
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "rb") as f:
                header = f.read(16)
            if len(header) > 0 and header != b"SQLite format 3\x00":
                os.remove(DB_PATH)
        except OSError:
            pass

def get_connection():
    _ensure_valid_sqlite()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn
    except sqlite3.DatabaseError:
        for ext in ("", "-wal", "-shm"):
            p = DB_PATH + ext
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        conn = sqlite3.connect(DB_PATH, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        phone TEXT DEFAULT '',
        locality TEXT DEFAULT '',
        lang TEXT DEFAULT 'en'
    );""")

    cur.execute("""CREATE TABLE IF NOT EXISTS scans (
        id TEXT PRIMARY KEY,
        owner_username TEXT NOT NULL,
        person TEXT NOT NULL,
        body_part TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        what_was_in_photo TEXT NOT NULL,
        identified_condition TEXT NOT NULL,
        causes TEXT NOT NULL,
        severity TEXT NOT NULL,
        confidence INTEGER NOT NULL,
        helpful_care TEXT NOT NULL
    );""")

    cur.execute("""CREATE TABLE IF NOT EXISTS appointments (
        id TEXT PRIMARY KEY,
        patient_username TEXT NOT NULL,
        patient_name TEXT NOT NULL,
        clinic_name TEXT NOT NULL,
        specialty TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        notes TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Confirmed'
    );""")

    cur.execute("""CREATE TABLE IF NOT EXISTS referrals (
        id TEXT PRIMARY KEY,
        patient_name TEXT NOT NULL,
        condition TEXT NOT NULL,
        urgency TEXT NOT NULL,
        hospital TEXT NOT NULL,
        referred_by TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active'
    );""")

    if cur.execute("SELECT COUNT(*) as c FROM users;").fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO users (username, password, full_name, role, phone, locality, lang) VALUES (?, ?, ?, ?, ?, ?, ?);",
            [
                ("arjun", "user123", "Arjun Rao", "user", "+91 98450 11223", "Bengaluru", "en"),
                ("kavitha", "worker123", "Kavitha Nair (PHC Nurse)", "worker", "+91 94481 22334", "Community Health Center", "kn"),
                ("ramesh", "admin123", "Dr. Ramesh Hegde (Admin)", "admin", "+91 99001 44556", "District Health Directorate", "en")
            ]
        )

    if cur.execute("SELECT COUNT(*) as c FROM scans;").fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO scans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            [
                (
                    "SCN-9012", "arjun", "Arjun Rao", "Arm / Forearm", "2026-10-18 09:15 AM",
                    "Skin surface showing a circular ring-shaped scaly patch",
                    "Tinea Corporis (Superficial Fungal Ringworm)",
                    "Dermatophyte fungi thriving in warm sweat and humidity",
                    "MILD", 92,
                    "Clotrimazole 1% Cream, Terbinafine 1% Ointment | Dermatology Advice: Consult a Dermatologist if ringworm persists beyond 10–14 days."
                ),
                (
                    "SCN-9015", "arjun", "Meenakshi S.", "Back / Torso", "2026-10-18 10:05 AM",
                    "Dark irregularly bordered pigmented lesion on skin",
                    "Atypical Pigmented Lesion / Suspected Melanocytic Dysplasia",
                    "Cumulative UV sun exposure or abnormal melanocyte growth",
                    "HIGH", 91,
                    "Urgent Dermatologist Evaluation & Dermoscopy Required Within 24–48 Hours"
                )
            ]
        )

    if cur.execute("SELECT COUNT(*) as c FROM appointments;").fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO appointments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                "APT-3011", "arjun", "Arjun Rao",
                "City Dermatology & Skin Care Clinic", "Dermatology",
                "2026-10-20", "10:30 AM",
                "Follow-up skin check after Smart Skin Lens scan.", "Confirmed"
            )
        )

    if cur.execute("SELECT COUNT(*) as c FROM referrals;").fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO referrals VALUES (?, ?, ?, ?, ?, ?, ?);",
            (
                "REF-501", "Meenakshi S.",
                "Atypical Pigmented Lesion / Suspected Melanocytic Dysplasia",
                "HIGH — Immediate Dermatologist Biopsy",
                "District General Hospital (Dermatology OPD)",
                "Kavitha Nair (PHC Nurse)", "Active"
            )
        )

    conn.commit()
    conn.close()
