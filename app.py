# app.py
"""
Streamlit Medicine Donation Assistant - updated (no playsound / no pyttsx3)
- Uses gTTS + st.audio for client-side playback
- Auto-initializes DB via db_init.py (if missing)
- Open registration for Donors and NGOs
- Admin / NGO / Donor roles supported
- Safe, minimal dependencies for deployment
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime
import tempfile
import streamlit as st
import pandas as pd

# Ensure DB exists (db_init.py should be present in project)
if not os.path.exists("meddonation.db"):
    try:
        import db_init
        db_init.ensure_db()
    except Exception as e:
        st.error("Failed to initialize DB (db_init.py missing or error): " + str(e))
        st.stop()

# --------------------------- Audio helper (gTTS -> st.audio) ---------------------------
def tts_to_bytes(text: str, lang: str = "en"):
    """
    Use gTTS to create an mp3 temporarily, read bytes and return them.
    Returns bytes or None on failure.
    """
    try:
        from gtts import gTTS
    except Exception as e:
        # gTTS not available
        return None

    try:
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tf.close()
        tts = gTTS(text=text, lang=(lang.split("-")[0] if "-" in lang else lang))
        tts.save(tf.name)
        with open(tf.name, "rb") as f:
            audio_bytes = f.read()
        try:
            os.remove(tf.name)
        except:
            pass
        return audio_bytes
    except Exception as e:
        # fallback: return None
        return None

# --------------------------- DB helpers (use admin_utils if present) ---------------------------
try:
    import admin_utils
    _HAS_ADMIN_UTILS = True
except Exception:
    _HAS_ADMIN_UTILS = False

def _connect(db_path="meddonation.db"):
    return sqlite3.connect(db_path)

def hash_password(password: str, salt: str = "medsalt") -> str:
    import hashlib
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def create_user(username: str, password: str, role: str = "donor", ngo_id: int = None) -> bool:
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

def get_user_by_username(username: str):
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

def insert_ngo(name, city, contact, accepts):
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO ngos (name, city, contact, accepts) VALUES (?, ?, ?, ?)",
                    (name, city, contact, accepts))
        conn.commit()
        nid = cur.lastrowid
        conn.close()
        return nid
    except Exception as e:
        print("insert_ngo error:", e)
        return None

def get_all_ngos_df():
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM ngos", conn)
        conn.close()
        return df
    except Exception as e:
        print("get_all_ngos_df error:", e)
        return pd.DataFrame(columns=["id","name","city","contact","accepts"])

def get_shelf_df():
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM shelf_life", conn)
        conn.close()
        return df
    except Exception as e:
        print("get_shelf_df error:", e)
        return pd.DataFrame(columns=["id","medicine_name","shelf_months","notes"])

def get_donations_df(limit=500):
    try:
        conn = _connect()
        df = pd.read_sql_query("SELECT * FROM donations ORDER BY id DESC LIMIT ?", conn, params=(limit,))
        conn.close()
        return df
    except Exception as e:
        print("get_donations_df error:", e)
        return pd.DataFrame()

def insert_donation(donor_name, medicine_name, batch_date, expiry_date, status, matched_ngo_id):
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO donations (donor_name, medicine_name, batch_date, expiry_date, status, matched_ngo_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (donor_name, medicine_name, batch_date, expiry_date, status, matched_ngo_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("insert_donation error:", e)
        return False

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

# wrapper to use admin_utils when available
def AU_create_user(username, password, role="donor", ngo_id=None):
    if _HAS_ADMIN_UTILS and hasattr(admin_utils, "create_user"):
        return admin_utils.create_user(username, password, role, ngo_id)
    return create_user(username, password, role, ngo_id)

def AU_get_user(username):
    if _HAS_ADMIN_UTILS and hasattr(admin_utils, "get_user_by_username"):
        return admin_utils.get_user_by_username(username)
    return get_user_by_username(username)

def AU_insert_ngo(name, city, contact, accepts):
    if _HAS_ADMIN_UTILS and hasattr(admin_utils, "insert_ngo"):
        return admin_utils.insert_ngo(name, city, contact, accepts)
    return insert_ngo(name, city, contact, accepts)

def AU_get_all_ngos():
    if _HAS_ADMIN_UTILS and hasattr(admin_utils, "get_all_ngos"):
        return admin_utils.get_all_ngos()
    return get_all_ngos_df()

def AU_get_shelf():
    if _HAS_ADMIN_UTILS and hasattr(admin_utils, "get_all_shelf_life"):
        return admin_utils.get_all_shelf_life()
    return get_shelf_df()

def AU_get_donations(limit=500):
    if _HAS_ADMIN_UTILS and hasattr(admin_utils, "get_recent_donations"):
        return admin_utils.get_recent_donations(limit=limit, filters={})
    return get_donations_df(limit=limit)

def AU_insert_donation(*args, **kwargs):
    if _HAS_ADMIN_UTILS and hasattr(admin_utils, "insert_donation"):
        return admin_utils.insert_donation(*args, **kwargs)
    return insert_donation(*args, **kwargs)

def AU_update_ngo(*args, **kwargs):
    if _HAS_ADMIN_UTILS and hasattr(admin_utils, "update_ngo"):
        return admin_utils.update_ngo(*args, **kwargs)
    return update_ngo(*args, **kwargs)

def AU_delete_donation(did):
    if _HAS_ADMIN_UTILS and hasattr(admin_utils, "delete_donation"):
        return admin_utils.delete_donation(did)
    return delete_donation(did)

# --------------------------- Streamlit UI ---------------------------
st.set_page_config(page_title="Medicine Donation Assistant", page_icon="💊", layout="wide")
st.title("💊 Medicine Donation Assistant")
st.write("Donate medicines, check expiry, register NGOs & donors. (No playsound/pyttsx3 required)")

# session defaults
if "user" not in st.session_state:
    st.session_state["user"] = None
if "show_change_pw" not in st.session_state:
    st.session_state["show_change_pw"] = False

# ---------- Sidebar: login + registration ----------
with st.sidebar:
    st.header("Login")
    st.text_input("Username", key="login_username")
    st.text_input("Password", key="login_password", type="password")
    if st.button("Login"):
        uname = st.session_state.get("login_username","").strip()
        pwd = st.session_state.get("login_password","")
        if not uname or not pwd:
            st.warning("Enter username & password")
        else:
            user = AU_get_user(uname)
            if not user:
                st.error("Invalid username or password.")
            else:
                # verify password
                conn = _connect()
                cur = conn.cursor()
                cur.execute("SELECT password_hash FROM users WHERE username=?", (uname,))
                row = cur.fetchone()
                conn.close()
                if row and row[0] == hash_password(pwd):
                    st.success(f"Logged in as {uname} ({user['role']})")
                    st.session_state["user"] = user
                    st.experimental_rerun()
                else:
                    st.error("Invalid username or password.")

    st.markdown("---")
    st.header("Register")
    reg_type = st.radio("Register as:", ["Donor", "NGO"])
    if reg_type == "Donor":
        d_un = st.text_input("Username (Donor)", key="reg_d_un")
        d_pw = st.text_input("Password (Donor)", type="password", key="reg_d_pw")
        if st.button("Register Donor"):
            if not d_un or not d_pw:
                st.error("Enter username & password.")
            elif AU_get_user(d_un):
                st.error("Username already exists.")
            else:
                ok = AU_create_user(d_un.strip(), d_pw.strip(), role="donor", ngo_id=None)
                if ok:
                    st.success("Donor account created. Please login.")
                else:
                    st.error("Registration failed.")
    else:
        n_name = st.text_input("NGO name", key="reg_ngo_name")
        n_city = st.text_input("City", key="reg_ngo_city")
        n_contact = st.text_input("Contact", key="reg_ngo_contact")
        n_accepts = st.text_input("Accepts (comma-separated)", key="reg_ngo_accepts")
        n_un = st.text_input("Username (NGO)", key="reg_ngo_un")
        n_pw = st.text_input("Password (NGO)", type="password", key="reg_ngo_pw")
        if st.button("Register NGO"):
            if not n_name.strip() or not n_un.strip() or not n_pw.strip():
                st.error("Please enter NGO name, username and password.")
            elif AU_get_user(n_un.strip()):
                st.error("Username already exists.")
            else:
                nid = AU_insert_ngo(n_name.strip(), n_city.strip(), n_contact.strip(), n_accepts.strip())
                if nid:
                    ok = AU_create_user(n_un.strip(), n_pw.strip(), role="ngo", ngo_id=int(nid))
                    if ok:
                        st.success("NGO registered. Please login.")
                    else:
                        st.error("Failed to create user for NGO.")
                else:
                    st.error("Failed to create NGO row.")

    st.markdown("---")
    if st.session_state["user"]:
        st.write("Logged in as:", st.session_state["user"]["username"])
        if st.button("Logout"):
            st.session_state["user"] = None
            st.experimental_rerun()
        if st.button("Change Password"):
            st.session_state["show_change_pw"] = True

# ---------- Top metrics ----------
ngos_df = AU_get_all_ngos()
shelf_df = AU_get_shelf()
don_df = AU_get_donations(limit=1000)
col1, col2, col3 = st.columns(3)
col1.metric("NGOs", len(ngos_df))
col2.metric("Shelf items", len(shelf_df))
col3.metric("Donations", len(don_df))

st.write("---")

# ---------- Public donation form ----------
st.header("Donate a Medicine (Public)")
with st.form("donate_form"):
    donor_name = st.text_input("Your name")
    donor_city = st.text_input("Your city (for NGO matching)")
    medicine = st.text_input("Medicine name (e.g., Paracetamol 500mg)")
    mfg_date = st.date_input("Manufacture / Purchase date", value=datetime.today())
    printed_expiry = st.text_input("Printed expiry (optional, YYYY-MM-DD)")
    prefer = st.selectbox("Prefer NGO (optional)", options=["(Any)"] + ngos_df["name"].tolist())
    sub = st.form_submit_button("Check & Submit")
if sub:
    if not donor_name.strip() or not medicine.strip():
        st.error("Provide your name and medicine.")
    else:
        expiry_text = printed_expiry.strip() or None
        allowed = True
        reason = "Looks OK (basic checks)."
        if expiry_text:
            try:
                ed = datetime.fromisoformat(expiry_text).date()
                if ed < datetime.today().date():
                    allowed = False
                    reason = "Medicine already expired."
            except:
                allowed = False
                reason = "Expiry format invalid (YYYY-MM-DD)."
        else:
            # try shelf life lookup
            sf = shelf_df[shelf_df["medicine_name"].str.lower()==medicine.strip().lower()]
            if not sf.empty:
                months = int(sf.iloc[0]["shelf_months"])
                approx_exp = (mfg_date.replace(day=1) + pd.DateOffset(months=months)).date()
                if approx_exp < datetime.today().date():
                    allowed = False
                    reason = "Likely expired based on shelf-life."
        if not allowed:
            st.warning(reason)
        else:
            st.success(reason)
            matches = ngos_df
            if donor_city.strip():
                matches = matches[matches["city"].str.lower()==donor_city.strip().lower()]
            if prefer != "(Any)":
                matches = matches[matches["name"]==prefer]
            if matches.empty:
                st.info("No matching NGOs found. Admin will be notified.")
            else:
                st.dataframe(matches[["id","name","city","contact","accepts"]])
                chosen = st.selectbox("Choose NGO ID to donate to", matches["id"].astype(str).tolist())
                if st.button("Confirm Donation"):
                    ok = AU_insert_donation(donor_name.strip(), medicine.strip(), mfg_date.isoformat(), expiry_text, "pledged", int(chosen))
                    if ok:
                        st.success("Donation recorded. Thank you!")
                    else:
                        st.error("Failed to record donation.")

st.write("---")

# ---------- Assistant (text + optional voice playback via st.audio) ----------
st.header("Assistant (Text + optional voice playback)")
qcol1, qcol2 = st.columns([1,2])
with qcol1:
    lang_sel = st.selectbox("Language", ["en", "hi"])
    audio_file = st.file_uploader("Upload voice (wav/mp3) — optional", type=["wav","mp3","m4a"])
    uploaded_transcript = None
    if audio_file:
        st.info("Audio upload accepted (transcription not implemented in minimal app).")
with qcol2:
    user_q = st.text_input("Ask the assistant (text)")
    if st.button("Ask"):
        if user_q.strip():
            # placeholder assistant response (replace with your chat_utils)
            answer = f"Assistant reply: {user_q.strip()}"
            st.write(answer)
            audio_bytes = tts_to_bytes(answer, lang=lang_sel)
            if audio_bytes:
                st.audio(audio_bytes, format="audio/mp3")
            else:
                st.info("Audio not available (gTTS missing).")

st.write("---")

# ---------- Role-specific UI ----------
if st.session_state["user"] and st.session_state["user"]["role"] == "admin":
    st.header("Admin Panel")
    st.subheader("NGO List")
    st.dataframe(ngos_df)

    edit_id = st.number_input("NGO ID to edit", min_value=1, step=1)
    if st.button("Load NGO"):
        if edit_id not in ngos_df["id"].tolist():
            st.error("NGO not found.")
        else:
            row = ngos_df[ngos_df["id"]==edit_id].iloc[0]
            name_new = st.text_input("Name", value=row["name"], key="adm_name")
            city_new = st.text_input("City", value=row["city"], key="adm_city")
            contact_new = st.text_input("Contact", value=row["contact"], key="adm_contact")
            accepts_new = st.text_input("Accepts", value=row["accepts"], key="adm_accepts")
            if st.button("Update NGO"):
                ok = AU_update_ngo(edit_id, name_new, city_new, contact_new, accepts_new)
                if ok:
                    st.success("NGO updated.")
                    st.experimental_rerun()
                else:
                    st.error("Update failed.")

    st.subheader("Create user for NGO")
    new_un = st.text_input("Username", key="adm_new_un")
    new_pw = st.text_input("Password", type="password", key="adm_new_pw")
    assign_ngo = st.selectbox("Assign NGO ID", options=ngos_df["id"].tolist(), key="adm_assign_ngo")
    if st.button("Create NGO user"):
        if not new_un or not new_pw:
            st.error("Enter username & password.")
        else:
            ok = AU_create_user(new_un.strip(), new_pw.strip(), role="ngo", ngo_id=int(assign_ngo))
            if ok:
                st.success("User created.")
            else:
                st.error("Failed to create user (username may exist).")

    st.subheader("Donations")
    st.dataframe(don_df)
    delid = st.number_input("Delete donation ID", min_value=0, step=1)
    if st.button("Delete donation"):
        if delid > 0:
            ok = AU_delete_donation(int(delid))
            if ok:
                st.success("Deleted.")
                st.experimental_rerun()
            else:
                st.error("Delete failed.")

elif st.session_state["user"] and st.session_state["user"]["role"] == "ngo":
    st.header("NGO Portal")
    ngo_id = int(st.session_state["user"]["ngo_id"])
    my_row = ngos_df[ngos_df["id"]==ngo_id].iloc[0] if not ngos_df.empty and ngo_id in ngos_df["id"].tolist() else None
    if my_row is None:
        st.error("NGO record missing. Contact admin.")
    else:
        st.subheader(f"{my_row['name']} ({my_row['city']})")
        contact_val = st.text_input("Contact", value=my_row["contact"], key="ngo_contact")
        accepts_val = st.text_input("Accepts", value=my_row["accepts"], key="ngo_accepts")
        if st.button("Update NGO Info"):
            ok = AU_update_ngo(ngo_id, my_row["name"], contact_val, accepts_val)
            if ok:
                st.success("Updated.")
                st.experimental_rerun()
            else:
                st.error("Update failed.")
        st.subheader("Donations assigned to you")
        my_d = don_df[don_df["matched_ngo_id"]==ngo_id]
        st.dataframe(my_d)
        if not my_d.empty:
            st.download_button("Export assigned donations (CSV)", my_d.to_csv(index=False), "my_donations.csv")

else:
    st.info("Login as admin or NGO to manage data. Donors can pledge via the donation form above.")

# ---------- Change password ----------
if st.session_state.get("show_change_pw") and st.session_state.get("user"):
    st.header("Change Password")
    oldp = st.text_input("Current password", type="password", key="cp_old")
    newp = st.text_input("New password", type="password", key="cp_new")
    if st.button("Change password now"):
        uname = st.session_state["user"]["username"]
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE username=?", (uname,))
        r = cur.fetchone()
        conn.close()
        if not r or r[0] != hash_password(oldp):
            st.error("Current password incorrect.")
        else:
            conn = _connect()
            cur = conn.cursor()
            cur.execute("UPDATE users SET password_hash=? WHERE username=?", (hash_password(newp), uname))
            conn.commit()
            conn.close()
            st.success("Password changed. Please login again.")
            st.session_state["user"] = None
            st.session_state["show_change_pw"] = False
            st.experimental_rerun()

st.markdown("<small style='color:#666'>DB seeded & managed locally. For deployment include db_init.py in the repo.</small>", unsafe_allow_html=True)
