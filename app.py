# app.py
"""
Medicine Donation Assistant - Colorful UI + Robust Chatbot
- Full Streamlit app (single file)
- Chatbot uses HF Inference API when HF_API_TOKEN present, else a rule-based fallback
- Chat replies persist across reruns and surface errors/fallbacks clearly
- Visual polish and optional live-refresh for multi-tab demos
"""

import os
import sqlite3
import hashlib
from datetime import datetime, date
from pathlib import Path
import time
import traceback

import streamlit as st
import pandas as pd
from PIL import Image
import requests
import streamlit.components.v1 as components

# ---------------- Configuration ----------------
APP_TITLE = "💊 Medicine Donation Assistant"

# Canonical absolute path for DB and uploads
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "meddonationn.db")
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Optional PPT path (change if you have one)
PPT_REF_PATH = str(BASE_DIR / "project_pptx_placeholder.pptx")

# Hugging Face token optional (set in streamlit secrets or env var)
HF_API_TOKEN = None
try:
    HF_API_TOKEN = st.secrets["HF_API_TOKEN"]
except Exception:
    HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}

# ---------------- Utilities ----------------
def safe_rerun():
    """Trigger Streamlit rerun safely."""
    try:
        st.experimental_rerun()
    except Exception:
        st.session_state["_app_rerun_flag"] = not st.session_state.get("_app_rerun_flag", False)
        st.stop()

def connect_db(path: str = None):
    """Return sqlite3.Connection using canonical DB_PATH by default."""
    p = DB_PATH if path is None else path
    conn = sqlite3.connect(p, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        pass
    return conn

# ---------------- DB seed ----------------
def seed_database(path: str = None):
    path = DB_PATH if path is None else path
    created = not Path(path).exists()
    conn = connect_db(path)
    cur = conn.cursor()
    cur.executescript("""
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
    """)
    conn.commit()

    if created:
        ngos = [
            ("Helping Hands Trust","Bengaluru","+91 9000000001","paracetamol,ibuprofen"),
            ("Care for All","Mumbai","+91 9000000002","vitamins,antibiotics"),
            ("Asha Foundation","Hyderabad","+91 9000000003","antibiotics,paracetamol"),
            ("Sakhi NGO","Chennai","+91 9000000004","vitamins,antiacids"),
            ("Janseva","Delhi","+91 9000000005","paracetamol,antibiotics"),
        ]
        cur.executemany("INSERT INTO ngos (name,city,contact,accepts) VALUES (?,?,?,?)", ngos)

        shelf = [
            ("Paracetamol",36,"Common painkiller"),
            ("Ibuprofen",36,"NSAID"),
            ("Amoxicillin",24,"Antibiotic"),
            ("Cough Syrup",12,"Liquid formulation"),
            ("Multivitamin",24,"Supplements"),
        ]
        cur.executemany("INSERT INTO shelf_life (medicine_name,shelf_months,notes) VALUES (?,?,?)", shelf)

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
        ]
        cur.executemany("INSERT INTO donations (donor_name,donor_city,medicine_name,batch_date,expiry_date,status,matched_ngo_id,created_at) VALUES (?,?,?,?,?,?,?,?)", donations)
        conn.commit()
    conn.close()

# ensure DB exists
seed_database(DB_PATH)

# ---------------- DB helpers ----------------
def hash_password(password: str, salt: str="medsalt"):
    return hashlib.sha256((salt + password).encode()).hexdigest()

def create_user(username, password, role="donor", ngo_id=None):
    conn = connect_db(); cur = conn.cursor()
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
    conn = connect_db(); cur = conn.cursor()
    cur.execute("SELECT id,username,password_hash,role,ngo_id FROM users WHERE username=?", (username,))
    row = cur.fetchone(); conn.close()
    if not row: return None
    if row["password_hash"] == hash_password(password):
        return {"id": row["id"], "username": row["username"], "role": row["role"], "ngo_id": row["ngo_id"]}
    return None

def get_all_ngos_df():
    conn = connect_db(); df = pd.read_sql_query("SELECT * FROM ngos ORDER BY id DESC", conn); conn.close(); return df

