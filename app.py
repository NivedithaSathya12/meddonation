# app.py
"""
Medicine Donation Assistant — login-first version
- Landing: Login / Register (first view)
- After login: Dashboard with donation form, image checker, admin/NGO views
- Sidebar: dedicated Chat assistant (text/STT paste) available after login
- Clean visuals, icons, helpful UX
- Requires: streamlit, pandas, requests, Pillow, gTTS (gTTS optional)
- HF API token still read from st.secrets["HF_API_TOKEN"] or environment var HF_API_TOKEN
- PPT file referenced at: /mnt/data/mini_projectruchi[1]2 (1).pptx
"""

import os, tempfile, json, sqlite3, hashlib
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd
import requests
from PIL import Image

# ---------------------------
# Config
# ---------------------------
PPT_FILE_PATH = "/mnt/data/mini_projectruchi[1]2 (1).pptx"
DB_FILE = "meddonation.db"

# ---------------------------
# DB helpers
# ---------------------------
def _connect(db_path=DB_FILE):
    return sqlite3.connect(db_path)

def _ensure_tables():
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT,
        ngo_id INTEGER
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
      CREATE TABLE IF NOT EXISTS shelf_life (
        id INTEGER PRIMARY KEY,
        medicine_name TEXT UNIQUE,
        shelf_months INTEGER,
        notes TEXT
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
    conn.commit()
    conn.close()

_ensure_tables()

def hash_password(password: str, salt: str = "medsalt"):
    return hashlib.sha256((salt + password).encode()).hexdigest()

def create_user(username, password, role="donor", ngo_id=None):
    try:
        conn = _connect(); cur = conn.cursor()
        cur.execute("INSERT INTO users (username,password_hash,role,ngo_id) VALUES (?,?,?,?)",
                    (username, hash_password(password), role, ngo_id))
        conn.commit(); conn.close(); return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print("create_user error", e); return False

def verify_user(username, password):
    conn = _connect(); cur = conn.cursor()
    cur.execute("SELECT id,password_hash,role,ngo_id FROM users WHERE username=?", (username,))
    row = cur.fetchone(); conn.close()
    if not row: return None
    if row[1] == hash_password(password):
        return {"id": row[0], "username": username, "role": row[2], "ngo_id": row[3]}
    return None

def insert_ngo(name, city, contact, accepts):
    try:
        conn = _connect(); cur = conn.cursor()
        cur.execute("INSERT INTO ngos (name,city,contact,accepts) VALUES (?,?,?,?)",(name,city,contact,accepts))
        nid = cur.lastrowid; conn.commit(); conn.close(); return nid
    except Exception as e:
        print("insert_ngo", e); return None

def get_all_ngos_df():
    try:
        conn = _connect(); df = pd.read_sql_query("SELECT * FROM ngos", conn); conn.close(); return df
    except Exception as e:
        print("get_all_ngos_df", e); return pd.DataFrame(columns=["id","name","city","contact","accepts"])

def get_shelf_df():
    try:
        conn = _connect(); df = pd.read_sql_query("SELECT * FROM shelf_life", conn); conn.close(); return df
    except Exception: return pd.DataFrame(columns=["id","medicine_name","shelf_months","notes"])

def insert_donation(donor_name, medicine_name, batch_date, expiry_date, status, matched_ngo_id):
    try:
        conn = _connect(); cur = conn.cursor()
        cur.execute("INSERT INTO donations (donor_name,medicine_name,batch_date,expiry_date,status,matched_ngo_id) VALUES (?,?,?,?,?,?)",
                    (donor_name, medicine_name, batch_date, expiry_date, status, matched_ngo_id))
        conn.commit(); conn.close(); return True
    except Exception as e:
        print("insert_donation", e); return False

def get_donations_df(limit=500):
    try:
        conn = _connect(); df = pd.read_sql_query("SELECT * FROM donations ORDER BY id DESC LIMIT ?", conn, params=(limit,)); conn.close(); return df
    except Exception as e:
        print("get_donations_df", e); return pd.DataFrame()

# ---------------------------
# HF wrapper helpers (light)
# ---------------------------
HF_API_TOKEN = None
try:
    HF_API_TOKEN = st.secrets["HF_API_TOKEN"]
except Exception:
    HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}

def hf_text_inference(model_name, inputs, params=None, timeout=60):
    if not HF_API_TOKEN:
        return {"error": "HF_API_TOKEN not set."}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    payload = {"inputs": inputs}
    if params: payload["parameters"] = params
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=timeout); r.raise_for_status(); return r.json()
    except Exception as e:
        return {"error": str(e)}

