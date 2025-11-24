# app.py
"""
Medicine Donation Assistant - patched single-file Streamlit app
Changes in this patched version:
 - Removed all HF image-model / OCR calls to avoid 410 / tesseract errors.
 - Image upload now only validates and displays the image (no remote calls).
 - Chatbot now prefers facebook/blenderbot-400M-distill and falls back to rule-based replies when HF inference fails.
 - Robust safe_rerun helper (non-deprecated).
 - Keeps DB seeding and donor/ngo/admin flows as before.
"""

import os
import io
import sqlite3
import hashlib
from datetime import datetime, date
from pathlib import Path

import streamlit as st
import pandas as pd
from PIL import Image
import requests

# ----------------- safe rerun helper (robust & non-deprecated) -----------------
def safe_rerun():
    """
    Attempt to rerun the app. Use st.experimental_rerun() if available.
    Otherwise attempt best-effort update of query params (st.query_params) if possible.
    If all else fails, toggle a session flag and stop the run.
    """
    try:
        st.experimental_rerun()
        return
    except Exception:
        try:
            st.session_state["_app_rerun_flag"] = not st.session_state.get("_app_rerun_flag", False)
            try:
                qp = dict(st.query_params) if hasattr(st, "query_params") else {}
                qp["_r"] = str(int(st.session_state["_app_rerun_flag"]))
                if hasattr(st, "experimental_set_query_params"):
                    st.experimental_set_query_params(**qp)
                else:
                    try:
                        st.query_params.clear()
                        st.query_params.update(qp)
                    except Exception:
                        pass
            except Exception:
                try:
                    if hasattr(st, "experimental_set_query_params"):
                        st.experimental_set_query_params(_r=str(int(st.session_state["_app_rerun_flag"])))
                except Exception:
                    pass
        except Exception:
            st.session_state["_app_rerun_flag"] = not st.session_state.get("_app_rerun_flag", False)
        st.stop()

# ----------------- Config -----------------
APP_TITLE = "Medicine Donation Assistant"
DB_FILE = "meddonation.db"

# HF token from secrets or env
HF_API_TOKEN = None
try:
    HF_API_TOKEN = st.secrets["HF_API_TOKEN"]
except Exception:
    HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}

