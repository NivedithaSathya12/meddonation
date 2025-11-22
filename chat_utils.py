# chat_utils.py
"""
Compatibility shim - re-export functions from chat_utils_enhanced.
"""

try:
    from chat_utils_enhanced import save_upload_to_tempfile, transcribe_audio, generate_chat_response, speak_text, extract_donation_suggestion
except Exception as e:
    # Provide minimal fallbacks
    def save_upload_to_tempfile(u): return None
    def transcribe_audio(p, lang_hint="en"): return ""
    def generate_chat_response(q, lc="en"): return "Assistant not available."
    def speak_text(t, lc="en"): return None
    def extract_donation_suggestion(t): return {}
