# db_init.py
"""
Initialize meddonationn.db with correct schema and sample data.

- Uses ONLY this file, no extra helper scripts.
- Backs up any existing meddonationn.db to meddonationn.db.bak
- Creates tables:
    users, ngos, shelf_life, donations, audio_transcriptions, ngo_connections
- Seeds:
    * 5 NGOs
    * 5 shelf_life entries
    * 4 users (admin, ravi, sita, helping_user)
    * 10 pledged donations with Indian names and cities
"""

import sqlite3
from pathlib import Path
import hashlib
from datetime import datetime, timedelta
import random

DB = "meddonationn.db"


def hash_pw(pw: str, salt: str = "medsalt") -> str:
    return hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()


def ensure_db():
    db_path = Path(DB)

    # If DB already exists, back it up and recreate (so you get clean data)
    if db_path.exists():
        backup = db_path.with_suffix(".db.bak") if db_path.suffix == ".db" else Path(str(db_path) + ".bak")
        print(f"[db_init] Existing {db_path.name} found. Backing up to {backup.name}")
        if backup.exists():
            backup.unlink()
        db_path.replace(backup)

    print(f"[db_init] Creating fresh {DB} ...")
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # ---------- Create tables ----------
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            ngo_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS ngos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            city TEXT,
            contact TEXT,
            accepts TEXT
        );

        CREATE TABLE IF NOT EXISTS shelf_life (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT UNIQUE,
            shelf_months INTEGER,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_name TEXT,
            donor_city TEXT,
            medicine_name TEXT,
            batch_date TEXT,
            expiry_date TEXT,
            status TEXT,
            matched_ngo_id INTEGER,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS audio_transcriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            filepath TEXT,
            uploader TEXT,
            uploaded_at TEXT,
            transcription TEXT
        );

        CREATE TABLE IF NOT EXISTS ngo_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ngo_id INTEGER,
            donation_id INTEGER,
            message TEXT,
            created_at TEXT
        );
        """
    )
    conn.commit()

    # ---------- Seed NGOs ----------
    ngos = [
        ("Helping Hands Trust", "Bengaluru", "+91 9000000001", "paracetamol,ibuprofen"),
        ("Care for All", "Mumbai", "+91 9000000002", "vitamins,antibiotics"),
        ("Asha Foundation", "Hyderabad", "+91 9000000003", "antibiotics,paracetamol"),
        ("Sakhi NGO", "Chennai", "+91 9000000004", "vitamins,antiacids"),
        ("Janseva", "Delhi", "+91 9000000005", "paracetamol,antibiotics"),
    ]
    cur.executemany(
        "INSERT INTO ngos (name, city, contact, accepts) VALUES (?, ?, ?, ?)",
        ngos,
    )

    # ---------- Seed shelf_life ----------
    shelf_entries = [
        ("Paracetamol", 36, "Common painkiller"),
        ("Ibuprofen", 36, "NSAID"),
        ("Amoxicillin", 24, "Antibiotic"),
        ("Cough Syrup", 12, "Liquid formulation"),
        ("Multivitamin", 24, "Supplements"),
    ]
    cur.executemany(
        "INSERT INTO shelf_life (medicine_name, shelf_months, notes) VALUES (?, ?, ?)",
        shelf_entries,
    )

    # ---------- Seed users ----------
    users = [
        ("admin", "admin@123", "admin", None),
        ("ravi", "ravi@123", "donor", None),
        ("sita", "sita@123", "donor", None),
        ("helping_user", "help@123", "ngo", 1),
    ]
    cur.executemany(
        "INSERT INTO users (username, password_hash, role, ngo_id) VALUES (?, ?, ?, ?)",
        [(u, hash_pw(p), r, n) for (u, p, r, n) in users],
    )

    # ---------- Seed 10 pledged donations (Indian names, all pledged) ----------
    donor_names = [
        "Ravi",
        "Sita",
        "Amit",
        "Priya",
        "Karthik",
        "Meera",
        "Anil",
        "Nisha",
        "Vikram",
        "Lakshmi",
    ]
    cities = [
        "Bengaluru",
        "Mumbai",
        "Chennai",
        "Hyderabad",
        "Delhi",
        "Pune",
        "Kolkata",
        "Jaipur",
        "Ahmedabad",
        "Kochi",
    ]
    medicines = ["Paracetamol", "Ibuprofen", "Amoxicillin", "Cough Syrup", "Multivitamin"]

    now = datetime.now()
    donation_rows = []

    for i in range(10):
        dn = donor_names[i]
        city = cities[i]
        med = random.choice(medicines)

        # manufacture date: between 1 and 12 months ago
        mfg = (now - timedelta(days=30 * random.randint(1, 12))).date().isoformat()
        # expiry date: 1–3 years after mfg
        exp = (datetime.fromisoformat(mfg) + timedelta(days=365 * random.randint(1, 3))).date().isoformat()

        status = "pledged"
        ngo_id = random.randint(1, 5)
        created_at = (now - timedelta(days=random.randint(0, 60))).isoformat()

        donation_rows.append(
            (dn, city, med, mfg, exp, status, ngo_id, created_at)
        )

    cur.executemany(
        """
        INSERT INTO donations
            (donor_name, donor_city, medicine_name, batch_date, expiry_date, status, matched_ngo_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        donation_rows,
    )

    conn.commit()

    # small summary
    for table in ["users", "ngos", "shelf_life", "donations"]:
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"[db_init] {table} rows:", count)

    conn.close()
    print(f"[db_init] ✅ Finished creating fresh {DB}")


if __name__ == "__main__":
    ensure_db()
