# chat_utils_enhanced.py
"""
Multilingual voice/text assistant utilities for the Medicine Donation System.
Includes:
- Whisper-tiny ASR (HF or local fallback)
- DistilBERT intent classification
- Rule-based + HF generation fallback
- gTTS + pyttsx3 TTS
- Donation suggestion extraction
"""

import os
import tempfile
import requests
import logging
# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
logger = logging.getLogger("assistant")
if not logger.handlers:
    fh = logging.FileHandler("app.log")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(fh)

# -------------------------------------------------------------------
# LANGUAGE MAP (Display Name → (Code, English Display))
# -------------------------------------------------------------------
LANG_MAP = {
    "English (en)": ("en", "English"),
    "हिन्दी / Hindi (hi)": ("hi", "Hindi"),
    "বাংলা / Bengali (bn)": ("bn", "Bengali"),
    "தமிழ் / Tamil (ta)": ("ta", "Tamil"),
    "తెలుగు / Telugu (te)": ("te", "Telugu"),
    "मराठी / Marathi (mr)": ("mr", "Marathi"),
    "ગુજરાતી / Gujarati (gu)": ("gu", "Gujarati"),
    "ಕನ್ನಡ / Kannada (kn)": ("kn", "Kannada"),
    "മലയാളം / Malayalam (ml)": ("ml", "Malayalam"),
    "ਪੰਜਾਬੀ / Punjabi (pa)": ("pa", "Punjabi"),
    "ଓଡ଼ିଆ / Odia (or)": ("or", "Odia"),
    "অসমীয়া / Assamese (as)": ("as", "Assamese"),
    "اردو / Urdu (ur)": ("ur", "Urdu"),
}

