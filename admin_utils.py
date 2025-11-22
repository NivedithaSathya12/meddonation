# admin_utils.py
"""
Database helper functions for admin UI.
All queries are parameterized and exceptions are logged to app.log.
Returns pandas.DataFrame for display when appropriate.
"""

import sqlite3
import pandas as pd
import logging
from pathlib import Path

DB = "meddonation.db"

# Setup logger
logger = logging.getLogger("meddonation_admin")
if not logger.handlers:
    fh = logging.FileHandler("app.log")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(fh)


def _connect():
    # Ensure DB file exists in current working dir
    db_file = Path(DB)
    conn = sqlite3.connect(str(db_file))
    return conn


def get_recent_donations(limit=100, filters=None):
    """
    Return recent donations as pandas.DataFrame.
    - limit: maximum rows
    - filters: dict with optional substrings: donor_name, medicine_name, city
    """
    try:
        conn = _connect()
        base = (
            "SELECT d.id, d.donor_name, d.medicine_name, d.batch_date, "
            "d.expiry_date, d.status, d.matched_ngo_id, n.name as ngo_name, n.city as ngo_city "
            "FROM donations d LEFT JOIN ngos n ON d.matched_ngo_id = n.id"
        )

        clauses = []
        params = []
        if filters:
            donor = filters.get("donor_name")
            if donor:
                clauses.append("LOWER(d.donor_name) LIKE ?")
                params.append(f"%{donor.lower()}%")
            med = filters.get("medicine_name")
            if med:
                clauses.append("LOWER(d.medicine_name) LIKE ?")
                params.append(f"%{med.lower()}%")
            city = filters.get("city")
            if city:
                clauses.append("LOWER(n.city) LIKE ?")
                params.append(f"%{city.lower()}%")

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"{base}{where} ORDER BY d.id DESC LIMIT ?"
        params.append(limit)

        df = pd.read_sql_query(sql, conn, params=params)
        conn.close()

        # Ensure columns exist and convert None to empty strings for display
        for c in ["batch_date", "expiry_date", "status", "ngo_name", "ngo_city"]:
            if c in df.columns:
                df[c] = df[c].fillna("")

        return df

    except Exception:
        logger.exception("get_recent_donations failed")
        return pd.DataFrame()


def get_all_ngos():
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM ngos ORDER BY id", conn)
        conn.close()
        return df
    except Exception:
        logger.exception("get_all_ngos failed")
        return pd.DataFrame()


def get_all_shelf_life():
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM shelf_life ORDER BY id", conn)
        conn.close()
        return df
    except Exception:
        logger.exception("get_all_shelf_life failed")
        return pd.DataFrame()


def insert_ngo(name, city, contact, accepts):
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ngos (name, city, contact, accepts) VALUES (?, ?, ?, ?)",
            (name, city, contact, accepts),
        )
        conn.commit()
        nid = cur.lastrowid
        conn.close()
        return nid
    except Exception:
        logger.exception("insert_ngo failed")
        return False


def update_ngo(nid, name, city, contact, accepts):
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE ngos SET name=?, city=?, contact=?, accepts=? WHERE id=?",
            (name, city, contact, accepts, nid),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        logger.exception("update_ngo failed")
        return False


def insert_shelf(medicine_name, shelf_months, notes):
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO shelf_life (medicine_name, shelf_months, notes) VALUES (?, ?, ?)",
            (medicine_name.lower(), int(shelf_months), notes),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        logger.exception("insert_shelf failed")
        return False


def delete_donation(did):
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM donations WHERE id=?", (did,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        logger.exception("delete_donation failed")
        return False


def insert_donation(donor, medicine, batch_date, expiry_date, status, ngo_id):
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO donations (donor_name, medicine_name, batch_date, expiry_date, status, matched_ngo_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (donor, medicine, batch_date, expiry_date, status, ngo_id),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        logger.exception("insert_donation failed")
        return False
import hashlib

def hash_password(password, salt="medsalt"):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def create_user(username, password, role="donor", ngo_id=None):
    try:
        conn = _connect()
        cur = conn.cursor()
        ph = hash_password(password)
        cur.execute("INSERT INTO users (username, password_hash, role, ngo_id) VALUES (?, ?, ?, ?)",
                    (username, ph, role, ngo_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        logger.exception("create_user failed")
        return False

def verify_user(username, password):
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
    except Exception:
        logger.exception("verify_user failed")
        return None

def get_user_by_username(username):
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM users WHERE username=?", conn, params=(username,))
        conn.close()
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception:
        logger.exception("get_user_by_username failed")
        return None
