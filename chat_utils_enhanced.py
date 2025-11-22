# chat_utils_enhanced.py
"""
Lightweight chat utilities for the meddonation app.
- save_upload_to_tempfile(file): saves an uploaded streamlit file to a temp path and returns path
- transcribe_audio(path, lang_hint): simple fallback transcription (no heavy models). Returns string.
- generate_chat_response(query, lang_code): small rule-based assistant (replace with your ML model later)
- speak_text(text, lang_code): returns audio bytes using gTTS if available, else None
"""

import tempfile
import os
from typing import Optional

def save_upload_to_tempfile(uploaded_file) -> Optional[str]:
    """
    Save a Streamlit uploaded file to a temporary file and return its path.
    uploaded_file should be the object returned by st.file_uploader.
    """
    if uploaded_file is None:
        return None
    try:
        suffix = ""
        name = getattr(uploaded_file, "name", None)
        if name and "." in name:
            suffix = "." + name.split(".")[-1]
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        # uploaded_file may be BytesIO; write buffer
        try:
            tf.write(uploaded_file.getbuffer())
        except Exception:
            # fallback read()
            tf.write(uploaded_file.read())
        tf.close()
        return tf.name
    except Exception as e:
        print("save_upload_to_tempfile error:", e)
        return None

def transcribe_audio(audio_path: str, lang_hint: str = "en") -> str:
    """
    Lightweight transcription fallback.
    - If you have whisper or speechrecognition installed, you can extend this function.
    - Currently returns a placeholder telling the user to type if no transcription available.
    """
    # Simple heuristic: if file exists, return a placeholder
    if not audio_path or not os.path.exists(audio_path):
        return ""
    # If you have whisper installed, uncomment / implement here.
    # For safety and to avoid heavy dependencies, we return a safe message.
    return "Transcription not available in this build — please type your query or upload a short audio in supported env."

def generate_chat_response(query: str, lang_code: str = "en") -> str:
    """
    Simple rule-based assistant response. Replace with real model or API calls later.
    """
    q = (query or "").strip().lower()
    if not q:
        return "Please enter a question or describe the medicine/donation you need help with."
    # Simple patterns
    if "donate" in q or "donation" in q:
        return ("To donate, please go to the 'Donate a Medicine' form. "
                "Provide medicine name, manufacture/purchase date, and (optional) printed expiry. "
                "Then choose a matched NGO and confirm. If you need help, type 'help donate'.")
    if "expiry" in q or "expire" in q:
        return ("Check the printed expiry date first. If not available, we estimate using shelf-life rules. "
                "If expiry is passed, do NOT donate. Ask your question with the medicine name and purchase date.")
    if "ngo" in q or "where" in q:
        return ("We match donations to local NGOs based on city and accepted items. "
                "You can register an NGO from the sidebar if you represent one.")
    # default
    return "I understand: " + query + "\n\n(Assistant is in demo mode — for full answers integrate a language model.)"

def extract_donation_suggestion(text: str) -> dict:
    """
    Example helper to parse a short user text to structured donation suggestion.
    Very basic: returns medicine name found (first token-like) and empty fields.
    """
    if not text:
        return {}
    parts = text.split()
    return {"medicine": parts[0], "note": " ".join(parts[1:])}

def speak_text(text: str, lang_code: str = "en") -> Optional[bytes]:
    """
    Return mp3 bytes using gTTS if available. Caller can feed these bytes to st.audio().
    """
    try:
        from gtts import gTTS
    except Exception as e:
        return None
    try:
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tf.close()
        tts = gTTS(text=text, lang=(lang_code.split("-")[0] if "-" in lang_code else lang_code))
        tts.save(tf.name)
        with open(tf.name, "rb") as f:
            b = f.read()
        try:
            os.remove(tf.name)
        except:
            pass
        return b
    except Exception as e:
        print("speak_text error:", e)
        return None

