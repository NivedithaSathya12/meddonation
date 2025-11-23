# chat_utils_updated.py
"""
Lightweight chat utilities for the Medicine Donation Assistant.
- save_upload_to_tempfile(uploaded_file) -> path
- hf_transcribe_audio(audio_bytes, model="openai/whisper-tiny") -> dict/result or {'error':...}
- generate_chat_response_hf(query, model="microsoft/DialoGPT-medium") -> string or error dict
- speak_text_gtts(text, lang="en") -> bytes (mp3) or None
- hf_image_classify(image_bytes, model="google/vit-base-patch16-224") -> list/dict or {'error':...}
- extract_donation_suggestion(text) -> small parsed dict
Notes:
- Uses HF API token from environment variable HF_API_TOKEN or passed header if provided.
- Safe: does not require heavy local ML libraries.
"""

import os
import tempfile
import json
from typing import Optional, Any, Dict
import requests

# Read HF token from environment variable by default.
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

if not HF_API_TOKEN:
    # If running inside Streamlit, user can set st.secrets; but modules don't import streamlit here.
    # The app that imports this module can set os.environ["HF_API_TOKEN"] before calling functions.
    HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}

def save_upload_to_tempfile(uploaded_file) -> Optional[str]:
    """
    Save a Streamlit uploaded file object to a temporary file and return its path.
    Returns None on failure or if uploaded_file is None.
    """
    if uploaded_file is None:
        return None
    try:
        suffix = ""
        try:
            name = getattr(uploaded_file, "name", None)
            if name and "." in name:
                suffix = "." + name.split(".")[-1]
        except Exception:
            suffix = ""
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            # uploaded_file could be an UploadedFile which supports getbuffer()
            tf.write(uploaded_file.getbuffer())
        except Exception:
            # fallback to read
            tf.write(uploaded_file.read())
        tf.close()
        return tf.name
    except Exception as e:
        print("save_upload_to_tempfile error:", e)
        return None

# ---------- Hugging Face helpers (simple wrappers) ----------
def _hf_post_json(model_name: str, payload: dict, timeout: int = 60) -> Any:
    """Helper to post JSON payload to HF inference endpoint."""
    if not HF_API_TOKEN:
        return {"error": "HF_API_TOKEN not set in environment."}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def _hf_post_audio_bytes(model_name: str, audio_bytes: bytes, timeout: int = 120) -> Any:
    """Post raw audio bytes to HF model that accepts audio (STT)."""
    if not HF_API_TOKEN:
        return {"error": "HF_API_TOKEN not set in environment."}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    try:
        r = requests.post(url, headers=HEADERS, data=audio_bytes, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def _hf_post_image_bytes(model_name: str, image_bytes: bytes, timeout: int = 60) -> Any:
    """Post image bytes to HF image models (multipart)."""
    if not HF_API_TOKEN:
        return {"error": "HF_API_TOKEN not set in environment."}
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    try:
        files = {"file": image_bytes}
        r = requests.post(url, headers=HEADERS, files=files, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# ---------- Public functions ----------
def hf_transcribe_audio(audio_bytes: bytes, model_name: str = "openai/whisper-tiny", timeout: int = 120) -> dict:
    """
    Send audio bytes to a Whisper-like model on HF Inference API.
    Returns dict with transcription keys or {'error':...}.
    Example return: {"text": "transcribed text"}
    """
    if not audio_bytes:
        return {"error": "No audio bytes provided."}
    return _hf_post_audio_bytes(model_name, audio_bytes, timeout=timeout)

def generate_chat_response_hf(prompt: str, model_name: str = "microsoft/DialoGPT-medium", params: dict = None, timeout: int = 60) -> Dict:
    """
    Generate a chat response using HF text-generation model.
    Returns parsed JSON or {'error':...}
    Note: DialoGPT returns different shapes; caller should handle them.
    """
    if not prompt:
        return {"error": "Empty prompt."}
    payload = {"inputs": prompt}
    if params:
        payload["parameters"] = params
    return _hf_post_json(model_name, payload, timeout=timeout)

def hf_image_classify(image_bytes: bytes, model_name: str = "google/vit-base-patch16-224", timeout: int = 60) -> Any:
    """
    Classify an image using HF image-classification endpoints.
    Returns list/dict (model-dependent) or {'error':...}
    """
    if not image_bytes:
        return {"error": "No image bytes provided."}
    return _hf_post_image_bytes(model_name, image_bytes, timeout=timeout)

def speak_text_gtts(text: str, lang: str = "en") -> Optional[bytes]:
    """
    Use gTTS to create mp3 bytes for client-side playback.
    Returns bytes (mp3) or None if gTTS is unavailable.
    """
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
            b = f.read()
        try:
            os.remove(tf.name)
        except:
            pass
        return b
    except Exception as e:
        print("speak_text_gtts error:", e)
        return None

# Lightweight fallback assistant (local rule-based) to use if HF unavailable
def generate_chat_response_local(prompt: str) -> str:
    if not prompt:
        return "Please type a question about donating medicines or upload a photo or audio."
    q = prompt.strip().lower()
    if "donate" in q or "how to donate" in q:
        return ("To donate medicines: use the 'Donate a Medicine' form on the main page. "
                "Provide medicine name, manufacture/purchase date, printed expiry if any, and choose a matched NGO.")
    if "expiry" in q or "expire" in q:
        return ("Check printed expiry. If not present, the app uses shelf-life rules. If expiry has passed, please do NOT donate.")
    if "ngo" in q:
        return ("NGOs can register using the sidebar. If you're an NGO, register and update your accepted items & contact info.")
    return "I understood: " + prompt + " — (assistant is running in local fallback mode)."

def extract_donation_suggestion(text: str) -> dict:
    """
    Very small parser: try to extract medicine token and date-like strings.
    Returns dict e.g. {'medicine': 'paracetamol', 'note': '...'}
    """
    if not text:
        return {}
    parts = text.split()
    suggestion = {"medicine": parts[0], "note": " ".join(parts[1:]) if len(parts)>1 else ""}
    # try to find a yyyy or dd-mm pattern (very naive)
    for tok in parts:
        if "-" in tok and any(ch.isdigit() for ch in tok):
            suggestion["possible_date"] = tok
            break
        if len(tok) == 4 and tok.isdigit():
            suggestion["possible_year"] = tok
            break
    return suggestion

# If module run directly, print minimal info
if __name__ == "__main__":
    print("chat_utils_updated loaded. HF_API_TOKEN present?" , bool(HF_API_TOKEN))
