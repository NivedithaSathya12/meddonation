# admin_utils.py
"""
Admin database utilities for meddonation (updated).
Provides:
- create_user / verify_user / get_user_by_username
- insert_ngo / update_ngo / get_all_ngos
- insert_shelf / get_all_shelf_life
- insert_donation / delete_donation / get_recent_donations
Notes:
- Uses sqlite file 'meddonation.db' in current working directory.
- Passwords are salted SHA-256 hashes (simple; for production use stronger methods).
"""

import sqlite3
from pathlib import Path
import hashlib
import pandas as pd
import os
from typing import Optional

DB_PATH = Path("meddonation.db")

def _connect():
    return sqlite3.connect(str(DB_PATH))

def _ensure_tables():
    """Create tables if they do not exist (safe to call repeatedly)."""
    conn = _connect()
    cur = conn.cursor()
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
    conn.commit()
    conn.close()

# ensure DB schema
_ensure_tables()

def hash_password(password: str, salt: str = "medsalt") -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

# ---------------- User functions ----------------
def create_user(username: str, password: str, role: str = "donor", ngo_id: Optional[int] = None) -> bool:
    """Create a user row. Returns True on success, False if username exists or error."""
    try:
        conn = _connect()
        cur = conn.cursor()
        ph = hash_password(password)
        cur.execute("INSERT INTO users (username, password_hash, role, ngo_id) VALUES (?, ?, ?, ?)",
                    (username, ph, role, ngo_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print("create_user error:", e)
        return False

def verify_user(username: str, password: str) -> Optional[dict]:
    """Verify credentials. Returns user dict (id, username, role, ngo_id) or None."""
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash, role, ngo_id FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        uid, phash, role, ngo_id = row
        if phash == hash_password(password):
            return {"id": uid, "username": username, "role": role, "ngo_id": ngo_id}
        return None
    except Exception as e:
        print("verify_user error:", e)
        return None

def get_user_by_username(username: str) -> Optional[dict]:
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT id, username, role, ngo_id FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {"id": row[0], "username": row[1], "role": row[2], "ngo_id": row[3]}
    except Exception as e:
        print("get_user_by_username error:", e)
    return None

# ---------------- NGO functions ----------------
def insert_ngo(name: str, city: str, contact: str, accepts: str) -> Optional[int]:
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO ngos (name, city, contact, accepts) VALUES (?, ?, ?, ?)",
                    (name, city, contact, accepts))
        nid = cur.lastrowid
        conn.commit()
        conn.close()
        return nid
    except Exception as e:
        print("insert_ngo error:", e)
        return None

def update_ngo(nid: int, name: str, city: str, contact: str, accepts: str) -> bool:
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("UPDATE ngos SET name=?, city=?, contact=?, accepts=? WHERE id=?", (name, city, contact, accepts, nid))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("update_ngo error:", e)
        return False

def get_all_ngos() -> pd.DataFrame:
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM ngos", conn)
        conn.close()
        return df
    except Exception as e:
        print("get_all_ngos error:", e)
        return pd.DataFrame(columns=["id","name","city","contact","accepts"])

# ---------------- Shelf-life ----------------
def insert_shelf(medicine_name: str, shelf_months: int, notes: str = "") -> bool:
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO shelf_life (medicine_name, shelf_months, notes) VALUES (?, ?, ?)",
                    (medicine_name.lower(), int(shelf_months), notes))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("insert_shelf error:", e)
        return False

def get_all_shelf_life() -> pd.DataFrame:
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM shelf_life", conn)
        conn.close()
        return df
    except Exception as e:
        print("get_all_shelf_life error:", e)
        return pd.DataFrame(columns=["id","medicine_name","shelf_months","notes"])

# ---------------- Donations ----------------
def insert_donation(donor_name: str, medicine_name: str, batch_date: str, expiry_date: str, status: str, matched_ngo_id: Optional[int]) -> bool:
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO donations (donor_name, medicine_name, batch_date, expiry_date, status, matched_ngo_id) VALUES (?, ?, ?, ?, ?, ?)",
            (donor_name, medicine_name, batch_date, expiry_date, status, matched_ngo_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("insert_donation error:", e)
        return False

def delete_donation(did: int) -> bool:
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM donations WHERE id=?", (did,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("delete_donation error:", e)
        return False

def get_recent_donations(limit: int = 500, filters: dict = None) -> pd.DataFrame:
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM donations ORDER BY id DESC LIMIT ?", conn, params=(limit,))
        conn.close()
        return df
    except Exception as e:
        print("get_recent_donations error:", e)
        return pd.DataFrame()

# ---------------- Utility (debug) ----------------
if __name__ == "__main__":
    print("admin_utils test run")
    print("DB path:", DB_PATH)
    print("NGOs sample:", get_all_ngos().head().to_dict(orient="records"))
    print("Shelf sample:", get_all_shelf_life().head().to_dict(orient="records"))
    try:
        import pandas as pd
        print("Users sample:", pd.read_sql_query("SELECT id,username,role,ngo_id FROM users LIMIT 10", _connect()).to_dict(orient="records"))
    except Exception:
        pass
