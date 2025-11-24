# app.py
"""
Complete updated app.py (ready to paste)
- Real-time donation updates (no caching)
- Reworked NGO dashboard
- Debug panel included to verify DB writes instantly
- Uses meddonationn.db (seeded if missing)
"""

import os
import sqlite3
import hashlib
from datetime import datetime, date
from pathlib import Path

import streamlit as st
import pandas as pd
from PIL import Image
import requests

# ---------------- Configuration ----------------
APP_TITLE = "Medicine Donation Assistant"
DB_FILE = "meddonationn.db"   # make sure this is the file present in same folder as app.py
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

# Local path to user PPT if available (optional)
PPT_REF_PATH = "/mnt/data/mini_projectruchi[1]2 (1).pptx"

# Hugging Face token if present (optional) - set in Streamlit secrets or environment
HF_API_TOKEN = None
try:
    HF_API_TOKEN = st.secrets["HF_API_TOKEN"]
except Exception:
    HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}

# ---------------- Utilities ----------------
def safe_rerun():
    """
    Robust rerun helper (avoids deprecated experimental_set_query_params).
    Try experimental_rerun; fallback toggles a session flag and stops.
    """
    try:
        st.experimental_rerun()
        return
    except Exception:
        st.session_state["_app_rerun_flag"] = not st.session_state.get("_app_rerun_flag", False)
        st.stop()

def connect_db(path=DB_FILE):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- DB seed & migrations ----------------
def seed_database(path=DB_FILE):
    """
    Create DB and seed only if missing. Also ensure migrations for ngo_connections.
    """
    if Path(path).exists():
        # Ensure ngo_connections table exists
        conn = connect_db(path)
        cur = conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS ngo_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ngo_id INTEGER,
            donation_id INTEGER,
            message TEXT,
            created_at TEXT
        );
        """)
        conn.commit()
        conn.close()
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
    CREATE TABLE audio_transcriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        filepath TEXT,
        uploader TEXT,
        uploaded_at TEXT,
        transcription TEXT
    );
    CREATE TABLE ngo_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ngo_id INTEGER,
        donation_id INTEGER,
        message TEXT,
        created_at TEXT
    );
    """)

    # sample NGOs
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

    shelf = [
        ("Paracetamol",36,"Common painkiller"),
        ("Ibuprofen",36,"NSAID"),
        ("Amoxicillin",24,"Antibiotic"),
        ("Azithromycin",24,"Antibiotic"),
        ("Cough Syrup",12,"Liquid formulation"),
        ("Multivitamin",24,"Supplements"),
        ("Antacid",36,"Stomach relief"),
        ("Aspirin",36,"Painkiller"),
        ("Metformin",24,"Diabetes med"),
        ("Vitamin C",36,"Supplement"),
    ]
    cur.executemany("INSERT INTO shelf_life (medicine_name,shelf_months,notes) VALUES (?,?,?)", shelf)

    # users (hash = sha256("medsalt"+password))
    def h(p): return hashlib.sha256(("medsalt"+p).encode()).hexdigest()
    users = [
        ("admin","admin@123","admin",None),
        ("ravi","ravi@123","donor",None),
        ("sita","sita@123","donor",None),
        ("manjari","manjari@123","donor",None),
        ("helping_user","help@123","ngo",1),
    ]
    cur.executemany("INSERT INTO users (username,password_hash,role,ngo_id) VALUES (?,?,?,?)",
                    [(u,h(p),r,n) for (u,p,r,n) in users])

    donations = [
        ("Ravi","Bengaluru","Paracetamol","2023-06-01","2026-06-01","pledged",1, datetime.now().isoformat()),
        ("Sita","Mumbai","Multivitamin","2024-01-01","","pledged",2, datetime.now().isoformat()),
        ("Ramesh","Delhi","Aspirin","2020-01-01","2021-01-01","rejected",5, datetime.now().isoformat())
    ]
    cur.executemany("INSERT INTO donations (donor_name,donor_city,medicine_name,batch_date,expiry_date,status,matched_ngo_id,created_at) VALUES (?,?,?,?,?,?,?,?)", donations)

    cur.execute("INSERT INTO audio_transcriptions (filename,filepath,uploader,uploaded_at,transcription) VALUES (?,?,?,?,?)",
                ("sample.wav","uploads/sample.wav","admin", datetime.now().isoformat(),"Sample transcription"))
    conn.commit()
    conn.close()

