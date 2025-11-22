# db_init.py
import sqlite3
from pathlib import Path
import hashlib
from datetime import datetime, timedelta

DB = "meddonation.db"

def hash_pw(pw, salt="medsalt"):
    return hashlib.sha256((salt+pw).encode("utf-8")).hexdigest()

def ensure_db():
    db_path = Path(DB)
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # create tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS shelf_life (
      id INTEGER PRIMARY KEY,
      medicine_name TEXT UNIQUE,
      shelf_months INTEGER,
      notes TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ngos (
      id INTEGER PRIMARY KEY,
      name TEXT,
      city TEXT,
      contact TEXT,
      accepts TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS donations (
      id INTEGER PRIMARY KEY,
      donor_name TEXT,
      medicine_name TEXT,
      batch_date TEXT,
      expiry_date TEXT,
      status TEXT,
      matched_ngo_id INTEGER
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY,
      username TEXT UNIQUE,
      password_hash TEXT,
      role TEXT,
      ngo_id INTEGER
    )""")

    # seed shelf_life if empty
    cur.execute("SELECT COUNT(*) FROM shelf_life")
    if cur.fetchone()[0] == 0:
        shelf_entries = [
            ("Paracetamol 500mg", 36, "Painkiller"),
            ("Amoxicillin 250mg", 24, "Antibiotic"),
            ("Ibuprofen 200mg", 36, "Anti-inflammatory"),
            ("Cetirizine 10mg", 48, "Anti-allergy"),
            ("Multivitamin", 36, "Supplement"),
            ("Cough Syrup", 12, "Liquid"),
            ("Vitamin C", 36, "Supplement"),
            ("Metformin 500mg", 24, "Diabetes"),
            ("Omeprazole 20mg", 36, "Acidity"),
            ("Aspirin 75mg", 36, "Heart health"),
            ("Zinc Tablets", 24, "Immunity"),
            ("ORS Pack", 12, "Hydration"),
            ("Amoxiclav", 24, "Antibiotic"),
            ("Dolo 650", 36, "Fever relief"),
            ("Azithromycin 500mg", 24, "Antibiotic"),
            ("Naproxen 250mg", 36, "Painkiller"),
            ("Saline Drops", 18, "Eye drops"),
            ("BP Tablet", 24, "Blood pressure"),
            ("Thyroid Tablet", 36, "Thyroid"),
            ("Iron Syrup", 12, "Supplement")
        ]
        cur.executemany("INSERT INTO shelf_life (medicine_name, shelf_months, notes) VALUES (?, ?, ?)", shelf_entries)

    # seed NGOs if empty
    cur.execute("SELECT COUNT(*) FROM ngos")
    if cur.fetchone()[0] == 0:
        ngo_entries = [
            ("Asha Trust","Bangalore","+91-900000001","tablets,liquids"),
            ("Seva NGO","Mumbai","+91-900000002","tablets"),
            ("Health Help","Chennai","+91-900000003","all"),
            ("Relief Care","Hyderabad","+91-900000004","tablets,ointments"),
            ("Grameen Aid","Patna","+91-900000005","tablets"),
            ("Hope Center","Delhi","+91-900000006","all"),
            ("Smile Group","Kolkata","+91-900000007","liquids"),
            ("Niramaya NGO","Jaipur","+91-900000008","tablets"),
            ("Ujjivan","Lucknow","+91-900000009","all"),
            ("Care India","Pune","+91-900000010","tablets")
        ]
        cur.executemany("INSERT INTO ngos (name, city, contact, accepts) VALUES (?, ?, ?, ?)", ngo_entries)

    # seed donations sample if empty
    cur.execute("SELECT COUNT(*) FROM donations")
    if cur.fetchone()[0] == 0:
        donor_names = ["Ravi","Sita","Amit","Priya","Manoj","Kiran","Deepa","Anand","Rupa","Vishal"]
        cur.execute("SELECT medicine_name FROM shelf_life LIMIT 20")
        meds = [r[0] for r in cur.fetchall()]
        for i in range(20):
            donor = donor_names[i % len(donor_names)]
            med = meds[i % len(meds)]
            mfg = (datetime.today() - timedelta(days=30*(i+1))).date().isoformat()
            expiry = (datetime.fromisoformat(mfg) + timedelta(days=365)).date().isoformat()
            status = "pledged"
            ngo_id = (i % 10) + 1
            cur.execute("INSERT INTO donations (donor_name, medicine_name, batch_date, expiry_date, status, matched_ngo_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (donor, med, mfg, expiry, status, ngo_id))

    # seed users if empty (admin + ngo1..ngo10)
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO users (username, password_hash, role, ngo_id) VALUES (?, ?, ?, ?)",
                    ("admin", hash_pw("Admin@123"), "admin", None))
        for i in range(1, 11):
            uname = f"ngo{i}"
            cur.execute("INSERT INTO users (username, password_hash, role, ngo_id) VALUES (?, ?, ?, ?)",
                        (uname, hash_pw("Ngo@1234"), "ngo", i))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    ensure_db()
    print("meddonation.db created/verified")
