# admin_utils.py
"""
Database helper utilities for meddonation app.
Keeps functions for user management, NGO management, donations, and shelf-life.
Uses sqlite3 and pandas for simple operations.
"""

import sqlite3
from pathlib import Path
import hashlib
import pandas as pd

DB_PATH = Path("meddonation.db")

def _connect():
    return sqlite3.connect(str(DB_PATH))

def hash_password(password: str, salt: str = "medsalt") -> str:
    """Return sha256(salt+password) hex digest."""
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

# ---------------- User helpers ----------------
def create_user(username: str, password: str, role: str = "donor", ngo_id: int = None) -> bool:
    """Create a user; returns True on success, False if username exists or error."""
    try:
        conn = _connect()
        cur = conn.cursor()
        ph = hash_password(password)
        cur.execute(
            "INSERT INTO users (username, password_hash, role, ngo_id) VALUES (?, ?, ?, ?)",
            (username, ph, role, ngo_id)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print("create_user error:", e)
        return False

def verify_user(username: str, password: str):
    """Verify username/password. Returns user dict or None."""
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

def get_user_by_username(username: str):
    """Return user dict without password (or None)."""
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

# ---------------- NGO helpers ----------------
def insert_ngo(name, city, contact, accepts):
    """Insert NGO row and return new id, or None on error."""
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

def update_ngo(nid, name, city, contact, accepts):
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

def get_all_ngos():
    """Return pandas DataFrame of all NGOs (id, name, city, contact, accepts)."""
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM ngos", conn)
        conn.close()
        return df
    except Exception as e:
        print("get_all_ngos error:", e)
        return pd.DataFrame(columns=["id","name","city","contact","accepts"])

# ---------------- Shelf-life helpers ----------------
def insert_shelf(medicine_name: str, shelf_months: int, notes: str = ""):
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

def get_all_shelf_life():
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM shelf_life", conn)
        conn.close()
        return df
    except Exception as e:
        print("get_all_shelf_life error:", e)
        return pd.DataFrame(columns=["id","medicine_name","shelf_months","notes"])

# ---------------- Donation helpers ----------------
def insert_donation(donor_name, medicine_name, batch_date, expiry_date, status, matched_ngo_id):
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

def delete_donation(did):
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

def get_recent_donations(limit=500, filters=None):
    """
    Return pandas DataFrame of recent donations. 'filters' is a dict but kept simple.
    """
    try:
        conn = _connect()
        query = "SELECT * FROM donations ORDER BY id DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=(limit,))
        conn.close()
        return df
    except Exception as e:
        print("get_recent_donations error:", e)
        return pd.DataFrame()

# ---------------- Utility: print small summary ----------------
if __name__ == "__main__":
    print("Tables preview:")
    print("NGOs:", get_all_ngos().head().to_dict(orient="records"))
    print("Shelf:", get_all_shelf_life().head().to_dict(orient="records"))
    print("Users sample:", pd.read_sql_query("SELECT id,username,role,ngo_id FROM users LIMIT 10", _connect()).to_dict(orient="records"))