seed_database(DB_FILE)

# ---------------- DB helpers (fresh reads/writes only) ----------------
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
    if not row: return None
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
    df = pd.read_sql_query("SELECT * FROM ngos ORDER BY id DESC", conn)
    conn.close()
    return df

def get_shelf_df():
    conn = connect_db()
    df = pd.read_sql_query("SELECT * FROM shelf_life ORDER BY medicine_name", conn)
    conn.close()
    return df

def get_donations_df(limit=500):
    # ALWAYS read fresh (no decorator, no caching)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    try:
        df = pd.read_sql_query("SELECT * FROM donations ORDER BY id DESC LIMIT ?", conn, params=(limit,))
    finally:
        conn.close()
    return df

def insert_donation(donor_name, donor_city, medicine_name, batch_date, expiry_date, status, matched_ngo_id):
    # Insert and return last inserted id
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO donations (donor_name, donor_city, medicine_name, batch_date, expiry_date, status, matched_ngo_id, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (donor_name, donor_city, medicine_name, batch_date, expiry_date, status, matched_ngo_id, datetime.now().isoformat())
        )
        conn.commit()
        last_id = cur.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return last_id

def insert_transcription_record(filename, filepath, uploader, transcription):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO audio_transcriptions (filename, filepath, uploader, uploaded_at, transcription) VALUES (?,?,?,?,?)",
                (filename, filepath, uploader, datetime.now().isoformat(), transcription))
    conn.commit()
    conn.close()

def update_donation_status(donation_id, new_status):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("UPDATE donations SET status=? WHERE id=?", (new_status, donation_id))
    conn.commit()
    conn.close()

def connect_donation_to_ngo(donation_id, ngo_id, message=""):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO ngo_connections (ngo_id, donation_id, message, created_at) VALUES (?,?,?,?)",
                (ngo_id, donation_id, message, datetime.now().isoformat()))
    cur.execute("UPDATE donations SET matched_ngo_id=? WHERE id=?", (ngo_id, donation_id))
    conn.commit()
    conn.close()

def get_connections_for_ngo(ngo_id):
    conn = connect_db()
    df = pd.read_sql_query("SELECT nc.*, d.donor_name, d.donor_city, d.medicine_name, d.created_at as donation_created_at FROM ngo_connections nc LEFT JOIN donations d ON nc.donation_id=d.id WHERE nc.ngo_id=? ORDER BY nc.id DESC", conn, params=(ngo_id,))
    conn.close()
    return df

