# app.py
"""
Full Streamlit app for Medicine Donation Assistant
Features:
- Role-based login (admin / ngo / donor)
- Admin Panel: manage NGOs, shelf life, donations, create NGO users
- NGO Portal: update NGO info & view assigned donations
- Donor/public donation form + eligibility check
- Multilingual voice/text assistant integration via chat_utils_enhanced.py
- Password change, logout, simple styling
Run: python -m streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import os
from pathlib import Path

# Local helpers (make sure these files exist in project)
import admin_utils
from utils import is_donation_allowed, get_shelf_info
from chat_utils_enhanced import (
    save_upload_to_tempfile, transcribe_audio, generate_chat_response,
    extract_donation_suggestion, speak_text, LANG_MAP
)

# ---------------- Page config & basic CSS ----------------
st.set_page_config(page_title="Medicine Donation Assistant", page_icon="💊", layout="wide")

# Simple style to make the UI more colorful and dynamic
st.markdown(
    """
    <style>
    .header {font-size:30px; font-weight:700; color: #0B4F6C;}
    .sub {color: #0B7285;}
    .card {background: linear-gradient(90deg, #f8fbff 0%, #ffffff 100%); padding:12px; border-radius:12px; box-shadow: 0 4px 14px rgba(11,79,108,0.06);}
    .small {font-size:13px; color:#444}
    .accent {color:#0B7285; font-weight:600}
    </style>
    """,
    unsafe_allow_html=True
)

# Page header
st.markdown("<div class='header'>💊 Medicine Donation Assistant</div>", unsafe_allow_html=True)
st.markdown("<div class='small'>Check expiry, match NGOs, record donations — voice & text friendly.</div>", unsafe_allow_html=True)
st.write("---")

# ---------------- Session defaults ----------------
if "user" not in st.session_state:
    st.session_state["user"] = None
if "show_ngo_register" not in st.session_state:
    st.session_state["show_ngo_register"] = False

# ---------------- Helper: DB connect quick check ----------------
DB_PATH = Path("meddonation.db")
if not DB_PATH.exists():
    st.error("Database meddonation.db not found in project folder. Please place the DB and refresh.")
    st.stop()

# ---------------- Authentication functions ----------------
def do_login():
    uname = st.session_state.get("login_username", "").strip()
    pwd = st.session_state.get("login_password", "")
    if not uname or not pwd:
        st.warning("Enter username & password.")
        return
    user = admin_utils.verify_user(uname, pwd)
    if not user:
        st.error("Invalid username or password.")
        return
    st.session_state["user"] = user
    st.success(f"Welcome {user['username']} ({user['role']})")
    st.experimental_rerun()

def do_logout():
    st.session_state["user"] = None
    st.experimental_rerun()

# ---------------- Sidebar: Login / Register / Profile ----------------
with st.sidebar:
    st.markdown("### 🔐 Account")
    if st.session_state["user"] is None:
        st.text_input("Username", key="login_username")
        st.text_input("Password", key="login_password", type="password")
        st.button("Login", on_click=do_login)
        st.markdown("---")
        st.markdown("New NGO? Request access:")
        if st.button("Register as NGO"):
            st.session_state["show_ngo_register"] = True
    else:
        u = st.session_state["user"]
        st.markdown(f"**Logged in:** `{u['username']}`")
        st.markdown(f"**Role:** {u['role']}")
        if st.button("Logout"):
            do_logout()
        st.markdown("---")
        st.markdown("Account actions")
        if st.button("Change Password"):
            st.session_state["show_change_pw"] = True

# ---------------- NGO Registration Form (public) ----------------
if st.session_state.get("show_ngo_register"):
    st.header("NGO Registration Request 📝")
    with st.form("ngo_reg"):
        reg_name = st.text_input("NGO Name")
        reg_city = st.text_input("City")
        reg_contact = st.text_input("Contact (phone/email)")
        reg_accepts = st.text_input("Accepts (comma separated)")
        reg_sub = st.form_submit_button("Submit registration")
    if reg_sub:
        if not reg_name.strip():
            st.error("Please enter NGO name.")
        else:
            nid = admin_utils.insert_ngo(reg_name.strip(), reg_city.strip(), reg_contact.strip(), reg_accepts.strip())
            if nid:
                st.success("Registration recorded. Admin will create an account for you.")
                st.session_state["show_ngo_register"] = False
            else:
                st.error("Failed to register NGO. Try again or contact admin.")

# ---------------- Top Metrics (public) ----------------
col1, col2, col3 = st.columns([1,1,2])
with col1:
    total_ngos = len(admin_utils.get_all_ngos())
    st.metric("Registered NGOs", total_ngos, delta=None)
with col2:
    total_shelf = len(admin_utils.get_all_shelf_life())
    st.metric("Shelf items", total_shelf)
with col3:
    donations_df = admin_utils.get_recent_donations(limit=1000, filters={})
    st.metric("Donations recorded", len(donations_df))

st.write("---")

# ---------------- Public / Donor Donation Form ----------------
st.markdown("<div class='card'><strong>Donate a Medicine</strong> — fill the form to check eligibility and match NGOs.</div>", unsafe_allow_html=True)
with st.form("donate_form"):
    dcol1, dcol2, dcol3 = st.columns(3)
    with dcol1:
        donor_name = st.text_input("Your name", placeholder="Full name")
        city = st.text_input("Your city", placeholder="City for NGO matching")
    with dcol2:
        medicine = st.text_input("Medicine name (e.g., Paracetamol 500mg)")
        mfg_date = st.date_input("Manufacture / Purchase date", value=datetime.today())
    with dcol3:
        expiry_text = st.text_input("Printed expiry (optional, YYYY-MM-DD)")
        preferred_ngo = st.selectbox("Prefer NGO (optional)", options=["(Any)"] + admin_utils.get_all_ngos()["name"].tolist())
    submitted = st.form_submit_button("Check & Find NGO")

if submitted:
    if not donor_name.strip() or not medicine.strip():
        st.error("Please provide your name and medicine name.")
    else:
        expiry_iso = expiry_text.strip() if expiry_text.strip() else None
        res = is_donation_allowed(medicine.strip(), mfg_date.isoformat(), expiry_iso)
        if res["allowed"]:
            st.success(res["reason"])
            # Show matched NGOs
            ngos = admin_utils.get_all_ngos()
            if city.strip():
                nearby = ngos[ngos["city"].str.lower() == city.strip().lower()]
            else:
                nearby = ngos
            if preferred_ngo != "(Any)":
                nearby = ngos[ngos["name"] == preferred_ngo]
            if nearby.empty:
                st.info("No NGOs found for given city / preference. Admin will be notified.")
            else:
                st.info(f"Found {len(nearby)} NGOs. Choose one to confirm donation.")
                st.dataframe(nearby[["id","name","city","contact","accepts"]])
                chosen = st.selectbox("Select NGO ID to donate to", nearby["id"].astype(str).tolist())
                if st.button("Confirm Donation"):
                    ok = admin_utils.insert_donation(donor_name.strip(), medicine.strip(), mfg_date.isoformat(), expiry_iso, "pledged", int(chosen))
                    if ok:
                        st.success("Donation recorded; NGO will be notified. Thank you!")
                    else:
                        st.error("Failed to record donation. Try again.")
        else:
            st.warning(res["reason"])
            if res.get("days_left") is not None:
                st.write("Days left (approx):", res["days_left"])

st.write("---")

# ---------------- Assistant (Voice & Text) ----------------
st.markdown("<div class='card'><strong>Assistant — Voice & Text</strong></div>", unsafe_allow_html=True)
assistant_col1, assistant_col2 = st.columns([1,2])
with assistant_col1:
    selected_lang = st.selectbox("Language", list(LANG_MAP.keys()))
    lang_code = LANG_MAP[selected_lang][0]
    audio_file = st.file_uploader("Upload voice (wav/mp3/m4a)", type=["wav","mp3","m4a"])
    if audio_file:
        st.info("Transcribing — please wait...")
        audio_path = save_upload_to_tempfile(audio_file)
        transcript = transcribe_audio(audio_path, lang_hint=lang_code)
        st.text_area("Transcription (edit if needed)", value=transcript, height=120, key="transcript_text")
        if st.button("Ask from voice"):
            query = st.session_state.get("transcript_text", transcript)
            reply = generate_chat_response(query, lang_code)
            st.markdown("**Assistant:**")
            st.write(reply)
            try:
                speak_text(reply, lang_code)
            except:
                pass

with assistant_col2:
    text_q = st.text_input("Ask the assistant (text)")
    if st.button("Ask (text)"):
        if text_q.strip():
            reply = generate_chat_response(text_q, lang_code)
            st.markdown("**Assistant:**")
            st.write(reply)
            try:
                speak_text(reply, lang_code)
            except:
                pass

st.write("---")

# ---------------- Role-specific UI ----------------

# ADMIN PANEL
if st.session_state["user"] and st.session_state["user"]["role"] == "admin":
    st.markdown("<h3 style='color:#0B4F6C'>⚙️ Admin Panel</h3>", unsafe_allow_html=True)

    # Dashboard metrics
    ngos_df = admin_utils.get_all_ngos()
    shelf_df = admin_utils.get_all_shelf_life()
    donations_df = admin_utils.get_recent_donations(limit=1000, filters={})

    a1, a2, a3 = st.columns(3)
    a1.metric("NGOs", len(ngos_df))
    a2.metric("Shelf entries", len(shelf_df))
    a3.metric("Donations", len(donations_df))

    st.subheader("Manage NGOs")
    with st.expander("NGO List & Edit"):
        st.dataframe(ngos_df)
        # Edit an NGO
        edit_id = st.number_input("NGO ID to edit", min_value=1, value=1, step=1)
        if st.button("Load NGO"):
            if edit_id not in ngos_df["id"].tolist():
                st.error("NGO id not found.")
            else:
                row = ngos_df[ngos_df["id"] == edit_id].iloc[0]
                new_name = st.text_input("Name", value=row["name"], key="name_edit")
                new_city = st.text_input("City", value=row["city"], key="city_edit")
                new_contact = st.text_input("Contact", value=row["contact"], key="contact_edit")
                new_accepts = st.text_input("Accepts", value=row["accepts"], key="accepts_edit")
                if st.button("Update NGO info"):
                    ok = admin_utils.update_ngo(edit_id, new_name, new_city, new_contact, new_accepts)
                    if ok:
                        st.success("NGO updated.")
                        st.experimental_rerun()
                    else:
                        st.error("Failed to update NGO.")

    st.subheader("Create NGO User Account")
    with st.form("create_ngo_user"):
        new_un = st.text_input("New NGO username")
        new_pw = st.text_input("New NGO password", type="password")
        select_ngo = st.selectbox("Assign NGO (ID)", options=ngos_df["id"].tolist())
        create_submit = st.form_submit_button("Create user")
    if create_submit:
        if not new_un or not new_pw:
            st.error("Provide username & password.")
        else:
            ok = admin_utils.create_user(new_un.strip(), new_pw.strip(), role="ngo", ngo_id=int(select_ngo))
            if ok:
                st.success(f"User {new_un} created for NGO id {select_ngo}.")
            else:
                st.error("Failed to create user (maybe username exists).")

    st.subheader("Shelf life management")
    with st.expander("Add / Edit shelf life"):
        sl_med = st.text_input("Medicine name")
        sl_months = st.number_input("Shelf life (months)", min_value=1, value=12)
        sl_notes = st.text_input("Notes / form")
        if st.button("Add / Update shelf record"):
            ok = admin_utils.insert_shelf(sl_med.strip().lower(), int(sl_months), sl_notes.strip())
            if ok:
                st.success("Shelf record added/updated.")
                st.experimental_rerun()
            else:
                st.error("Failed to add shelf record.")

    st.subheader("Donations")
    with st.expander("View & manage donations"):
        df = donations_df.copy()
        st.dataframe(df)
        del_id = st.number_input("Donation ID to delete", min_value=0, value=0, step=1)
        if st.button("Delete donation"):
            if del_id <= 0:
                st.warning("Enter a valid donation ID.")
            else:
                ok = admin_utils.delete_donation(int(del_id))
                if ok:
                    st.success("Deleted.")
                    st.experimental_rerun()
                else:
                    st.error("Delete failed.")

    st.info("Admin actions are logged. Change admin password from sidebar if needed.")

# NGO PORTAL (only for NGO users)
elif st.session_state["user"] and st.session_state["user"]["role"] == "ngo":
    st.markdown("<h3 style='color:#0B4F6C'>🤝 NGO Portal</h3>", unsafe_allow_html=True)
    ngo_id = st.session_state["user"].get("ngo_id")
    ngos = admin_utils.get_all_ngos()
    if not ngo_id or int(ngo_id) not in ngos["id"].tolist():
        st.error("NGO record missing or not linked to your account. Contact admin.")
    else:
        row = ngos[ngos["id"] == int(ngo_id)].iloc[0]
        st.subheader(f"{row['name']} — {row['city']}")
        with st.form("ngo_update_form"):
            c_contact = st.text_input("Contact", value=row["contact"])
            c_accepts = st.text_input("Accepts", value=row["accepts"])
            sub = st.form_submit_button("Update NGO info")
        if sub:
            ok = admin_utils.update_ngo(int(ngo_id), row["name"], c_contact, c_accepts)
            if ok:
                st.success("NGO info updated.")
            else:
                st.error("Update failed.")
        st.subheader("Donations assigned to you")
        don_df = admin_utils.get_recent_donations(limit=1000, filters={})
        my = don_df[don_df["matched_ngo_id"] == int(ngo_id)]
        st.dataframe(my)
        if not my.empty:
            st.download_button("Export assigned donations (CSV)", my.to_csv(index=False), "my_donations.csv")

# Else: not logged in or other roles (donor can be public)
else:
    st.info("Log in as admin or NGO to manage records. Donors can use the donation form above to pledge medicines.")

# ---------------- Password Change flow (simple) ----------------
if st.session_state.get("show_change_pw"):
    st.header("Change Password")
    oldp = st.text_input("Current password", type="password", key="old_pw")
    newp = st.text_input("New password", type="password", key="new_pw")
    if st.button("Change now"):
        if not st.session_state["user"]:
            st.error("Login first.")
        else:
            verified = admin_utils.verify_user(st.session_state["user"]["username"], oldp)
            if not verified:
                st.error("Current password incorrect.")
            else:
                # update directly in DB
                import hashlib, sqlite3
                def _hash(pw, salt="medsalt"): return hashlib.sha256((salt+pw).encode()).hexdigest()
                conn = sqlite3.connect("meddonation.db")
                conn.cursor().execute("UPDATE users SET password_hash=? WHERE username=?", (_hash(newp), st.session_state["user"]["username"]))
                conn.commit()
                conn.close()
                st.success("Password updated. Please log in again.")
                st.session_state["user"] = None
                st.session_state["show_change_pw"] = False
                st.experimental_rerun()

st.write("---")
st.markdown("<div class='small'>Built for accessibility and quick field use — supports voice input and multiple Indian languages. For deployment, use Streamlit Cloud or Render.</div>", unsafe_allow_html=True)