def get_shelf_df():
    conn = connect_db(); df = pd.read_sql_query("SELECT * FROM shelf_life ORDER BY medicine_name", conn); conn.close(); return df

def get_donations_df(limit=500):
    conn = connect_db()
    try:
        df = pd.read_sql_query("SELECT * FROM donations ORDER BY id DESC LIMIT ?", conn, params=(limit,))
    finally:
        conn.close()
    return df

def insert_donation(donor_name, donor_city, medicine_name, batch_date, expiry_date, status, matched_ngo_id):
    conn = connect_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO donations (donor_name,donor_city,medicine_name,batch_date,expiry_date,status,matched_ngo_id,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (donor_name, donor_city, medicine_name, batch_date, expiry_date, status, matched_ngo_id, datetime.now().isoformat()))
        conn.commit()
        last_id = cur.lastrowid
        print(f"[insert_donation] inserted id={last_id}, donor={donor_name}, med={medicine_name}")
    except Exception as exc:
        conn.rollback()
        print("[insert_donation] ERROR:", exc)
        traceback.print_exc()
        raise
    finally:
        conn.close()
    return last_id

def insert_transcription_record(filename, filepath, uploader, transcription):
    conn = connect_db(); cur = conn.cursor()
    cur.execute("INSERT INTO audio_transcriptions (filename, filepath, uploader, uploaded_at, transcription) VALUES (?,?,?,?,?)",
                (filename, filepath, uploader, datetime.now().isoformat(), transcription))
    conn.commit(); conn.close()

def update_donation_status(donation_id, new_status):
    conn = connect_db(); cur = conn.cursor()
    cur.execute("UPDATE donations SET status=? WHERE id=?", (new_status, donation_id))
    conn.commit(); conn.close()

def connect_donation_to_ngo(donation_id, ngo_id, message=""):
    conn = connect_db(); cur = conn.cursor()
    cur.execute("INSERT INTO ngo_connections (ngo_id, donation_id, message, created_at) VALUES (?,?,?,?)",
                (ngo_id, donation_id, message, datetime.now().isoformat()))
    cur.execute("UPDATE donations SET matched_ngo_id=? WHERE id=?", (ngo_id, donation_id))
    conn.commit(); conn.close()

def get_connections_for_ngo(ngo_id):
    conn = connect_db()
    df = pd.read_sql_query("""
        SELECT nc.*, d.donor_name, d.donor_city, d.medicine_name, d.created_at as donation_created_at
        FROM ngo_connections nc
        LEFT JOIN donations d ON nc.donation_id=d.id
        WHERE nc.ngo_id=?
        ORDER BY nc.id DESC
    """, conn, params=(ngo_id,))
    conn.close(); return df

def get_connections_for_donor(donor_name: str):
    conn = connect_db()
    df = pd.read_sql_query("""
        SELECT
            nc.id,
            nc.donation_id,
            nc.message,
            nc.created_at,
            d.medicine_name,
            d.batch_date,
            d.expiry_date,
            d.status,
            n.name       AS ngo_name,
            n.city       AS ngo_city,
            n.contact    AS ngo_contact
        FROM ngo_connections nc
        JOIN donations d ON d.id = nc.donation_id
        LEFT JOIN ngos n ON n.id = nc.ngo_id
        WHERE d.donor_name = ?
        ORDER BY nc.id DESC
    """, conn, params=(donor_name,))
    conn.close()
    return df

# ---------------- Preprocessing helpers ----------------
def canonicalize_med_name(name: str):
    if not name: return ""
    name = name.strip().lower()
    alias = {"paracet":"paracetamol","crocin":"paracetamol","acetaminophen":"paracetamol","tylenol":"paracetamol"}
    for k,v in alias.items():
        if k in name:
            return v.capitalize()
    return name.capitalize()