# ---------------- date parsing ----------------
def parse_date_flexible(s: str):
    if not s or not s.strip():
        return None, "Empty date"
    s = s.strip()
    try:
        d = datetime.fromisoformat(s).date()
        return d, None
    except Exception:
        pass
    patterns = ["%d-%m-%Y", "%d-%m-%y", "%d/%m/%Y", "%d/%m/%y", "%Y/%m/%d", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"]
    for p in patterns:
        try:
            d = datetime.strptime(s, p).date()
            return d, None
        except Exception:
            continue
    try:
        d = pd.to_datetime(s, dayfirst=True, errors="raise").date()
        return d, None
    except Exception:
        return None, f"Could not parse date '{s}'. Use YYYY-MM-DD or DD-MM-YYYY or DD/MM/YYYY."

# ---------------- image validation ----------------
def analyze_image_local(uploaded_file):
    try:
        img = Image.open(uploaded_file)
        img.verify()
        return {"ok": True, "message": "Image valid (no OCR)."}
    except Exception as e:
        return {"ok": False, "message": f"Invalid image: {e}"}

# ---------------- UI ----------------
st.set_page_config(page_title=APP_TITLE, page_icon="💊", layout="wide")
st.markdown("""<style> .title { font-size:26px; font-weight:700; } .muted{color:#556;} </style>""", unsafe_allow_html=True)
st.title(APP_TITLE)
st.caption("Donate medicines, match NGOs, and manage donations. Real-time updates.")

# debug: show DB path used
st.text(f"DB used (path): {DB_FILE}")

# session defaults
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "user" not in st.session_state: st.session_state["user"] = None

# Sidebar: account + assistant
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
        st.sidebar.info("Login / Register on main page")

    st.sidebar.markdown("---")
    st.sidebar.markdown("## Assistant (simple)")
    chat_input = st.sidebar.text_area("Ask (expiry/donate/help)", key="chat_input", height=120, placeholder="Ask about expiry, how to donate, or NGO contact")
    if st.sidebar.button("Send"):
        txt = chat_input.strip()
        if not txt:
            st.sidebar.warning("Type a message.")
        else:
            q = txt.lower()
            if "donate" in q:
                reply = "Fill Donate form on dashboard: enter medicine & dates, choose NGO if you prefer, confirm."
            elif "expiry" in q:
                reply = "Enter printed expiry (YYYY-MM-DD or DD-MM-YYYY) or provide manufacture date; app approximates from shelf DB if missing."
            else:
                reply = "Try asking: 'How to donate paracetamol?' or 'Which NGOs accept vitamins?'"
            st.sidebar.success(reply)

sidebar_panel()

# Landing (login/register)
def landing_page():
    st.markdown("<div class='title'>Welcome</div>", unsafe_allow_html=True)
    st.write("Login or Register. Guest access allowed.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Login")
        lu = st.text_input("Username", key="login_user")
        lp = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if not lu or not lp:
                st.warning("Enter credentials.")
            else:
                user = verify_user(lu.strip(), lp.strip())
                if user:
                    st.session_state["logged_in"] = True
                    st.session_state["user"] = user
                    safe_rerun()
                else:
                    st.error("Invalid username/password.")
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
            ng_accepts = st.text_input("Accepts (comma separated)", key="reg_ngo_accepts")
            ng_user = st.text_input("Choose admin username", key="reg_ngo_user")
            ng_pass = st.text_input("Choose password", key="reg_ngo_pass", type="password")
            if st.button("Register NGO"):
                if not ng_name or not ng_user or not ng_pass:
                    st.error("Enter NGO info and credentials.")
                else:
                    nid = insert_ngo(ng_name.strip(), ng_city.strip(), ng_contact.strip(), ng_accepts.strip())
                    if nid:
                        ok, err = create_user(ng_user.strip(), ng_pass.strip(), role="ngo", ngo_id=int(nid))
                        if ok:
                            st.success("NGO & its user created — please login.")
                            safe_rerun()
                        else:
                            st.error(err)
                    else:
                        st.error("Failed to create NGO.")

# Dashboard for donors and guests
def dashboard():
    st.markdown("<h3>Dashboard</h3>", unsafe_allow_html=True)
    if Path(PPT_REF_PATH).exists():
        with st.expander("Project PPT (download)"):
            with open(PPT_REF_PATH, "rb") as f:
                st.download_button("📄 Download project PPT", data=f.read(), file_name=Path(PPT_REF_PATH).name)

    user = st.session_state["user"]
    ngos_df = get_all_ngos_df()
    shelf_df = get_shelf_df()
    don_df = get_donations_df()
    c1,c2,c3 = st.columns(3)
    c1.metric("NGOs", len(ngos_df))
    c2.metric("Shelf entries", len(shelf_df))
    c3.metric("Donations", len(don_df))

    st.markdown("### Live data controls")
    colA, colB = st.columns([1,3])
    with colA:
        if st.button("🔄 Refresh live data"):
            safe_rerun()
    with colB:
        st.write("Writes refresh automatically. Use Refresh if needed.")

    left, right = st.columns([2,1])
    with left:
        st.subheader("Donate a Medicine")
        with st.form("don_form"):
            d_name = st.text_input("Donor name", value=user["username"] if user else "")
            d_city = st.text_input("City")
            d_med = st.text_input("Medicine (name)")
            d_mfg = st.date_input("Manufacture/Purchase date", value=date.today())
            d_printed = st.text_input("Printed expiry (optional)", help="e.g. YYYY-MM-DD or DD/MM/YYYY")
            d_pref = st.selectbox("Preferred NGO (optional)", options=["(Any)"] + ngos_df["name"].tolist())
            submit = st.form_submit_button("Check & Submit")
        if submit:
            if not d_name or not d_med:
                st.error("Provide donor name and medicine name.")
            else:
                expiry_obj = None
                expiry_err = None
                if d_printed and d_printed.strip():
                    expiry_obj, expiry_err = parse_date_flexible(d_printed.strip())
                    if expiry_err:
                        st.error(f"Expiry parse error: {expiry_err}")
                    else:
                        if expiry_obj < date.today():
                            st.warning("Printed expiry in the past — donation likely rejected.")
                if (not d_printed or not d_printed.strip()) and d_mfg:
                    sf = shelf_df[shelf_df["medicine_name"].str.lower()==d_med.strip().lower()] if not shelf_df.empty else pd.DataFrame()
                    if not sf.empty:
                        months = int(sf.iloc[0]["shelf_months"])
                        approx_expiry = (pd.to_datetime(d_mfg) + pd.DateOffset(months=months)).date()
                        expiry_obj = approx_expiry
                        st.info(f"No printed expiry. Approx expiry from shelf-life: {approx_expiry.isoformat()}")
                if expiry_obj and isinstance(expiry_obj, date) and expiry_obj >= date.today():
                    st.success(f"Expiry OK: {expiry_obj.isoformat()}")
                allow_submit = True
                if d_printed and d_printed.strip() and expiry_err:
                    allow_submit = False
                if allow_submit:
                    matches = ngos_df
                    if d_city:
                        matches = matches[matches["city"].str.lower()==d_city.strip().lower()]
                    if d_pref != "(Any)":
                        matches = matches[matches["name"]==d_pref]
                    chosen = None
                    if matches.empty:
                        st.info("No matching NGOs found. You can still record donation without NGO.")
                    else:
                        st.dataframe(matches[["id","name","city","contact","accepts"]])
                        chosen = st.selectbox("Choose NGO ID", options=["(None)"] + matches["id"].astype(str).tolist(), key="choose_ngo_id")
                        if chosen == "(None)": chosen = None
                    if st.button("Confirm Donation"):
                        matched_id = int(chosen) if chosen else None
                        ed_str = expiry_obj.isoformat() if (expiry_obj and isinstance(expiry_obj, date)) else ""
                        try:
                            new_id = insert_donation(d_name.strip(), d_city.strip(), d_med.strip(), d_mfg.isoformat(), ed_str, "pledged", matched_id)
                            st.success(f"Donation recorded (id={new_id}). It will appear in Recent Donations.")
                            # Force immediate UI refresh
                            safe_rerun()
                        except Exception as e:
                            st.error("Failed to record donation: " + str(e))
        st.write("---")
        st.subheader("Recent Donations (live)")
        df_recent = get_donations_df(200)
        st.dataframe(df_recent)

        # -------- Debug panel (direct DB read) --------
        st.markdown("#### Debug: latest donations (direct DB read)")
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            rows = cur.execute("SELECT id, donor_name, donor_city, medicine_name, batch_date, expiry_date, matched_ngo_id, created_at FROM donations ORDER BY id DESC LIMIT 10").fetchall()
            conn.close()
            st.write(rows)
        except Exception as e:
            st.error("Debug read failed: " + str(e))

    with right:
        st.subheader("Image Upload (Optional)")
        st.markdown("Upload a photo — the app validates file only (no OCR).")
        img_file = st.file_uploader("Upload image", type=["jpg","jpeg","png"])
        if img_file:
            st.image(img_file, use_column_width=True, caption="Uploaded Image")
            res = analyze_image_local(img_file)
            if res["ok"]:
                st.info(res["message"])
            else:
                st.error(res["message"])
        st.write("---")
        st.subheader("Audio for STT (optional)")
        audio = st.file_uploader("Upload audio (wav/mp3/m4a)", type=["wav","mp3","m4a"])
        if audio:
            try:
                st.info("Saving audio and attempting transcription (if HF token present)...")
                safe_name = audio.name.replace(" ", "_")
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                local_filename = f"{timestamp}_{safe_name}"
                local_path = UPLOADS_DIR / local_filename
                with open(local_path, "wb") as f:
                    f.write(audio.read())
                st.success(f"Saved audio: {local_path}")
                transcription = ""
                if HF_API_TOKEN:
                    try:
                        out = requests.post(f"https://api-inference.huggingface.co/models/openai/whisper-tiny",
                                            headers=HEADERS, data=open(local_path,"rb").read(), timeout=120)
                        if out.status_code == 200:
                            j = out.json()
                            if isinstance(j, dict) and j.get("text"):
                                transcription = j.get("text")
                    except Exception:
                        transcription = ""
                else:
                    st.warning("HF_API_TOKEN not set — transcription skipped.")
                uploader = st.session_state["user"]["username"] if st.session_state.get("user") else "guest"
                insert_transcription_record(local_filename, str(local_path), uploader, transcription or "")
                st.info("Saved audio record to DB (live).")
            except Exception as e:
                st.error("Audio processing failed: " + str(e))

# NGO panel
def ngo_panel():
    st.subheader("NGO Dashboard")
    user = st.session_state["user"]
    if not user or user["role"] != "ngo":
        st.info("NGO area only. Please login as NGO user.")
        return
    ngo_id = user.get("ngo_id")
    if not ngo_id:
        st.error("This user is not linked to an NGO record.")
        return

    st.markdown("### Live donors — filter & connect")
    col1, col2, col3 = st.columns([2,2,1])
    donations_df = get_donations_df(1000)
    cities = ["(Any)"] + sorted(list(donations_df["donor_city"].dropna().unique()))
    medicines = ["(Any)"] + sorted(list(donations_df["medicine_name"].dropna().unique()))
    sel_city = col1.selectbox("Filter by donor city", options=cities)
    sel_med = col2.selectbox("Filter by medicine", options=medicines)
    show_unmatched_only = col3.checkbox("Show unmatched donations only", value=True)

    df = donations_df.copy()
    if sel_city and sel_city != "(Any)":
        df = df[df["donor_city"].str.lower() == sel_city.lower()]
    if sel_med and sel_med != "(Any)":
        df = df[df["medicine_name"].str.lower() == sel_med.lower()]
    if show_unmatched_only:
        df = df[df["matched_ngo_id"].isnull() | (df["matched_ngo_id"] == "")]

    st.write(f"Showing {len(df)} donation(s). New donors appear instantly when they donate.")
    st.dataframe(df[["id","donor_name","donor_city","medicine_name","batch_date","expiry_date","status","matched_ngo_id","created_at"]])

    st.markdown("### Connect with a donor")
    choose = st.selectbox("Choose donation id to connect", options=["(None)"] + df["id"].astype(str).tolist(), key="ngo_choose_donation")
    msg = st.text_area("Message to donor (optional)", placeholder="Hello, we can collect your donation. Please contact ...")
    if st.button("Connect with donor"):
        if choose == "(None)":
            st.warning("Select a donation id to connect.")
        else:
            donation_id = int(choose)
            connect_donation_to_ngo(donation_id, ngo_id, message=msg.strip())
            st.success("Connected to donor — recorded and donation linked to your NGO.")
            safe_rerun()

    st.markdown("### Your NGO connections (history)")
    con_df = get_connections_for_ngo(ngo_id)
    if con_df.empty:
        st.info("No connections recorded yet.")
    else:
        st.dataframe(con_df[["id","donation_id","donor_name","donor_city","medicine_name","message","created_at"]])

# Admin panel
def admin_panel():
    st.subheader("Admin Panel")
    user = st.session_state["user"]
    if not user or user["role"] != "admin":
        st.info("Admin area only.")
        return
    st.markdown("NGOs")
    st.dataframe(get_all_ngos_df())
    st.markdown("Add/update shelf-life")
    mname = st.text_input("Medicine name (exact)", key="admin_mname")
    mmonths = st.number_input("Shelf life (months)", min_value=1, max_value=120, step=1, key="admin_mmonths")
    mnotes = st.text_input("Notes", key="admin_mnotes")
    if st.button("Add / Update"):
        if not mname:
            st.error("Provide medicine name.")
        else:
            conn=connect_db(); conn.execute("INSERT OR REPLACE INTO shelf_life (medicine_name,shelf_months,notes) VALUES (?,?,?)",(mname.strip(),int(mmonths),mnotes.strip())); conn.commit(); conn.close()
            st.success("Added/updated")
            safe_rerun()
    st.markdown("All donations (full)")
    st.dataframe(get_donations_df(1000))

# Main routing
if not st.session_state["logged_in"]:
    landing_page()
else:
    user = st.session_state["user"]
    if user["role"] == "admin":
        admin_panel()
    elif user["role"] == "ngo":
        ngo_panel()
    else:
        dashboard()