# -------------------------------------------------------------------
# SAVE UPLOADS SAFELY
# -------------------------------------------------------------------
def save_upload_to_tempfile(uploaded):
    """Save uploaded audio file to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as fp:
        fp.write(uploaded.read())
        return fp.name

# -------------------------------------------------------------------
# TRANSCRIPTION (Whisper-Tiny)
# -------------------------------------------------------------------

def _hf_whisper(audio_path, model="openai/whisper-tiny", lang_hint="en"):
    """HF Inference API transcription."""
    try:
        token = os.environ.get("HF_API_TOKEN", None)
        if not token:
            return None

        API_URL = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {token}"}

        with open(audio_path, "rb") as f:
            resp = requests.post(API_URL, headers=headers, data=f, timeout=60)

        if resp.status_code == 200:
            out = resp.json()
            if "text" in out:
                return out["text"]
        logger.error("HF Whisper failed: %s", resp.text)
        return None
    except Exception:
        logger.exception("HF Whisper Exception")
        return None


def _local_whisper(audio_path, model="openai/whisper-tiny"):
    """Local Whisper tiny transcription (slow, only works if transformers installed)."""
    try:
        from transformers import WhisperProcessor, WhisperForConditionalGeneration
        import torch
        import soundfile as sf

        speech, sr = sf.read(audio_path)
        processor = WhisperProcessor.from_pretrained(model)
        model = WhisperForConditionalGeneration.from_pretrained(model)

        inputs = processor(speech, sampling_rate=sr, return_tensors="pt")
        with torch.no_grad():
            ids = model.generate(inputs["input_features"])
        text = processor.batch_decode(ids, skip_special_tokens=True)[0]
        return text
    except Exception:
        logger.exception("Local Whisper failed")
        return None


def transcribe_audio(audio_path, lang_hint="en", prefer_hf=True):
    """Unified transcription."""
    if prefer_hf:
        text = _hf_whisper(audio_path, lang_hint=lang_hint)
        if text:
            return text
    return _local_whisper(audio_path) or "Sorry, I couldn't transcribe the audio."

# -------------------------------------------------------------------
# TRANSLATION (HF → English)
# -------------------------------------------------------------------

def translate_to_english(text, lang_code):
    """Translate many Indian languages → English using HF API."""
    if lang_code == "en":
        return text

    token = os.environ.get("HF_API_TOKEN", None)
    if not token:
        return text  # return original if no HF token

    try:
        model = f"Helsinki-NLP/opus-mt-{lang_code}-en"
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"inputs": text}

        resp = requests.post(url, headers=headers, json=payload, timeout=45)
        if resp.status_code == 200:
            out = resp.json()
            if isinstance(out, list) and len(out) > 0 and "translation_text" in out[0]:
                return out[0]["translation_text"]
        return text
    except:
        logger.exception("Translation failed")
        return text

# -------------------------------------------------------------------
# CLASSIFICATION (DistilBERT)
# -------------------------------------------------------------------

def _hf_distilbert(text):
    try:
        token = os.environ.get("HF_API_TOKEN", None)
        if not token:
            return None

        url = "https://api-inference.huggingface.co/models/distilbert-base-uncased-finetuned-sst-2-english"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(url, headers=headers, json={"inputs": text})
        if resp.status_code == 200:
            out = resp.json()
            return out[0][0]
        return None
    except:
        logger.exception("HF DistilBERT failed")
        return None


def _local_distilbert(text):
    try:
        from transformers import pipeline
        clf = pipeline("text-classification")
        return clf(text)[0]
    except:
        logger.exception("Local DistilBERT failed")
        return {"label": "neutral", "score": 0.0}


def classify_intent(text, lang_code="en"):
    """Translate → classify → return label"""
    english = translate_to_english(text, lang_code)
    res = None

    if os.environ.get("USE_HF_API", "1").lower() in ("1", "true"):
        res = _hf_distilbert(english)

    if not res:
        res = _local_distilbert(english)
    return res

# -------------------------------------------------------------------
# SAFE RULE-BASED RESPONSES
# -------------------------------------------------------------------

def _rule_based_reply(text, lang_code):
    t = text.lower()

    if "donate" in t or "donation" in t:
        return {
            "en": "You can donate by filling the form above. I can help check expiry!",
            "hi": "आप दान फ़ॉर्म भरकर दवा दान कर सकते हैं। मैं एक्सपायरी जांचने में मदद कर सकता/सकती हूँ!",
        }.get(lang_code, "Please use the donation form above.")

    if "expiry" in t:
        return {
            "en": "You can tell me the medicine name and date, and I will check if it can be donated.",
            "hi": "आप दवा का नाम और तारीख बताएँ, मैं बता दूँगा कि दान संभव है या नहीं।",
        }.get(lang_code, "Tell me medicine name and date to check expiry.")

    if "ngo" in t:
        return {
            "en": "NGOs appear in the list above. I can help match based on your city.",
            "hi": "ऊपर NGO सूची है। मैं आपके शहर के आधार पर मिलान में मदद कर सकता/सकती हूँ।",
        }.get(lang_code, "NGO list is above.")

    return {
        "en": "I am here to help with medicine donation. Tell me what you need.",
        "hi": "मैं दवा दान में आपकी मदद कर सकता/सकती हूँ। कृपया अपना प्रश्न पूछें।",
    }.get(lang_code, "I can help with medicine donation.")

# -------------------------------------------------------------------
# HF GENERATION (optional)
# -------------------------------------------------------------------

def _hf_generate(text):
    token = os.environ.get("HF_API_TOKEN", None)
    if not token:
        return None

    try:
        url = "https://api-inference.huggingface.co/models/facebook/blenderbot-400M-distill"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(url, headers=headers, json={"inputs": text}, timeout=60)
        if resp.status_code == 200:
            out = resp.json()
            if isinstance(out, dict) and "generated_text" in out:
                return out["generated_text"]
        return None
    except:
        logger.exception("HF generation failed")
        return None

# -------------------------------------------------------------------
# MAIN CHAT RESPONSE GENERATOR
# -------------------------------------------------------------------

def generate_chat_response(text, lang_code="en", prefer_hf=True):
    """Unified reply with translation + rule-based fallback."""
    try:
        eng_text = translate_to_english(text, lang_code)

        reply = None
        if prefer_hf:
            reply = _hf_generate(eng_text)

        if not reply:
            reply = _rule_based_reply(text, lang_code)

        # Translate back to user language
        if lang_code != "en":
            reply = _translate_back(reply, lang_code)
        return reply

    except Exception:
        logger.exception("Chat response error")
        return "Sorry, I couldn't understand."

# -------------------------------------------------------------------
# TRANSLATE BACK ENG → LANG
# -------------------------------------------------------------------

def _translate_back(text, lang_code):
    token = os.environ.get("HF_API_TOKEN", None)
    if not token or lang_code == "en":
        return text

    try:
        model = f"Helsinki-NLP/opus-mt-en-{lang_code}"
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"inputs": text}

        resp = requests.post(url, headers=headers, json=payload, timeout=45)
        if resp.status_code == 200:
            out = resp.json()
            if isinstance(out, list) and len(out) > 0 and "translation_text" in out[0]:
                return out[0]["translation_text"]
        return text
    except:
        logger.exception("Translate back failed")
        return text

# -------------------------------------------------------------------
# DONATION SUGGESTION EXTRACTION
# -------------------------------------------------------------------

def extract_donation_suggestion(text):
    """Find medicine name (simple keyword match)."""
    meds = ["paracetamol", "amoxicillin", "syrup", "tablet", "capsule"]
    t = text.lower()

    for m in meds:
        if m in t:
            return {"medicine": m}
    return {"medicine": None}

# -------------------------------------------------------------------
# TEXT TO SPEECH
# -------------------------------------------------------------------
def speak_text(text, lang_code="en"):
    """
    Speak text aloud. This does lazy imports so the module can be used
    on machines without TTS packages installed.
    """
    try:
        # Try offline pyttsx3 first
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 140)
            engine.say(text)
            engine.runAndWait()
            return True
        except Exception:
            pass  # fall back to gTTS

        # Fallback: gTTS + playsound (online)
        try:
            from gtts import gTTS
            from playsound import playsound
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                tts = gTTS(text=text, lang=lang_code if lang_code else "en")
                tts.save(fp.name)
                playsound(fp.name)
            return True
        except Exception:
            logger.exception("TTS fallback failed")
            return False

    except Exception:
        logger.exception("Unexpected speak_text error")
        return False