def hf_stt_inference(model_name, audio_bytes, timeout=120):
    if not HF_API_TOKEN: return {"error": "HF_API_TOKEN not set."}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    try:
        r = requests.post(url, headers=HEADERS, data=audio_bytes, timeout=timeout); r.raise_for_status(); return r.json()
    except Exception as e:
        return {"error": str(e)}

def hf_image_classify(model_name, image_bytes, timeout=60):
    if not HF_API_TOKEN: return {"error": "HF_API_TOKEN not set."}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    try:
        files = {"file": image_bytes}; r = requests.post(url, headers=HEADERS, files=files, timeout=timeout); r.raise_for_status(); return r.json()
    except Exception as e:
        return {"error": str(e)}

# ---------------------------
# UI config & styles
# ---------------------------
st.set_page_config(page_title="Medicine Donation Assistant", page_icon="💊", layout="wide")
st.markdown("""
<style>
body { font-family: "Segoe UI", Roboto, Arial, sans-serif; }
.header-card { background: linear-gradient(90deg,#f9fbff,#ffffff); padding:14px; border-radius:8px; margin-bottom:10px; display:flex; gap:12px; align-items:center; }
.header-card img { width:60px; }
.login-box { max-width:520px; margin: 12px auto; padding: 18px; border-radius:10px; box-shadow: 0 6px 18px rgba(10,20,50,0.06); background:white; }
.welcome { color:#234; font-weight:600; }
.small-muted { color:#667; font-size:14px; }
.card { padding:10px; border-radius:8px; background:white; box-shadow:0 6px 18px rgba(10,20,50,0.04); }
.sidebar-chat { margin-top:18px; padding:8px; border-radius:8px; background:#fff; box-shadow:0 6px 18px rgba(10,20,50,0.04); }
</style>
""", unsafe_allow_html=True)

# ---------- app flow control ----------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user" not in st.session_state:
    st.session_state["user"] = None
if "assistant_history" not in st.session_state:
    st.session_state["assistant_history"] = []