# ----------------- Utility: DB -----------------
def connect_db(path=DB_FILE):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def seed_database(path=DB_FILE):
    """
    Create DB and seed sample data (users, ngos, shelf_life, donations)
    This will only run if DB does not exist.
    """
    if Path(path).exists():
        return
    conn = connect_db(path)
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT,
        ngo_id INTEGER
    );
    CREATE TABLE ngos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        city TEXT,
        contact TEXT,
        accepts TEXT
    );
    CREATE TABLE shelf_life (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medicine_name TEXT UNIQUE,
        shelf_months INTEGER,
        notes TEXT
    );
    CREATE TABLE donations (
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
    """)
    # seed ngos
    ngos = [
        ("Helping Hands Trust","Bengaluru","+91 9000000001","paracetamol,ibuprofen"),
        ("Care for All","Mumbai","+91 9000000002","vitamins,antibiotics"),
        ("Asha Foundation","Hyderabad","+91 9000000003","antibiotics,paracetamol"),
        ("Sakhi NGO","Chennai","+91 9000000004","vitamins,antiacids"),
        ("Janseva","Delhi","+91 9000000005","paracetamol,antibiotics"),
        ("Grameen Care","Patna","+91 9000000006","vitamins,paracetamol"),
        ("Seva Samiti","Kolkata","+91 9000000007","cough syrups,antibiotics"),
        ("Rural Relief","Lucknow","+91 9000000008","paracetamol,vitamins"),
        ("Smile Foundation","Pune","+91 9000000009","general medicines"),
        ("Udaan Welfare","Jaipur","+91 9000000010","paracetamol,vitamins"),
    ]
    cur.executemany("INSERT INTO ngos (name,city,contact,accepts) VALUES (?,?,?,?)", ngos)
    # seed shelf-life
    shelf = [
        ("Paracetamol",36,"Common painkiller"),
        ("Ibuprofen",36,"NSAID"),
        ("Amoxicillin",24,"Antibiotic"),
        ("Azithromycin",24,"Antibiotic"),
        ("Cough Syrup",12,"Liquid formulations"),
        ("Multivitamin",24,"Supplements"),
        ("Antacid",36,"Stomach relief"),
        ("Aspirin",36,"Painkiller"),
        ("Metformin",24,"Diabetes med"),
        ("Vitamin C",36,"Supplement"),
    ]
    cur.executemany("INSERT INTO shelf_life (medicine_name,shelf_months,notes) VALUES (?,?,?)", shelf)
    # seed users
    def h(p): return hashlib.sha256(("medsalt"+p).encode()).hexdigest()
    users = [
        ("admin","admin@123","admin",None),
        ("ravi","ravi@123","donor",None),
        ("sita","sita@123","donor",None),
        ("helping_user","help@123","ngo",1),
    ]
    cur.executemany("INSERT INTO users (username,password_hash,role,ngo_id) VALUES (?,?,?,?)",
                    [(u,h(p),r,n) for (u,p,r,n) in users])
    donations = [
        ("Ravi","Bengaluru","Paracetamol","2023-06-01","2026-06-01","pledged",1, datetime.now().isoformat()),
        ("Sita","Mumbai","Multivitamin","2024-01-01","","pledged",2, datetime.now().isoformat()),
        ("Ramesh","Delhi","Aspirin","2020-01-01","2021-01-01","rejected",5, datetime.now().isoformat()),
        ("Meena","Pune","Amoxicillin","2022-03-01","2024-03-01","received",9, datetime.now().isoformat()),
        ("Sunil","Hyderabad","Ibuprofen","2022-08-01","2025-08-01","pledged",3, datetime.now().isoformat())
    ]
    cur.executemany("INSERT INTO donations (donor_name,donor_city,medicine_name,batch_date,expiry_date,status,matched_ngo_id,created_at) VALUES (?,?,?,?,?,?,?,?)", donations)
    conn.commit()
    conn.close()

seed_database(DB_FILE)

# ----------------- DB helpers -----------------
def hash_password(password: str, salt: str="medsalt"):
    return hashlib.sha256((salt + password).encode()).hexdigest()

def create_user(username, password, role="donor", ngo_id=None):
    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username,password_hash,role,ngo_id) VALUES (?,?,?,?)",
                    (username, hash_password(password), role, ngo_id))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def verify_user(username, password):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id,username,password_hash,role,ngo_id FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if row["password_hash"] == hash_password(password):
        return {"id": row["id"], "username": row["username"], "role": row["role"], "ngo_id": row["ngo_id"]}
    return None

def insert_ngo(name, city, contact, accepts):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO ngos (name,city,contact,accepts) VALUES (?,?,?,?)", (name,city,contact,accepts))
    nid = cur.lastrowid
    conn.commit()
    conn.close()
    return nid

def get_all_ngos_df():
    conn = connect_db()
    df = pd.read_sql_query("SELECT * FROM ngos", conn)
    conn.close()
    return df

def get_shelf_df():
    conn = connect_db()
    df = pd.read_sql_query("SELECT * FROM shelf_life", conn)
    conn.close()
    return df

def insert_shelf_item(medicine_name, months, notes):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO shelf_life (medicine_name,shelf_months,notes) VALUES (?,?,?)",
                (medicine_name, months, notes))
    conn.commit()
    conn.close()

def get_donations_df(limit=500):
    conn = connect_db()
    df = pd.read_sql_query("SELECT * FROM donations ORDER BY id DESC LIMIT ?", conn, params=(limit,))
    conn.close()
    return df

def insert_donation(donor_name, donor_city, medicine_name, batch_date, expiry_date, status, matched_ngo_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO donations (donor_name,donor_city,medicine_name,batch_date,expiry_date,status,matched_ngo_id,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (donor_name, donor_city, medicine_name, batch_date, expiry_date, status, matched_ngo_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def update_donation_status(donation_id, new_status):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("UPDATE donations SET status=? WHERE id=?", (new_status, donation_id))
    conn.commit()
    conn.close()

# ----------------- HF helpers (text gen + STT) -----------------
def hf_text_generation(model_name, prompt, params=None, timeout=60):
    """
    Call Hugging Face inference API for text generation. Returns dict:
    { 'ok':bool, 'text':str, 'error':None-or-str, 'status_code':int-or-None }
    """
    if not HF_API_TOKEN:
        return {"ok": False, "text": "", "error": "HF_API_TOKEN not set", "status_code": None}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    payload = {"inputs": prompt}
    if params:
        payload["parameters"] = params
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=timeout)
        if r.status_code == 200:
            try:
                out = r.json()
                if isinstance(out, list) and len(out) > 0 and isinstance(out[0], dict):
                    gen = out[0].get("generated_text") or out[0].get("generated_text", "")
                    return {"ok": True, "text": gen, "error": None, "status_code": 200}
                if isinstance(out, dict) and out.get("generated_text"):
                    return {"ok": True, "text": out.get("generated_text"), "error": None, "status_code": 200}
                return {"ok": True, "text": str(out), "error": None, "status_code": 200}
            except Exception as e:
                return {"ok": False, "text": "", "error": f"parse-error:{e}", "status_code": r.status_code}
        else:
            if r.status_code == 410:
                return {"ok": False, "text": "", "error": "Model endpoint returned 410 Gone (model not available for inference)", "status_code": 410}
            if r.status_code == 403:
                return {"ok": False, "text": "", "error": "Forbidden (403) — check token permissions", "status_code": 403}
            return {"ok": False, "text": "", "error": f"HTTP {r.status_code}: {r.text}", "status_code": r.status_code}
    except Exception as e:
        return {"ok": False, "text": "", "error": f"request-exception: {str(e)}", "status_code": None}

def hf_stt_from_bytes(model_name, audio_bytes, timeout=120):
    """
    Call HF STT inference if token present. May return dict or error.
    """
    if not HF_API_TOKEN:
        return {"error":"HF_API_TOKEN not set"}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    try:
        r = requests.post(url, headers=HEADERS, data=audio_bytes, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# ----------------- Image: simple local validate (NO HF, NO OCR) -----------------
def analyze_image_local(uploaded_file):
    """
    Simple image validation function — displays the image and returns a stable message.
    No HF calls, no OCR.
    """
    try:
        img = Image.open(uploaded_file)
        # verify integrity by loading
        img.verify()
        return {"ok": True, "message": "Image uploaded successfully. (No remote image analysis configured.)"}
    except Exception as e:
        return {"ok": False, "message": f"Invalid image file: {e}"}

# ----------------- Streamlit UI -----------------
st.set_page_config(page_title=APP_TITLE, page_icon="💊", layout="wide")
st.markdown("""<style> .big-title { font-size:28px; font-weight:700; } .muted {color:#556;}</style>""", unsafe_allow_html=True)
st.title(APP_TITLE)
st.caption("Check expiry, match NGOs, record donations — voice & image friendly.")

# session state defaults
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user" not in st.session_state:
    st.session_state["user"] = None
if "assistant_history" not in st.session_state:
    st.session_state["assistant_history"] = []

# ----------------- Sidebar: chat + quick info -----------------
def sidebar_panel():
    st.sidebar.markdown("## Account")
    if st.session_state["logged_in"]:
        u = st.session_state["user"]
        st.sidebar.write("**User:**", u["username"])
        st.sidebar.write("**Role:**", u["role"])
        if st.sidebar.button("Logout"):
            st.session_state["logged_in"] = False
            st.session_state["user"] = None
            safe_rerun()
    else:
        st.sidebar.info("Please login or register from the main page.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("## Assistant")
    chat_input = st.sidebar.text_area("Message (type or paste STT)", key="chat_input", height=120, placeholder="Ask about expiry, donation process, or NGO info")
    if st.sidebar.button("Send"):
        txt = chat_input.strip()
        if not txt:
            st.sidebar.warning("Type or paste some text.")
        else:
            st.session_state["assistant_history"].append({"role":"user","text":txt})
            # Try HF conversational model(s), with fallback
            reply = None
            if HF_API_TOKEN:
                preferred_models = ["facebook/blenderbot-400M-distill", "microsoft/DialoGPT-medium"]
                for model in preferred_models:
                    res = hf_text_generation(model, txt, params={"max_new_tokens":120})
                    if res.get("ok"):
                        reply = res.get("text")
                        break
                    else:
                        # If model returned 410 or 403, try next model
                        continue
            # Rule-based fallback/response if no HF or HF failed
            if not reply:
                q = txt.lower()
                if "donate" in q:
                    reply = "To donate: open 'Donate a Medicine', provide medicine name and dates (if available), pick NGO or leave blank and confirm."
                elif "expiry" in q or "expire" in q:
                    reply = "If a printed expiry exists, use it. Otherwise the system estimates safety using shelf-life entries."
                elif "ngo" in q or "where" in q:
                    reply = "Visit the NGO list or choose a preferred NGO while donating; the dashboard lists NGOs by city and contact."
                else:
                    reply = "I can help with donation steps, expiry checks, and NGO matching. Try questions like: 'Is paracetamol safe to donate?'"
            st.sidebar.success(reply)
            st.session_state["assistant_history"].append({"role":"assistant","text":reply})

    st.sidebar.markdown("---")
    st.sidebar.markdown("## Quick Links")
    if st.sidebar.button("Go to Dashboard"):
        pass

sidebar_panel()

# ----------------- Landing: Login / Register -----------------
def landing_page():
    st.markdown("<div class='big-title'>Welcome</div>", unsafe_allow_html=True)
    st.write("Please login or register to continue. Use Guest if you just want to view.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Login")
        lu = st.text_input("Username", key="login_user")
        lp = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if not lu or not lp:
                st.warning("Provide username and password.")
            else:
                user = verify_user(lu.strip(), lp.strip())
                if user:
                    st.success(f"Logged in as {user['username']} ({user['role']})")
                    st.session_state["logged_in"] = True
                    st.session_state["user"] = user
                    safe_rerun()
                else:
                    st.error("Invalid credentials.")
        if st.button("Continue as Guest"):
            st.session_state["logged_in"] = True
            st.session_state["user"] = {"id":0,"username":"guest","role":"guest","ngo_id":None}
            safe_rerun()
    with col2:
        st.subheader("Register")
        rtype = st.radio("Register as", ("Donor","NGO"), horizontal=True)
        if rtype == "Donor":
            du = st.text_input("Choose username", key="reg_d_user")
            dp = st.text_input("Choose password", key="reg_d_pass", type="password")
            if st.button("Register Donor"):
                if not du or not dp:
                    st.error("Enter username and password.")
                else:
                    ok, err = create_user(du.strip(), dp.strip(), role="donor")
                    if ok:
                        st.success("Donor created — please login.")
                    else:
                        st.error(err)
        else:
            ng_name = st.text_input("NGO Name", key="reg_ngo_name")
            ng_city = st.text_input("City", key="reg_ngo_city")
            ng_contact = st.text_input("Contact", key="reg_ngo_contact")
            ng_accepts = st.text_input("Accepts (comma separated, e.g. paracetamol,vitamins)", key="reg_ngo_accepts")
            ng_user = st.text_input("Choose admin username", key="reg_ngo_user")
            ng_pass = st.text_input("Choose password", key="reg_ngo_pass", type="password")
            if st.button("Register NGO"):
                if not ng_name or not ng_user or not ng_pass:
                    st.error("Enter NGO name and credentials.")
                else:
                    nid = insert_ngo(ng_name.strip(), ng_city.strip(), ng_contact.strip(), ng_accepts.strip())
                    if nid:
                        ok, err = create_user(ng_user.strip(), ng_pass.strip(), role="ngo", ngo_id=int(nid))
                        if ok:
                            st.success("NGO and NGO user created — please login.")
                        else:
                            st.error(err)
                    else:
                        st.error("Failed to create NGO.")

# ----------------- Dashboard after login -----------------
def dashboard():
    st.markdown("<div style='display:flex;align-items:center;gap:12px;'><img src='https://img.icons8.com/fluency/48/pill.png'/> <h2 style='margin:0'>Medicine Donation Assistant</h2></div>", unsafe_allow_html=True)

    user = st.session_state["user"]
    ngos_df = get_all_ngos_df()
    shelf_df = get_shelf_df()
    don_df = get_donations_df()
    c1,c2,c3 = st.columns(3)
    c1.metric("NGOs", len(ngos_df))
    c2.metric("Shelf entries", len(shelf_df))
    c3.metric("Donations", len(don_df))

    st.write("---")
    left, right = st.columns([2,1])
    with left:
        st.subheader("Donate a Medicine")
        with st.form("don_form"):
            d_name = st.text_input("Donor name", value=user["username"] if user else "")
            d_city = st.text_input("City")
            d_med = st.text_input("Medicine (name)")
            d_mfg = st.date_input("Manufacture/Purchase date", value=date.today())
            d_printed = st.text_input("Printed expiry (YYYY-MM-DD) (optional)")
            d_pref = st.selectbox("Preferred NGO (optional)", options=["(Any)"] + ngos_df["name"].tolist())
            submit = st.form_submit_button("Check & Submit")
        if submit:
            if not d_name or not d_med:
                st.error("Provide donor name and medicine name.")
            else:
                expired = False
                reason = ""
                if d_printed.strip():
                    try:
                        ed = datetime.fromisoformat(d_printed.strip()).date()
                        if ed < date.today():
                            expired = True; reason = "Printed expiry is past."
                    except Exception:
                        expired = True; reason = "Invalid expiry format."
                else:
                    sf = shelf_df[shelf_df["medicine_name"].str.lower()==d_med.strip().lower()] if not shelf_df.empty else pd.DataFrame()
                    if not sf.empty:
                        months = int(sf.iloc[0]["shelf_months"])
                        approx_expiry = (pd.to_datetime(d_mfg) + pd.DateOffset(months=months)).date()
                        if approx_expiry < date.today():
                            expired = True; reason = "Likely expired based on shelf-life estimate."
                if expired:
                    st.warning(reason)
                else:
                    st.success("Looks OK (basic check). Choose NGO and confirm.")
                    matches = ngos_df
                    if d_city:
                        matches = matches[matches["city"].str.lower()==d_city.strip().lower()]
                    if d_pref != "(Any)":
                        matches = matches[matches["name"]==d_pref]
                    if matches.empty:
                        st.info("No nearby matching NGO found. You can still record the donation without NGO.")
                        chosen = None
                    else:
                        st.dataframe(matches[["id","name","city","contact","accepts"]])
                        chosen = st.selectbox("Choose NGO ID", options=["(None)"] + matches["id"].astype(str).tolist())
                        if chosen == "(None)": chosen = None
                    if st.button("Confirm Donation"):
                        matched_id = int(chosen) if chosen else None
                        ok = insert_donation(d_name.strip(), d_city.strip(), d_med.strip(), d_mfg.isoformat(), d_printed.strip(), "pledged", matched_id)
                        if ok:
                            st.success("Donation recorded. Thank you.")
                        else:
                            st.error("Failed to record donation.")

        st.write("---")
        st.subheader("Recent Donations")
        df_recent = get_donations_df(20)
        st.dataframe(df_recent)

    with right:
        st.subheader("Image Upload (Optional)")
        st.markdown("Upload a photo of the medicine or pack. This app does **not** perform OCR or remote image classification — it only validates the file and displays it.")
        img_file = st.file_uploader("Upload an image (jpg/png)", type=["jpg","jpeg","png"])
        if img_file:
            st.image(img_file, use_column_width=True, caption="Uploaded Image")
            # local validation only
            res = analyze_image_local(img_file)
            if res["ok"]:
                st.info(res["message"])
            else:
                st.error(res["message"])

        st.write("---")
        st.subheader("Audio for STT (optional, HF only)")
        audio = st.file_uploader("Upload audio for transcription (wav/mp3)", type=["wav","mp3","m4a"])
        if audio:
            try:
                st.info("Transcribing... (may take a few seconds)")
                audio_bytes = audio.read()
                if HF_API_TOKEN:
                    out = hf_stt_from_bytes("openai/whisper-tiny", audio_bytes)
                    if isinstance(out, dict) and out.get("error"):
                        st.error("STT error: " + out.get("error"))
                    else:
                        text = ""
                        if isinstance(out, dict) and out.get("text"):
                            text = out.get("text")
                        elif isinstance(out, str):
                            text = out
                        elif isinstance(out, list):
                            text = " ".join([seg.get("text","") if isinstance(seg, dict) else str(seg) for seg in out])
                        st.success("Transcribed text:")
                        st.text_area("Transcript", value=text, height=160)
                        st.session_state["assistant_history"].append({"role":"user","text":text})
                else:
                    st.warning("HF API token not set — STT not available.")
            except Exception as e:
                st.error("STT processing failed: " + str(e))

# ----------------- NGO panel -----------------
def ngo_panel():
    st.subheader("NGO Dashboard")
    user = st.session_state["user"]
    if not user or user["role"] != "ngo":
        st.info("This area is for NGO users.")
        return
    ngo_id = user.get("ngo_id")
    if not ngo_id:
        st.error("Your user is not linked to an NGO.")
        return
    df = get_donations_df(500)
    my = df[df["matched_ngo_id"] == ngo_id]
    st.write(f"Donations assigned to NGO ID {ngo_id}")
    st.dataframe(my)
    st.markdown("### Update donation status")
    sel = st.selectbox("Choose donation id", options=["(None)"] + my["id"].astype(str).tolist())
    if sel != "(None)":
        sid = int(sel)
        new = st.selectbox("New status", ["pledged","intransit","received","rejected"])
        if st.button("Update status"):
            update_donation_status(sid, new)
            st.success("Status updated")
            safe_rerun()

# ----------------- Admin panel -----------------
def admin_panel():
    st.subheader("Admin Panel")
    user = st.session_state["user"]
    if not user or user["role"] != "admin":
        st.info("Admin access only.")
        return
    st.markdown("### NGOs")
    ngos = get_all_ngos_df()
    st.dataframe(ngos)
    st.markdown("Add new shelf-life item")
    mname = st.text_input("Medicine name (exact)", key="admin_mname")
    mmonths = st.number_input("Shelf life (months)", min_value=1, max_value=120, step=1, key="admin_mmonths")
    mnotes = st.text_input("Notes", key="admin_mnotes")
    if st.button("Add / Update shelf-life"):
        if not mname:
            st.error("Provide medicine name")
        else:
            insert_shelf_item(mname.strip(), int(mmonths), mnotes.strip())
            st.success("Entry added/updated")
            safe_rerun()
    st.markdown("### All donations")
    st.dataframe(get_donations_df(500))

# ----------------- Main run -----------------
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    landing_page()
else:
    user = st.session_state["user"]
    if user["role"] == "admin":
        admin_panel()
    elif user["role"] == "ngo":
        ngo_panel()
        st.write("---")
        dashboard()
    else:
        dashboard()
