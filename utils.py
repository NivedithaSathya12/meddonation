# utils.py
import sqlite3
from datetime import datetime, timedelta
import logging

DB = "meddonation.db"

logger = logging.getLogger("utils")
if not logger.handlers:
    handler = logging.FileHandler("app.log")
    logger.addHandler(handler)

def get_shelf_info(med_name):
    try:
        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute("SELECT shelf_months, notes FROM shelf_life WHERE medicine_name = ?", (med_name.lower(),))
        r = cur.fetchone()
        con.close()
        return r
    except:
        logger.exception("Shelf info error")
        return None

def is_donation_allowed(medicine, mfg_date, expiry_date=None, threshold=180):
    today = datetime.today().date()

    if expiry_date:
        try:
            exp = datetime.fromisoformat(expiry_date).date()
        except:
            return {"allowed": False, "reason": "Invalid expiry format.", "days_left": None}

        days = (exp - today).days
        if days > threshold:
            return {"allowed": True, "reason": "Eligible based on printed expiry.", "days_left": days}
        return {"allowed": False, "reason": "Too close to expiry.", "days_left": days}

    # Use shelf life
    shelf = get_shelf_info(medicine)
    if not shelf:
        return {"allowed": False, "reason": "No shelf-life reference.", "days_left": None}

    mfg = datetime.fromisoformat(mfg_date).date()
    approx_exp = mfg + timedelta(days=30 * shelf[0])
    days_left = (approx_exp - today).days

    if days_left >= threshold:
        return {"allowed": True, "reason": "Eligible based on shelf life.", "days_left": days_left}
    return {"allowed": False, "reason": "Too close to expiry.", "days_left": days_left}