# ---------------------------
# Landing page (Login/Register)
# ---------------------------
def landing_page():
    st.markdown('<div class="header-card"><img src="https://img.icons8.com/fluency/96/pill.png"/><div><h1 style="margin:0">Medicine Donation Assistant</h1><div class="small-muted">Voice-friendly • Photo-check • Multi-language • NGO/Donor workflows</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown('<div style="display:flex; justify-content:space-between; align-items:center;"><h2 style="margin:0">Welcome</h2><div style="color:#666">New? Register below</div></div>', unsafe_allow_html=True)
    st.markdown('<p class="small-muted">Please login or register to continue. This first page protects the dashboard and improves UX for users who only need to login.</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Login")
        lu = st.text_input("Username", key="login_user", placeholder="your username")
        lp = st.text_input("Password", key="login_pass", type="password")
        if st.button("Login"):
            if not lu or not lp:
                st.warning("Provide username and password.")
            else:
                user = verify_user(lu.strip(), lp.strip())
                if user:
                    st.success(f"Logged in as {user['username']} ({user['role']})")
                    st.session_state["logged_in"] = True
                    st.session_state["user"] = user
                    # safe rerun
                    try:
                        st.experimental_rerun()
                    except Exception:
                        pass
                else:
                    st.error("Invalid credentials.")
        if st.button("Continue as Guest (view only)"):
            st.info("Guest mode: limited features.")
            st.session_state["logged_in"] = True
            st.session_state["user"] = {"username":"guest","role":"guest","id":0,"ngo_id":None}
            try:
                st.experimental_rerun()
            except:
                pass

    with col2:
        st.subheader("Register")
        rtype = st.radio("Register as", ["Donor","NGO"], horizontal=True)
        if rtype == "Donor":
            du = st.text_input("Choose username", key="reg_d_user")
            dp = st.text_input("Choose password", key="reg_d_pass", type="password")
            if st.button("Register Donor"):
                if not du or not dp:
                    st.error("Provide username and password.")
                else:
                    ok = create_user(du.strip(), dp.strip(), role="donor")
                    if ok:
                        st.success("Donor created — please login on the left.")
                    else:
                        st.error("Username exists or registration failed.")
        else:
            ng_name = st.text_input("NGO Name", key="reg_ngo_name")
            ng_city = st.text_input("City", key="reg_ngo_city")
            ng_contact = st.text_input("Contact", key="reg_ngo_contact")
            ng_accepts = st.text_input("Accepts (comma sep)", key="reg_ngo_accepts")
            ng_user = st.text_input("Choose username", key="reg_ngo_user")
            ng_pass = st.text_input("Choose password", key="reg_ngo_pass", type="password")
            if st.button("Register NGO"):
                if not ng_name or not ng_user or not ng_pass:
                    st.error("Enter NGO name and credentials.")
                else:
                    nid = insert_ngo(ng_name.strip(), ng_city.strip(), ng_contact.strip(), ng_accepts.strip())
                    if nid:
                        ok = create_user(ng_user.strip(), ng_pass.strip(), role="ngo", ngo_id=int(nid))
                        if ok:
                            st.success("NGO registered — please login.")
                        else:
                            st.error("Username exists or failed.")
                    else:
                        st.error("Failed to create NGO row.")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------
# Dashboard (post-login)
# ---------------------------
def dashboard():
    # header + optional PPT download
    st.markdown('<div class="header-card"><img src="https://img.icons8.com/fluency/96/pill.png"/><div><h1 style="margin:0">Welcome to Medicine Donation Assistant</h1><div class="small-muted">Easy donation checks • NGO matching • image & speech support</div></div></div>', unsafe_allow_html=True)
    # show PPT download if exists (quiet)
    try:
        if Path(PPT_FILE_PATH).exists():
            with st.expander("📄 Project PPT (download)"):
                with open(PPT_FILE_PATH, "rb") as f:
                    st.download_button("⬇️ Download project PPT", data=f.read(), file_name="mini_project_reference.pptx")
    except Exception:
        pass

    ngos_df = get_all_ngos_df(); shelf_df = get_shelf_df(); don_df = get_donations_df()
    c1,c2,c3 = st.columns(3)
    c1.metric("NGOs", len(ngos_df)); c2.metric("Shelf items", len(shelf_df)); c3.metric("Donations", len(don_df))
    st.write("---")

    # two-column layout: donation form + media tools
    left, right = st.columns([2,1])
    with left:
        st.subheader("Donate a Medicine")
        with st.form("don_form"):
            d_name = st.text_input("Donor name", value=st.session_state["user"]["username"] if st.session_state["user"] else "")
            d_city = st.text_input("City")
            d_med = st.text_input("Medicine (name)")
            d_mfg = st.date_input("Manufacture/Purchase date", value=datetime.today())
            d_printed = st.text_input("Printed expiry (YYYY-MM-DD) (optional)")
            d_pref = st.selectbox("Preferred NGO (optional)", options=["(Any)"] + ngos_df["name"].tolist())
            sub = st.form_submit_button("Check & Submit")
        if sub:
            if not d_name or not d_med:
                st.error("Provide donor name and medicine.")
            else:
                expiry_iso = d_printed.strip() or None
                allowed = True; reason = "Looks OK (basic check)"
                if expiry_iso:
                    try:
                        ed = datetime.fromisoformat(expiry_iso).date()
                        if ed < datetime.today().date():
                            allowed = False; reason = "Printed expiry is past."
                    except:
                        allowed = False; reason = "Invalid expiry format."
                else:
                    # shelf estimate if available
                    sf = shelf_df[shelf_df["medicine_name"].str.lower()==d_med.strip().lower()] if not shelf_df.empty else pd.DataFrame()
                    if not sf.empty:
                        months = int(sf.iloc[0]["shelf_months"])
                        approx = (pd.to_datetime(d_mfg) + pd.DateOffset(months=months)).date()
                        if approx < datetime.today().date():
                            allowed = False; reason = "Likely expired given shelf life."
                if not allowed:
                    st.warning(reason)
                else:
                    st.success(reason)
                    matches = ngos_df
                    if d_city: matches = matches[matches["city"].str.lower()==d_city.strip().lower()]
                    if d_pref != "(Any)": matches = matches[matches["name"]==d_pref]
                    if matches.empty:
                        st.info("No matching NGO found.")
                    else:
                        st.dataframe(matches[["id","name","city","contact","accepts"]])
                        chosen = st.selectbox("Choose NGO ID", matches["id"].astype(str).tolist())
                        if st.button("Confirm Donation"):
                            ok = insert_donation(d_name.strip(), d_med.strip(), d_mfg.isoformat(), expiry_iso, "pledged", int(chosen))
                            if ok:
                                st.success("Donation recorded. Thank you.")
                            else:
                                st.error("Failed to record donation.")

    with right:
        st.subheader("Image / Media Tools")
        st.markdown("Upload a clear tablet/blister photo or short audio for STT.")
        img = st.file_uploader("Tablet photo", type=["jpg","jpeg","png"])
        if img:
            im = Image.open(img).convert("RGB"); st.image(im, use_column_width=True, caption="Uploaded")
            if st.button("Analyze image"):
                bio = img.read()
                res = hf_image_classify("google/vit-base-patch16-224", bio)
                if isinstance(res, dict) and res.get("error"):
                    st.error("Image API error: " + str(res.get("error")))
                else:
                    st.write("Predictions (top):")
                    if isinstance(res, list):
                        for p in res[:6]:
                            lab = p.get("label", str(p)); sc = p.get("score",0.0)
                            st.write(f"- **{lab}** — {sc:.2f}")
        audio = st.file_uploader("Audio for STT (wav/mp3)", type=["wav","mp3","m4a"])
        stt_model = st.text_input("STT model (HF)", value="openai/whisper-tiny")
        if st.button("Transcribe audio") and audio:
            res = hf_stt_inference(stt_model, audio.read())
            if isinstance(res, dict) and res.get("error"):
                st.error("STT error: " + str(res.get("error")))
            else:
                text = ""
                if isinstance(res, dict) and "text" in res: text = res["text"]
                elif isinstance(res, list):
                    try: text = " ".join([seg.get("text","") for seg in res if isinstance(seg, dict)])
                    except: text = str(res)
                elif isinstance(res, str): text = res
                st.success("Transcribed:")
                st.text_area("Transcription (edit if required)", value=text, height=140, key="transcript_area")
                # also send to chat input, to be used easily
                st.session_state["assistant_history"].append({"role":"user","text": text})

    st.write("---")
    # Admin / NGO quick panels
    if st.session_state["user"] and st.session_state["user"]["role"] == "admin":
        st.subheader("Admin: Quick view")
        st.dataframe(get_all_ngos_df())
        st.dataframe(get_shelf_df())
    elif st.session_state["user"] and st.session_state["user"]["role"] == "ngo":
        st.subheader("Your NGO details")
        ngos = get_all_ngos_df()
        myid = st.session_state["user"]["ngo_id"]
        if myid in (ngos["id"].tolist() if not ngos.empty else []):
            st.write(ngos[ngos["id"]==myid])
        else:
            st.info("NGO row not found.")

# ---------------------------
# Sidebar: Chat + quick nav + logout
# ---------------------------
def sidebar_chat_and_nav():
    st.sidebar.markdown("## 🔐 Account")
    if st.session_state["logged_in"]:
        st.sidebar.write("**User:**", st.session_state["user"]["username"])
        st.sidebar.write("**Role:**", st.session_state["user"]["role"])
        if st.sidebar.button("Logout"):
            st.session_state["logged_in"] = False
            st.session_state["user"] = None
            try: st.experimental_rerun()
            except: pass
    else:
        st.sidebar.info("Please login or register on the main page.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 💬 Assistant")
    st.sidebar.markdown("Ask simple questions about donating medicines, expiry, or paste transcribed text.")
    chat_text = st.sidebar.text_area("Message (type or paste STT)", key="sidebar_chat_input", height=110)
    if st.sidebar.button("Send to Assistant"):
        if not chat_text.strip(): st.sidebar.warning("Type or paste some text.")
        else:
            st.session_state["assistant_history"].append({"role":"user","text":chat_text.strip()})
            # call HF chat default (fallback if token missing)
            if HF_API_TOKEN:
                model = "microsoft/DialoGPT-medium"
                out = hf_text_inference(model, chat_text.strip(), params={"max_new_tokens":120})
                reply = ""
                if isinstance(out, dict) and out.get("error"):
                    reply = "(Model error) " + out.get("error")
                else:
                    if isinstance(out, list) and len(out)>0:
                        f = out[0]
                        if isinstance(f, dict) and "generated_text" in f: reply = f["generated_text"]
                        elif isinstance(f, str): reply = f
                        else: reply = str(f)
                    elif isinstance(out, dict) and "generated_text" in out: reply = out["generated_text"]
                    else: reply = str(out)
            else:
                # small local fallback
                q = chat_text.strip().lower()
                if "donate" in q: reply = "Use the Donate a Medicine form. Provide name, date and NGO."
                elif "expiry" in q: reply = "Check printed expiry; if none we check shelf-life DB estimates."
                else: reply = "I can help check donations, expiry and matching NGOs. Try: 'How to donate paracetamol?'"
            st.sidebar.success(reply)
            st.session_state["assistant_history"].append({"role":"assistant","text":reply})

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🔧 Quick Links")
    if st.session_state["logged_in"]:
        st.sidebar.button("Go to Dashboard")  # visual only; dashboard renders automatically when logged_in True
    else:
        st.sidebar.markdown("Please login to access the dashboard.")

# ---------------------------
# App runner
# ---------------------------
sidebar_chat_and_nav()
if not st.session_state["logged_in"]:
    landing_page()
else:
    dashboard()
