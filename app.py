# app.py
"""
Medicine Donation Assistant - full updated app.py (single file)
- No use of st.modal() (compatibility)
- Floating chat panel (auto-open) + send & TTS playback
- Speech->Text via Hugging Face Inference API (model ID editable)
- Image classification (tablet/photo) via HF Inference API
- Lightweight DB helpers (uses meddonation.db)
- PPT download shown only if file exists (silent otherwise)
- Clean UI with icons, colors and interactive elements
Requirements: streamlit, pandas, requests, Pillow, gTTS
Set HF_API_TOKEN in Streamlit Secrets (HF_API_TOKEN) or as env var.
"""

import os
import io
import json
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime
import requests
import streamlit as st
import pandas as pd
from PIL import Image

# -----------------------
# Configuration & Paths
# -----------------------
PPT_FILE_PATH = "/mnt/data/mini_projectruchi[1]2 (1).pptx"  # developer-provided file path
DB_FILE = "meddonation.db"

# -----------------------
# Ensure DB / minimal schema
# -----------------------
def _connect(db_path=DB_FILE):
    return sqlite3.connect(db_path)

def _ensure_tables():
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

_ensure_tables()

# -----------------------
# HF token (secrets or env)
# -----------------------
HF_API_TOKEN = None
try:
    # Streamlit secrets (preferred for deployed app)
    HF_API_TOKEN = st.secrets.get("HF_API_TOKEN", None)
except Exception:
    HF_API_TOKEN = None

if not HF_API_TOKEN:
    HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}

# -----------------------
# Utilities: TTS & HF wrappers
# -----------------------
def tts_bytes(text: str, lang: str = "en"):
    """Return mp3 bytes using gTTS or None if not available."""
    try:
        from gtts import gTTS
    except Exception:
        return None
    try:
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tf.close()
        tts = gTTS(text=text, lang=(lang.split("-")[0] if "-" in lang else lang))
        tts.save(tf.name)
        with open(tf.name, "rb") as f:
            data = f.read()
        try:
            os.remove(tf.name)
        except:
            pass
        return data
    except Exception:
        return None