def parse_date_flexible(s: str):
    if not s: return None, "Empty"
    s = s.strip()
    try:
        dt = datetime.fromisoformat(s).date()
        return dt, None
    except Exception:
        pass
    formats = ["%d-%m-%Y","%d/%m/%Y","%Y-%m-%d","%d-%b-%Y","%d %B %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date(), None
        except Exception:
            continue
    try:
        d = pd.to_datetime(s, dayfirst=True, errors="raise").date()
        return d, None
    except Exception:
        return None, f"Could not parse date '{s}'. Use YYYY-MM-DD or DD-MM-YYYY."

# ---------------- Model wrappers with safe fallbacks ----------------
def hf_whisper_transcribe(filepath: str):
    if not HF_API_TOKEN:
        return "", "HF token not set - transcription skipped"
    url = "https://api-inference.huggingface.co/models/openai/whisper-tiny"
    try:
        with open(filepath, "rb") as f:
            resp = requests.post(url, headers=HEADERS, data=f.read(), timeout=120)
        if resp.status_code == 200:
            j = resp.json()
            if isinstance(j, dict) and j.get("text"):
                return j.get("text"), None
            if isinstance(j, list) and len(j)>0 and isinstance(j[0], dict) and j[0].get("text"):
                return j[0]["text"], None
        return "", f"HF transcribe failed: {resp.status_code} {resp.text}"
    except Exception as e:
        return "", f"Transcription error: {e}"

def hf_dialoggpt_reply(prompt: str):
    """
    Try to get a reply from a simple HF conversational endpoint.
    Fall back to rule_based_chatbot if anything goes wrong.
    """
    if not HF_API_TOKEN:
        return rule_based_chatbot(prompt)
    url = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"
    try:
        payload = {"inputs": prompt}
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            # Many HF endpoints return either a dict or list; handle both.
            if isinstance(data, dict):
                # Try several likely keys
                for k in ("generated_text", "text", "response"):
                    if data.get(k):
                        return data.get(k)
                # If model returns 'error' or other, fall through to fallback
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, dict):
                    for k in ("generated_text","text","response"):
                        if first.get(k):
                            return first.get(k)
                    # otherwise return stringified first item
                    return str(first)
                else:
                    return str(first)
        # non-200 or unexpected shape -> fallback
        print("[hf_dialoggpt_reply] HF resp status:", resp.status_code, resp.text[:500])
        return rule_based_chatbot(prompt) + " (model fallback used)"
    except Exception as e:
        print("[hf_dialoggpt_reply] exception:", e)
        traceback.print_exc()
        return rule_based_chatbot(prompt) + " (model fallback used)"

