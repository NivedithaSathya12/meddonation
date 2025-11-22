# db_init.py
import sqlite3
from pathlib import Path

DB = "meddonation.db"

def create_tables(conn):
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS shelf_life (
        id INTEGER PRIMARY KEY,
        medicine_name TEXT UNIQUE,
        shelf_months INTEGER,
        notes TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS ngos (
        id INTEGER PRIMARY KEY,
        name TEXT,
        city TEXT,
        contact TEXT,
        accepts TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS donations (
        id INTEGER PRIMARY KEY,
        donor_name TEXT,
        medicine_name TEXT,
        batch_date TEXT,
        expiry_date TEXT,
        status TEXT,
        matched_ngo_id INTEGER
    )
    """)

    conn.commit()

def seed_data(conn):
    c = conn.cursor()

    meds = [
        ("paracetamol", 36, "tablet"),
        ("amoxicillin", 24, "capsule"),
        ("cough syrup", 12, "liquid")
    ]

    for m, s, n in meds:
        c.execute("INSERT OR IGNORE INTO shelf_life (medicine_name, shelf_months, notes) VALUES (?, ?, ?)", (m, s, n))

    ngos = [
        ("CareRelief Bangalore", "Bangalore", "+91 99999 00000", "tablets"),
        ("RuralHealth Patna", "Patna", "+91 88888 11111", "all")
    ]

    for name, city, contact, accepts in ngos:
        c.execute("INSERT OR IGNORE INTO ngos (name, city, contact, accepts) VALUES (?, ?, ?, ?)",
                  (name, city, contact, accepts))

    conn.commit()

def ensure_db():
    db = Path(DB)
    conn = sqlite3.connect(db)
    create_tables(conn)
    seed_data(conn)
    conn.close()

if __name__ == "__main__":
    ensure_db()
    print("Database created/ensured.")