def hf_text_inference(model_name: str, inputs: str, params: dict = None, timeout: int = 60):
    """Call HF Inference API for text generation/classification."""
    if not HF_API_TOKEN:
        return {"error": "HF_API_TOKEN not set. Add it to Streamlit Secrets or environment."}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    payload = {"inputs": inputs}
    if params:
        payload["parameters"] = params
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def hf_stt_inference(model_name: str, audio_bytes: bytes, timeout: int = 120):
    """Call HF Inference API for speech-to-text (send raw audio bytes)."""
    if not HF_API_TOKEN:
        return {"error": "HF_API_TOKEN not set."}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    try:
        r = requests.post(url, headers=HEADERS, data=audio_bytes, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def hf_image_classify(model_name: str, image_bytes: bytes, timeout: int = 60):
    """Call HF Inference API for image classification (multipart)."""
    if not HF_API_TOKEN:
        return {"error": "HF_API_TOKEN not set."}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    try:
        files = {"file": image_bytes}
        r = requests.post(url, headers=HEADERS, files=files, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# -----------------------
# DB helpers (lightweight)
# -----------------------
import hashlib
def hash_password(password: str, salt: str = "medsalt") -> str:
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
        print("get_user error:", e)
    return None

def insert_ngo(name, city, contact, accepts):
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

# -----------------------
# Heuristic: pill keywords
# -----------------------
PILL_KEYWORDS = {"pill", "tablet", "capsule", "blister", "lozenge", "medicine", "medication", "drug"}

def label_implies_pill(label: str) -> bool:
    if not label:
        return False
    lab = label.lower()
    for kw in PILL_KEYWORDS:
        if kw in lab:
            return True
    return False

# -----------------------
# UI: styling & header
# -----------------------
st.set_page_config(page_title="Medicine Donation Assistant", page_icon="💊", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background: linear-gradient(90deg,#f7fbff 0%, #ffffff 100%); }
      .hero { display:flex; gap:12px; align-items:center; padding:12px; border-radius:10px; margin-bottom:12px; background: linear-gradient(90deg,#fff,#f7fbff); }
      .hero img { width:56px; height:56px; }
      .metric-card { border-radius:10px; padding:10px; background:white; box-shadow:0 6px 18px rgba(10,30,80,0.04); }
      .chat-btn { position: fixed; right: 24px; bottom: 24px; background: linear-gradient(135deg,#ff7a18,#af002d); color: white; width:64px; height:64px; border-radius:50%; box-shadow: 0 8px 24px rgba(0,0,0,0.2); display:flex; align-items:center; justify-content:center; font-size:28px; cursor:pointer; z-index:1000; }
      .chat-panel { position: fixed; right: 24px; bottom: 100px; width: 380px; max-width: 92%; max-height: 70vh; background: white; border-radius: 12px; box-shadow: 0 12px 32px rgba(20,40,80,0.12); padding: 12px; z-index:1000; overflow:auto; }
      .chat-header { font-weight:600; font-size:16px; display:flex; justify-content:space-between; align-items:center; }
      .chat-message-user { background: #e6f0ff; padding:8px 10px; border-radius:8px; margin:8px 0; }
      .chat-message-assistant { background: #f6f7fb; padding:8px 10px; border-radius:8px; margin:8px 0; }
    </style>
    """, unsafe_allow_html=True)

st.markdown(
    f"""<div class="hero"><img src="https://img.icons8.com/fluency/96/pill.png" alt="pill"/><div>
    <h1 style="margin:0">Medicine Donation Assistant</h1>
    <div style="color:#666">Voice-friendly • Photo-check • Multi-language • Simple admin & NGO portals</div>
    </div></div>""", unsafe_allow_html=True)

# -----------------------
# Session state defaults
# -----------------------
if "user" not in st.session_state:
    st.session_state["user"] = None
if "assistant_history" not in st.session_state:
    st.session_state["assistant_history"] = []
if "assistant_query" not in st.session_state:
    st.session_state["assistant_query"] = ""
if "chat_open" not in st.session_state:
    st.session_state["chat_open"] = True  # auto-open chat panel by default

# -----------------------
# Sidebar: login & registration
# -----------------------
with st.sidebar:
    st.header("Login")
    su = st.text_input("Username", key="login_username")
    sp = st.text_input("Password", key="login_password", type="password")
    if st.button("Login"):
        if not su.strip() or not sp:
            st.warning("Enter both username and password.")
        else:
            user = get_user_by_username(su.strip())
            if not user:
                st.error("Invalid username or password.")
            else:
                conn = _connect()
                cur = conn.cursor()
                cur.execute("SELECT password_hash FROM users WHERE username=?", (su.strip(),))
                row = cur.fetchone()
                conn.close()
                if row and row[0] == hash_password(sp):
                    st.success(f"Logged in as {su.strip()} ({user['role']})")
                    st.session_state["user"] = user
                    st.experimental_rerun()
                else:
                    st.error("Invalid username or password.")

    st.markdown("---")
    st.header("Register")
    reg_type = st.radio("Register as", ["Donor", "NGO"])
    if reg_type == "Donor":
        d_un = st.text_input("Username (Donor)", key="reg_d_un")
        d_pw = st.text_input("Password (Donor)", type="password", key="reg_d_pw")
        if st.button("Register Donor"):
            if not d_un or not d_pw:
                st.error("Provide username and password.")
            elif get_user_by_username(d_un):
                st.error("Username exists.")
            else:
                ok = create_user(d_un.strip(), d_pw.strip(), role="donor", ngo_id=None)
                if ok:
                    st.success("Donor account created. Please login.")
                else:
                    st.error("Registration failed.")
    else:
        n_name = st.text_input("NGO name", key="reg_ngo_name")
        n_city = st.text_input("City", key="reg_ngo_city")
        n_contact = st.text_input("Contact phone/email", key="reg_ngo_contact")
        n_accepts = st.text_input("Accepts (comma-separated)", key="reg_ngo_accepts")
        n_un = st.text_input("Username (NGO)", key="reg_ngo_un")
        n_pw = st.text_input("Password (NGO)", type="password", key="reg_ngo_pw")
        if st.button("Register NGO"):
            if not n_name.strip() or not n_un.strip() or not n_pw.strip():
                st.error("Provide NGO name and login credentials.")
            elif get_user_by_username(n_un.strip()):
                st.error("Username exists.")
            else:
                nid = insert_ngo(n_name.strip(), n_city.strip(), n_contact.strip(), n_accepts.strip())
                if nid:
                    ok = create_user(n_un.strip(), n_pw.strip(), role="ngo", ngo_id=int(nid))
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

    # show HF token state quietly
    if HF_API_TOKEN:
        st.success("HF token: available")
    else:
        st.info("HF token: not set (add to Streamlit Secrets or env).")

# -----------------------
# Top metrics & PPT download (silent if missing)
# -----------------------
ngos_df = get_all_ngos_df()
shelf_df = get_shelf_df()
don_df = get_donations_df(limit=1000)
c1, c2, c3 = st.columns(3)
c1.metric("NGOs", len(ngos_df))
c2.metric("Shelf items", len(shelf_df))
c3.metric("Donations", len(don_df))

# PPT download only shown if file exists (no noisy message)
try:
    if Path(PPT_FILE_PATH).exists():
        with st.expander("📄 Project PPT (download)"):
            with open(PPT_FILE_PATH, "rb") as f:
                ppt_bytes = f.read()
            st.download_button("⬇️ Download PPT (project reference)", data=ppt_bytes, file_name="mini_project_reference.pptx")
except Exception:
    pass

st.write("---")

# -----------------------
# Main columns: donation form + assistant features
# -----------------------
col1, col2 = st.columns([2,1])

with col1:
    st.header("Donate a Medicine (Public)")
    with st.form("donate_form"):
        dn_name = st.text_input("Donor name")
        dn_city = st.text_input("City (for NGO matching)")
        dn_med = st.text_input("Medicine name (e.g., Paracetamol 500mg)")
        dn_mfg = st.date_input("Manufacture / Purchase date", value=datetime.today())
        dn_printed_expiry = st.text_input("Printed expiry (optional, YYYY-MM-DD)")
        dn_pref = st.selectbox("Prefer NGO (optional)", options=["(Any)"] + ngos_df["name"].tolist())
        donate_submit = st.form_submit_button("Check & Submit")
    if donate_submit:
        if not dn_name.strip() or not dn_med.strip():
            st.error("Provide name and medicine.")
        else:
            expiry_iso = dn_printed_expiry.strip() or None
            allowed = True
            reason = "Looks OK (basic check)."
            if expiry_iso:
                try:
                    ed = datetime.fromisoformat(expiry_iso).date()
                    if ed < datetime.today().date():
                        allowed = False
                        reason = "This medicine is already expired."
                except:
                    allowed = False
                    reason = "Expiry date format invalid (use YYYY-MM-DD)."
            else:
                # shelf life lookup
                sf = shelf_df[shelf_df["medicine_name"].str.lower()==dn_med.strip().lower()] if not shelf_df.empty else pd.DataFrame()
                if not sf.empty:
                    months = int(sf.iloc[0]["shelf_months"])
                    approx_exp = (pd.to_datetime(dn_mfg) + pd.DateOffset(months=months)).date()
                    if approx_exp < datetime.today().date():
                        allowed = False
                        reason = "Likely expired based on shelf-life estimate."
            if not allowed:
                st.warning(reason)
            else:
                st.success(reason)
                matches = ngos_df
                if dn_city.strip():
                    matches = matches[matches["city"].str.lower()==dn_city.strip().lower()]
                if dn_pref != "(Any)":
                    matches = matches[matches["name"]==dn_pref]
                if matches.empty:
                    st.info("No matching NGO found. Admin will be notified.")
                else:
                    st.dataframe(matches[["id","name","city","contact","accepts"]])
                    chosen_id = st.selectbox("Choose NGO ID to donate to", matches["id"].astype(str).tolist())
                    if st.button("Confirm Donation"):
                        ok = insert_donation(dn_name.strip(), dn_med.strip(), dn_mfg.isoformat(), expiry_iso, "pledged", int(chosen_id))
                        if ok:
                            st.success("Donation recorded. Thank you!")
                        else:
                            st.error("Failed to record donation.")

    st.write("---")
    st.header("Assistant — Speech → Text & Chat")
    st.markdown("Upload a short audio (wav/mp3/m4a) or type text. Select models if you host custom HF models.")

    # STT upload
    audio_file = st.file_uploader("Upload audio for STT", type=["wav","mp3","m4a"])
    st.selectbox("STT language", ["en","hi","bn","ta","te","ml","gu","mr","kn","or","pa","as"], key="stt_lang", index=0)
    stt_model = st.text_input("STT model (HF)", value="openai/whisper-tiny", help="e.g., openai/whisper-tiny")
    if st.button("Transcribe audio"):
        if not audio_file:
            st.warning("Upload audio first.")
        else:
            audio_bytes = audio_file.read()
            st.info("Transcribing via HF inference...")
            res = hf_stt_inference(stt_model, audio_bytes)
            if isinstance(res, dict) and res.get("error"):
                st.error("STT error: " + str(res.get("error")))
            else:
                # extract text
                transcribed = None
                if isinstance(res, dict) and "text" in res:
                    transcribed = res["text"]
                elif isinstance(res, list):
                    try:
                        transcribed = " ".join([seg.get("text","") for seg in res if isinstance(seg, dict)])
                    except:
                        transcribed = str(res)
                elif isinstance(res, str):
                    transcribed = res
                else:
                    transcribed = json.dumps(res)[:1000]
                st.success("Transcription:")
                st.text_area("Transcribed text (edit if needed)", value=transcribed, height=140, key="transcript_box")
                st.session_state["assistant_query"] = transcribed

    # typed input
    user_q = st.text_input("Or type your question for assistant", key="typed_query", value=st.session_state.get("assistant_query",""))
    if st.button("Ask Assistant (send to chat)"):
        qtxt = st.session_state.get("typed_query","").strip()
        if not qtxt:
            st.warning("Type or transcribe some text first.")
        else:
            st.session_state["assistant_history"].append({"role":"user","text":qtxt})
            # We'll call HF from the chat panel logic below (so it's centralized)

with col2:
    st.header("Image / Tablet Checker")
    st.markdown("Upload a clear photo of the tablet or its blister pack. The model will try to detect if it's a tablet/capsule.")
    img_file = st.file_uploader("Upload Tablet Photo", type=["jpg","jpeg","png"])
    image_model = st.text_input("Image model (HF)", value="google/vit-base-patch16-224", help="Try HF image-classification models")
    if img_file:
        img = Image.open(img_file).convert("RGB")
        st.image(img, caption="Uploaded image", use_column_width=True)
        if st.button("Analyze image"):
            st.info("Calling image model...")
            bio = img_file.read()
            res = hf_image_classify(image_model, bio)
            if isinstance(res, dict) and res.get("error"):
                st.error("Image API error: " + str(res.get("error")))
            else:
                preds = []
                if isinstance(res, list):
                    for p in res:
                        if isinstance(p, dict):
                            label = p.get("label") or p.get("class") or str(p)
                            score = float(p.get("score", 0.0))
                            preds.append((label, score))
                        else:
                            preds.append((str(p), 0.0))
                elif isinstance(res, dict):
                    if "labels" in res and isinstance(res["labels"], list):
                        for p in res["labels"]:
                            if isinstance(p, dict):
                                preds.append((p.get("label",""), float(p.get("score",0.0))))
                            else:
                                preds.append((str(p), 0.0))
                    elif "label" in res:
                        preds.append((res.get("label",""), float(res.get("score",0.0))))
                    else:
                        preds.append((str(res), 0.0))
                st.subheader("Top predictions")
                for lab, sc in preds[:8]:
                    st.write(f"- **{lab}** — {sc:.2f}")
                top_label = preds[0][0] if preds else ""
                likely_tablet = label_implies_pill(top_label)
                if not likely_tablet:
                    for lab, sc in preds:
                        if label_implies_pill(lab):
                            likely_tablet = True
                            break
                if likely_tablet:
                    st.success("Heuristic result: Image likely contains a tablet/capsule. Check printed expiry manually.")
                else:
                    st.warning("Heuristic result: Model did not detect a tablet/capsule label. Manual verification recommended.")

# -----------------------
# Floating Chat Panel (no st.modal)
# -----------------------
# Render floating chat button and panel (HTML + widgets)
st.markdown('<div style="position:fixed; right:24px; bottom:24px; z-index:1000">', unsafe_allow_html=True)
if st.button("💬", key="floating_chat_toggle"):
    st.session_state["chat_open"] = not st.session_state["chat_open"]
st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.get("chat_open", True):
    # Render panel in a container so it appears above main content
    chat_container = st.container()
    with chat_container:
        st.markdown('<div class="chat-panel">', unsafe_allow_html=True)
        st.markdown('<div class="chat-header">🤖 Assistant <span style="font-size:12px;color:#666"> (voice & image aware)</span></div>', unsafe_allow_html=True)

        # Show history messages
        for msg in st.session_state["assistant_history"]:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-message-user">👤 {msg["text"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-message-assistant">🤖 {msg["text"]}</div>', unsafe_allow_html=True)

        # Chat input and send
        chat_input = st.text_area("Message", key="chat_input_area", height=100, placeholder="Type a question or paste transcribed text here...")
        colA, colB = st.columns([4,1])
        with colB:
            if st.button("Send", key="chat_send_btn"):
                q = (st.session_state.get("chat_input_area","") or "").strip()
                if not q:
                    st.warning("Type a message.")
                else:
                    # Append user message
                    st.session_state["assistant_history"].append({"role":"user","text":q})
                    # Choose model and call HF
                    chat_model_default = "microsoft/DialoGPT-medium"
                    chat_model = st.text_input("Chat model (HF)", value=chat_model_default, key="chat_model_input")
                    with st.spinner("Assistant is typing..."):
                        out = hf_text_inference(chat_model, q, params={"max_new_tokens":150})
                    # Parse reply
                    reply_text = ""
                    if isinstance(out, dict) and out.get("error"):
                        reply_text = f"(Model error) {out.get('error')}"
                    else:
                        if isinstance(out, list) and len(out)>0:
                            first = out[0]
                            if isinstance(first, dict) and "generated_text" in first:
                                reply_text = first["generated_text"]
                            elif isinstance(first, str):
                                reply_text = first
                            else:
                                reply_text = str(first)
                        elif isinstance(out, dict) and "generated_text" in out:
                            reply_text = out["generated_text"]
                        else:
                            reply_text = str(out)
                    st.session_state["assistant_history"].append({"role":"assistant","text":reply_text})
                    # TTS playback if available
                    audio_b = tts_bytes(reply_text, lang="en")
                    if audio_b:
                        # st.audio displays a player in the chat panel
                        st.audio(audio_b, format="audio/mp3")
                    # Clear input area
                    st.session_state["chat_input_area"] = ""
                    # re-render so user sees the new messages immediately
                    st.experimental_rerun()

        st.markdown('</div>', unsafe_allow_html=True)

# -----------------------
# Role-specific admin / NGO sections
# -----------------------
if st.session_state["user"] and st.session_state["user"]["role"] == "admin":
    st.header("Admin Panel")
    st.subheader("NGO list")
    st.dataframe(ngos_df)
    st.subheader("Shelf-life")
    st.dataframe(shelf_df)
    st.subheader("Donations")
    st.dataframe(don_df)
    # Admin: create NGO user
    st.subheader("Create NGO user")
    new_un = st.text_input("Username", key="adm_new_un")
    new_pw = st.text_input("Password", type="password", key="adm_new_pw")
    assign_ngo = st.selectbox("Assign NGO ID", options=ngos_df["id"].tolist() if not ngos_df.empty else [0], key="adm_assign_ngo")
    if st.button("Create NGO user"):
        if not new_un or not new_pw:
            st.error("Provide username and password.")
        else:
            ok = create_user(new_un.strip(), new_pw.strip(), role="ngo", ngo_id=int(assign_ngo))
            if ok:
                st.success("User created.")
            else:
                st.error("Failed to create user (username may exist).")
    # Edit NGO
    st.subheader("Edit NGO")
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
                ok = update_ngo(edit_id, name_new, city_new, contact_new, accepts_new)
                if ok:
                    st.success("NGO updated.")
                    st.experimental_rerun()
                else:
                    st.error("Update failed.")
    # Delete donation
    st.subheader("Delete donation")
    delid = st.number_input("Donation ID to delete", min_value=0, step=1, key="delid_admin")
    if st.button("Delete donation now"):
        if delid > 0:
            ok = delete_donation(int(delid))
            if ok:
                st.success("Deleted.")
                st.experimental_rerun()
            else:
                st.error("Failed to delete.")

elif st.session_state["user"] and st.session_state["user"]["role"] == "ngo":
    st.header("NGO Portal")
    my_ngo_id = int(st.session_state["user"]["ngo_id"])
    my_row = ngos_df[ngos_df["id"]==my_ngo_id].iloc[0] if not ngos_df.empty and my_ngo_id in ngos_df["id"].tolist() else None
    if my_row is None:
        st.error("NGO record not found. Contact admin.")
    else:
        st.subheader(f"{my_row['name']} ({my_row['city']})")
        contact_val = st.text_input("Contact", value=my_row["contact"], key="ngo_contact")
        accepts_val = st.text_input("Accepts", value=my_row["accepts"], key="ngo_accepts")
        if st.button("Update NGO info"):
            ok = update_ngo(my_ngo_id, my_row["name"], contact_val, accepts_val)
            if ok:
                st.success("Updated.")
                st.experimental_rerun()
            else:
                st.error("Update failed.")
        st.subheader("Donations assigned to you")
        my_d = don_df[don_df["matched_ngo_id"]==my_ngo_id]
        st.dataframe(my_d)
        if not my_d.empty:
            st.download_button("Export assigned donations (CSV)", my_d.to_csv(index=False), "my_assigned_donations.csv")
else:
    st.info("Login as admin or NGO for advanced management. Donors can pledge via the donation form.")

# -----------------------
# Password change flow
# -----------------------
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

st.markdown("<small style='color:#666'>DB stored in meddonation.db (local). For deployment, ensure db_init.py and HF_API_TOKEN are configured in Streamlit Secrets.</small>", unsafe_allow_html=True)