def hf_distilbert_intent(prompt: str):
    """
    Try HF sentiment/classifier for intent; fallback to heuristics.
    """
    if not HF_API_TOKEN:
        return heuristic_intent(prompt)
    url = "https://api-inference.huggingface.co/models/distilbert-base-uncased-finetuned-sst-2-english"
    try:
        resp = requests.post(url, headers=HEADERS, json={"inputs": prompt}, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            # data often a list of dicts
            if isinstance(data, list) and len(data)>0 and isinstance(data[0], dict):
                lab = data[0].get("label","").lower()
                score = data[0].get("score",0.0)
                return {"intent":"ask" if "neutral" in lab or "pos" in lab else "ask", "confidence":score}
            if isinstance(data, dict) and "label" in data:
                lab = data.get("label","").lower()
                return {"intent":"ask","confidence":data.get("score",0.0)}
    except Exception as e:
        print("[hf_distilbert_intent] exception:", e)
        traceback.print_exc()
    return heuristic_intent(prompt)

def heuristic_intent(text):
    t = text.lower()
    if any(x in t for x in ["donate","how to donate","where to donate","donation","i want to donate"]):
        return {"intent":"donation"}
    if any(x in t for x in ["expiry","expire","expired","best before","shelf","shelf life"]):
        return {"intent":"expiry"}
    if any(x in t for x in ["ngos","ngo","help","collect","pickup","pickup"]):
        return {"intent":"ngo"}
    return {"intent":"ask"}

def rule_based_chatbot(prompt: str):
    """
    Lightweight rule-based assistant fallback. Uses shelf DB for expiry hints.
    """
    intent = heuristic_intent(prompt)
    if intent["intent"] == "donation":
        return ("To donate: open Donate form → enter your name and city → enter medicine name and manufacture/purchase date or printed expiry → choose NGO (optional) → Confirm. "
                "If you'd like voice input, upload audio in the Image/Audio panel.")
    if intent["intent"] == "expiry":
        meds = [row["medicine_name"].lower() for _,row in get_shelf_df().iterrows()] if not get_shelf_df().empty else []
        for m in meds:
            if m.lower() in prompt.lower():
                row = get_shelf_df()[get_shelf_df()["medicine_name"].str.lower()==m]
                months = int(row.iloc[0]["shelf_months"])
                return f"Typical shelf life for {m.title()} is {months} months from manufacture. If printed expiry is present, prefer that."
        return "Please provide printed expiry or manufacture date; I can approximate expiry using shelf-life data."
    if intent["intent"] == "ngo":
        ngos = get_all_ngos_df()
        if ngos.empty:
            return "No NGOs available in DB. Please register an NGO from admin or contact support."
        return "Use the dashboard to find NGOs by city or medicine they accept. You can see NGO contact details in the list."
    return "I can help with donation steps, expiry checks, or NGO contacts. Try: 'How to donate paracetamol?'"

# ---------------- Image validation ----------------
def analyze_image_local(uploaded_file):
    try:
        img = Image.open(uploaded_file)
        img.verify()
        return {"ok": True, "message": "Image is valid (this demo does not OCR). Please type expiry if unreadable."}
    except Exception as e:
        return {"ok": False, "message": f"Image invalid: {e}"}

# ---------------- UI & Styling ----------------
st.set_page_config(page_title=APP_TITLE, page_icon="💊", layout="wide")
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: linear-gradient(180deg,#fff,#f7fbff); }
.title { font-size:34px; font-weight:800; color:#0b4f6c; }
.bigcard { padding:18px; border-radius:14px; background: linear-gradient(90deg,#ffffffcc,#f6fbffcc); box-shadow: 0 6px 18px rgba(11,79,108,0.06); }
.stButton>button { background: linear-gradient(90deg,#ff7eb6,#7afcff); border: none; color:#012; padding:10px 14px; border-radius:10px; font-weight:600; }
.stButton>button:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
.metric { background: linear-gradient(90deg,#fffef0,#f0fff5); padding:10px; border-radius:10px; }
.small-muted { color:#666; font-size:12px; }
.card-title { font-weight:700; color:#0b4f6c; }
.table { border-radius:10px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

st.markdown(f"<div class='title'>{APP_TITLE}</div>", unsafe_allow_html=True)
st.caption("Voice & text friendly • Photo-check (no OCR) • Donor ↔ NGO connections")

# --- Live-refresh toggle in sidebar
st.sidebar.markdown("### Live options")
enable_live = st.sidebar.checkbox("Enable live auto-refresh (every 8s)", value=False, help="Reload page every 8 seconds to pick up updates from other tabs (demo only).")
if enable_live:
    components.html("<script>setInterval(function(){ window.location.reload(); }, 8000);</script>", height=0)

# ---------------- Sidebar assistant (robust, persistent) ----------------
def sidebar_panel():
    """
    Robust assistant in sidebar:
    - mini_q and mini_reply persist in session_state
    - uses HF when available, else rule-based fallback
    - shows mode and any errors
    """
    st.sidebar.markdown("## Account")
    if st.session_state.get("logged_in"):
        u = st.session_state["user"]
        st.sidebar.markdown(f"**{u['username']}** — *{u['role']}*")
        if st.sidebar.button("Logout"):
            st.session_state["logged_in"] = False
            st.session_state["user"] = None
            safe_rerun()
    else:
        st.sidebar.info("Login / Register on the main page")

    st.sidebar.markdown("---")
    st.sidebar.markdown("## Quick Assistant")

    # initialize session keys
    if "mini_q" not in st.session_state: st.session_state["mini_q"] = ""
    if "mini_reply" not in st.session_state: st.session_state["mini_reply"] = ""
    if "mini_last_mode" not in st.session_state: st.session_state["mini_last_mode"] = ""
    if "mini_error" not in st.session_state: st.session_state["mini_error"] = ""

    # text area bound to session_state (prevents losing text on reruns)
    st.session_state["mini_q"] = st.sidebar.text_area("Ask (expiry / donate / NGO)", value=st.session_state["mini_q"], key="mini_q_widget", height=110)

    # Ask button
    if st.sidebar.button("Ask"):
        q = st.session_state.get("mini_q", "").strip()
        if not q:
            st.sidebar.warning("Type a question.")
        else:
            st.sidebar.info("Processing...")
            st.session_state["mini_error"] = ""
            try:
                # If HF token set, attempt network call; otherwise fallback
                if HF_API_TOKEN:
                    try:
                        reply = hf_dialoggpt_reply(q)
                        st.session_state["mini_last_mode"] = "HF"
                    except Exception as e:
                        # HF failed - fallback
                        print("[sidebar_panel] HF error:", e)
                        traceback.print_exc()
                        reply = rule_based_chatbot(q)
                        st.session_state["mini_last_mode"] = "fallback_due_to_HF_error"
                        st.sidebar.warning("HF error — used fallback. See logs.")
                else:
                    reply = rule_based_chatbot(q)
                    st.session_state["mini_last_mode"] = "rule_based"
                st.session_state["mini_reply"] = reply
                print("[mini assistant] q:", q[:200])
                print("[mini assistant] mode:", st.session_state["mini_last_mode"])
                print("[mini assistant] reply:", (reply or "")[:300])
            except Exception as e:
                st.session_state["mini_reply"] = ""
                st.session_state["mini_error"] = str(e)
                st.sidebar.error("Assistant error: " + str(e))
                print("[sidebar_panel] assistant exception:", e)
                traceback.print_exc()

    # Show the persisted reply
    if st.session_state.get("mini_reply"):
        mode = st.session_state.get("mini_last_mode", "unknown")
        st.sidebar.markdown(f"**Assistant ({mode})**")
        st.sidebar.success(st.session_state["mini_reply"])
        if st.session_state.get("mini_error"):
            st.sidebar.text("Last error: " + st.session_state.get("mini_error"))
    else:
        st.sidebar.info("Assistant ready. Type a question and press 'Ask'.")

    # Quick test to prefill and run demo question
    if st.sidebar.button("Quick test: donation example"):
        st.session_state["mini_q"] = "How to donate paracetamol?"
        # re-run so the filled text shows
        safe_rerun()

sidebar_panel()

# ---------------- Rest of UI (landing/dashboard/ngo/admin) ----------------
def landing_page():
    st.markdown("<div class='bigcard'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Welcome 👋</div>", unsafe_allow_html=True)
    st.write("Please login or register. You may also continue as guest for demonstration.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🔐 Login")
        lu = st.text_input("Username", key="login_user")
        lp = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if not lu or not lp:
                st.warning("Enter credentials")
            else:
                user = verify_user(lu.strip(), lp.strip())
                if user:
                    st.session_state["logged_in"] = True
                    st.session_state["user"] = user
                    safe_rerun()
                else:
                    st.error("Invalid username/password")
        if st.button("Continue as Guest"):
            st.session_state["logged_in"] = True
            st.session_state["user"] = {"id":0,"username":"guest","role":"guest","ngo_id":None}
            safe_rerun()
    with c2:
        st.subheader("📝 Register")
        rtype = st.radio("Register as", ("Donor","NGO"), horizontal=True)
        if rtype == "Donor":
            du = st.text_input("Username", key="reg_d_user")
            dp = st.text_input("Password", type="password", key="reg_d_pass")
            if st.button("Register Donor"):
                if not du or not dp:
                    st.error("Enter username and password")
                else:
                    ok, err = create_user(du.strip(), dp.strip(), role="donor")
                    if ok:
                        st.success("Donor created. Please login.")
                    else:
                        st.error(err)
        else:
            ng_name = st.text_input("NGO name", key="reg_ngo_name")
            ng_city = st.text_input("City", key="reg_ngo_city")
            ng_contact = st.text_input("Contact", key="reg_ngo_contact")
            ng_accepts = st.text_input("Accepts (comma separated)", key="reg_ngo_accepts")
            ng_user = st.text_input("Admin username", key="reg_ngo_user")
            ng_pass = st.text_input("Admin password", type="password", key="reg_ngo_pass")
            if st.button("Register NGO"):
                if not ng_name or not ng_user or not ng_pass:
                    st.error("Fill NGO & admin credentials")
                else:
                    try:
                        conn = connect_db(); cur = conn.cursor()
                        cur.execute("INSERT INTO ngos (name,city,contact,accepts) VALUES (?,?,?,?)", (ng_name.strip(), ng_city.strip(), ng_contact.strip(), ng_accepts.strip()))
                        ngo_id = cur.lastrowid; conn.commit(); conn.close()
                        ok, err = create_user(ng_user.strip(), ng_pass.strip(), role="ngo", ngo_id=int(ngo_id))
                        if ok:
                            st.success("NGO created. Please login as admin user.")
                            safe_rerun()
                        else:
                            st.error(err)
                    except Exception as e:
                        st.error("DB write failed: " + str(e))
    st.markdown("</div>", unsafe_allow_html=True)

def dashboard():
    st.markdown("<div class='bigcard'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Dashboard</div>", unsafe_allow_html=True)
    user = st.session_state["user"]
    ngos_df = get_all_ngos_df()
    shelf_df = get_shelf_df()
    don_df = get_donations_df()
    c1,c2,c3 = st.columns(3)
    c1.metric("🏢 NGOs", len(ngos_df))
    c2.metric("📦 Shelf entries", len(shelf_df))
    c3.metric("🩺 Donations", len(don_df))

    st.markdown("### Live controls")
    colA, colB = st.columns([1,3])
    with colA:
        if st.button("🔄 Refresh"):
            safe_rerun()
    with colB:
        st.write("Donations write instantly and appear below. Use Refresh in other tabs if needed.")

    left, right = st.columns([2,1])
    with left:
        st.subheader("🧾 Donate a Medicine")
        with st.form("don_form"):
            if user and user.get("username") not in (None, "guest"):
                d_name = st.text_input("Donor name", value=user["username"], key="donor_name", disabled=True)
            else:
                d_name = st.text_input("Donor name", key="donor_name")
            d_city = st.text_input("City", key="donor_city")
            d_med_raw = st.text_input("Medicine (name)", key="don_med")
            d_med = canonicalize_med_name(d_med_raw)
            d_mfg = st.date_input("Manufacture/Purchase date", value=date.today(), key="don_mfg")
            d_printed = st.text_input("Printed expiry (optional)", help="e.g. YYYY-MM-DD or DD/MM/YYYY", key="don_printed")
            d_pref = st.selectbox("Preferred NGO (optional)", options=["(Any)"] + ngos_df["name"].tolist(), key="don_pref")
            submit = st.form_submit_button("Check & Submit")
        if submit:
            if not d_name or not d_med:
                st.error("Donor and medicine required")
            else:
                expiry_obj, expiry_err = (None, None)
                if d_printed and d_printed.strip():
                    expiry_obj, expiry_err = parse_date_flexible(d_printed.strip())
                    if expiry_err:
                        st.error("Printed expiry parse error: " + expiry_err)
                if (not d_printed or not d_printed.strip()) and d_mfg:
                    sf = shelf_df[shelf_df["medicine_name"].str.lower()==d_med.lower()] if not shelf_df.empty else pd.DataFrame()
                    if not sf.empty:
                        months = int(sf.iloc[0]["shelf_months"])
                        approx = (pd.to_datetime(d_mfg) + pd.DateOffset(months=months)).date()
                        expiry_obj = approx
                        st.info(f"No printed expiry: approx expiry = {approx.isoformat()}")
                if expiry_obj:
                    if expiry_obj < date.today():
                        st.error("This medicine is expired — donation not accepted.")
                        allow = False
                    else:
                        st.success(f"Expiry OK: {expiry_obj.isoformat()}")
                        allow = True
                else:
                    st.warning("No expiry provided; the recipient NGO may request inspection.")
                    allow = True
                if allow:
                    matches = ngos_df
                    if d_city:
                        matches = matches[matches["city"].str.lower()==d_city.strip().lower()]
                    if d_pref != "(Any)":
                        matches = matches[matches["name"]==d_pref]
                    chosen = None
                    if not matches.empty:
                        st.dataframe(matches[["id","name","city","contact","accepts"]])
                        chosen = st.selectbox("Choose NGO ID", options=["(None)"] + matches["id"].astype(str).tolist(), key="choose_ngo_id")
                        if chosen=="(None)": chosen=None
                    if st.button("✅ Confirm Donation"):
                        matched = int(chosen) if chosen else None
                        ed_str = expiry_obj.isoformat() if expiry_obj else ""
                        try:
                            new_id = insert_donation(d_name.strip(), d_city.strip(), d_med.strip(), d_mfg.isoformat(), ed_str, "pledged", matched)
                            st.success(f"Donation recorded (id={new_id}) — it appears below. Use Refresh on other tabs.")
                            safe_rerun()
                        except Exception as e:
                            st.error("Failed to record donation: " + str(e))
        st.write("---")
        st.subheader("Recent Donations (live)")
        recent = get_donations_df(200)
        st.dataframe(recent)

        st.markdown("#### Debug: last 10 donations (direct DB read)")
        try:
            conn = connect_db(); cur = conn.cursor()
            rows = cur.execute("SELECT id, donor_name, donor_city, medicine_name, batch_date, expiry_date, matched_ngo_id, created_at FROM donations ORDER BY id DESC LIMIT 10").fetchall()
            conn.close()
            st.write(rows)
        except Exception as e:
            st.error("Debug read failed: " + str(e))

        if user and user.get("username") not in (None, "guest"):
            st.markdown("#### Your donations & NGO replies")
            my_con_df = get_connections_for_donor(user["username"])
            if my_con_df.empty:
                st.info("No NGO has responded to your donations yet.")
            else:
                display_df = my_con_df[[
                    "donation_id",
                    "medicine_name",
                    "ngo_name",
                    "ngo_city",
                    "ngo_contact",
                    "message",
                    "created_at",
                    "status",
                ]].rename(columns={
                    "donation_id": "Donation ID",
                    "medicine_name": "Medicine",
                    "ngo_name": "NGO",
                    "ngo_city": "NGO City",
                    "ngo_contact": "NGO Contact",
                    "message": "NGO Message",
                    "created_at": "Connected At",
                    "status": "Donation Status",
                })
                st.dataframe(display_df)

    with right:
        st.subheader("Image Upload (optional)")
        st.write("Upload a photo of the medicine pack (we validate file only).")
        img_file = st.file_uploader("Photo (jpg/png)", type=["jpg","jpeg","png"])
        if img_file:
            st.image(img_file, use_column_width=True, caption="Uploaded image")
            try:
                img = Image.open(img_file)
                img.verify()
                st.info("Image looks okay. Please type expiry if unreadable.")
            except Exception as e:
                st.error("Image invalid: " + str(e))

        st.write("---")
        st.subheader("Audio for STT (optional)")
        st.write("Upload an audio clip (wav/mp3) to transcribe (HF token required).")
        audio = st.file_uploader("Upload audio", type=["wav","mp3","m4a"])
        if audio:
            local_path = UPLOADS_DIR / f"{int(time.time())}_{audio.name.replace(' ','_')}"
            with open(local_path, "wb") as f: f.write(audio.read())
            st.success(f"Saved audio to {local_path}")
            trans, err = hf_whisper_transcribe(str(local_path))
            if err:
                st.warning("Transcription skipped or failed: " + err)
                insert_transcription_record(local_path.name, str(local_path), st.session_state.get("user",{}).get("username","guest"), "")
            else:
                st.success("Transcription (auto): " + trans)
                insert_transcription_record(local_path.name, str(local_path), st.session_state.get("user",{}).get("username","guest"), trans)

    st.markdown("</div>", unsafe_allow_html=True)

def ngo_panel():
    st.subheader("🏥 NGO Dashboard")
    user = st.session_state["user"]
    if not user or user["role"]!="ngo":
        st.info("NGO portal — login as NGO user.")
        return
    ngo_id = user.get("ngo_id")
    if not ngo_id:
        st.error("NGO-id not linked to this user.")
        return

    row = st.columns([1,4])
    if row[0].button("🔄 Refresh donations"):
        safe_rerun()
    row[1].write("Tip: enable 'Live auto-refresh' in the sidebar to auto-reload this page every few seconds (demo).")

    st.markdown("#### Recent donations (filter & connect)")
    donations = get_donations_df(1000)
    cities = ["(Any)"] + sorted(list(donations["donor_city"].dropna().unique()))
    meds = ["(Any)"] + sorted(list(donations["medicine_name"].dropna().unique()))
    c1,c2,c3 = st.columns([2,2,1])
    sel_city = c1.selectbox("City", options=cities)
    sel_med = c2.selectbox("Medicine", options=meds)
    only_unmatched = c3.checkbox("Show unmatched only", value=True)
    df = donations.copy()
    if sel_city!="(Any)":
        df = df[df["donor_city"].str.lower()==sel_city.lower()]
    if sel_med!="(Any)":
        df = df[df["medicine_name"].str.lower()==sel_med.lower()]
    if only_unmatched:
        df = df[df["matched_ngo_id"].isnull() | (df["matched_ngo_id"]=="")]
    st.write(f"Showing {len(df)} donations.")
    st.dataframe(df[["id","donor_name","donor_city","medicine_name","batch_date","expiry_date","status","created_at"]])

    st.markdown("#### Connect to donor")
    chosen = st.selectbox("Choose donation id", options=["(None)"] + df["id"].astype(str).tolist(), key="ngo_choose")
    msg = st.text_area("Message to donor (optional)", placeholder="We can pick up your donation...")
    if st.button("✉️ Connect"):
        if chosen=="(None)":
            st.warning("Select donation id")
        else:
            try:
                connect_donation_to_ngo(int(chosen), ngo_id, msg.strip())
                st.success("Connected and donation linked to your NGO.")
                safe_rerun()
            except Exception as e:
                st.error("Connect failed: " + str(e))

    st.markdown("#### Your NGO connections")
    con_df = get_connections_for_ngo(ngo_id)
    if con_df.empty:
        st.info("No connections yet")
    else:
        st.dataframe(con_df[["id","donation_id","donor_name","donor_city","medicine_name","message","created_at"]])

def admin_panel():
    st.subheader("🔧 Admin Panel")
    user = st.session_state["user"]
    if not user or user["role"]!="admin":
        st.info("Admin only")
        return
    st.markdown("#### NGOs")
    st.dataframe(get_all_ngos_df())
    st.markdown("#### Add / Update shelf-life")
    mname = st.text_input("Medicine name", key="admin_mname")
    mmonths = st.number_input("Shelf months", min_value=1, max_value=240, value=12, key="admin_mmonths")
    mnotes = st.text_input("Notes", key="admin_mnotes")
    if st.button("➕ Add / Update"):
        if not mname:
            st.error("Provide medicine name")
        else:
            conn = connect_db(); conn.execute("INSERT OR REPLACE INTO shelf_life (medicine_name,shelf_months,notes) VALUES (?,?,?)", (mname.strip().capitalize(), int(mmonths), mnotes.strip()))
            conn.commit(); conn.close()
            st.success("Shelf entry saved")
            safe_rerun()
    st.markdown("#### All donations")
    st.dataframe(get_donations_df(1000))

# Router
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user" not in st.session_state:
    st.session_state["user"] = None

if not st.session_state["logged_in"]:
    landing_page()
else:
    user = st.session_state["user"]
    if user["role"]=="admin":
        admin_panel()
    elif user["role"]=="ngo":
        ngo_panel()
    else:
        dashboard()
