"""
Chat utilities with speech-to-text (Whisper) and intent classification (DistilBERT).
Supports Hugging Face Inference API with fallback to local models.
All exceptions are logged to app.log.
"""

import os
import logging
import requests
import json
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

# Environment variables for HF API
HF_API_TOKEN = os.getenv('HF_API_TOKEN', '')
USE_HF_API = os.getenv('USE_HF_API', '0').lower() in ('1', 'true', 'yes')


def transcribe_audio(audio_file_path: str, prefer_hf: bool = True) -> Optional[str]:
    """
    Transcribe audio file to text using Whisper.
    Prefers Hugging Face Inference API, falls back to local model if needed.
    
    Args:
        audio_file_path: Path to audio file (wav, mp3, etc.)
        prefer_hf: If True, try HF API first
    
    Returns:
        Transcription string or None on error
    """
    if prefer_hf and USE_HF_API and HF_API_TOKEN:
        try:
            # Try Hugging Face Inference API
            with open(audio_file_path, 'rb') as f:
                files = {'file': f}
                headers = {'Authorization': f'Bearer {HF_API_TOKEN}'}
                response = requests.post(
                    'https://api-inference.huggingface.co/models/openai/whisper-tiny',
                    headers=headers,
                    files=files,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    transcription = result.get('text', '')
                    if transcription:
                        logging.info("Audio transcribed successfully via HF API")
                        return transcription
                else:
                    logging.warning(f"HF API returned status {response.status_code}: {response.text}")
        except requests.exceptions.RequestException as e:
            logging.warning(f"HF API request failed: {e}")
        except Exception as e:
            logging.error(f"Error using HF API for transcription: {e}")
    
    # Fallback to local model (if available)
    try:
        # Lazy import to avoid heavy dependencies if not needed
        # transformers is optional - install with: pip install transformers torch soundfile
        from transformers import pipeline  # type: ignore
        
        # Try to load Whisper pipeline
        try:
            asr_pipeline = pipeline(
                "automatic-speech-recognition",
                model="openai/whisper-tiny",
                device=-1  # CPU
            )
            result = asr_pipeline(audio_file_path)
            transcription = result.get('text', '')
            if transcription:
                logging.info("Audio transcribed successfully via local Whisper")
                return transcription
        except Exception as e:
            logging.warning(f"Local Whisper model failed: {e}")
    except ImportError:
        logging.warning("transformers library not installed. Install with: pip install transformers torch soundfile")
    except Exception as e:
        logging.error(f"Error in local transcription: {e}")
    
    logging.error("All transcription methods failed")
    return None


def classify_intent(text: str, prefer_hf: bool = True, 
                   model: str = "distilbert-base-uncased-finetuned-sst-2-english") -> Dict[str, any]:
    """
    Classify intent/sentiment of text using DistilBERT.
    Prefers Hugging Face Inference API, falls back to local model.
    
    Args:
        text: Input text to classify
        prefer_hf: If True, try HF API first
        model: Model name for classification
    
    Returns:
        Dict with 'label' and 'score' keys, or empty dict on error
    """
    if not text or not text.strip():
        return {'label': 'NEUTRAL', 'score': 0.0}
    
    if prefer_hf and USE_HF_API and HF_API_TOKEN:
        try:
            # Try Hugging Face Inference API
            headers = {
                'Authorization': f'Bearer {HF_API_TOKEN}',
                'Content-Type': 'application/json'
            }
            payload = {'inputs': text.strip()}
            response = requests.post(
                f'https://api-inference.huggingface.co/models/{model}',
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                # Handle different response formats
                if isinstance(result, list) and len(result) > 0:
                    if isinstance(result[0], list):
                        result = result[0]
                    top_result = result[0] if isinstance(result[0], dict) else result
                    label = top_result.get('label', 'NEUTRAL')
                    score = top_result.get('score', 0.0)
                    logging.info(f"Intent classified via HF API: {label} ({score:.2f})")
                    return {'label': label, 'score': score}
        except requests.exceptions.RequestException as e:
            logging.warning(f"HF API request failed: {e}")
        except Exception as e:
            logging.error(f"Error using HF API for classification: {e}")
    
    # Fallback to local model (if available)
    try:
        # transformers is optional - install with: pip install transformers torch soundfile
        from transformers import pipeline  # type: ignore
        
        try:
            classifier = pipeline(
                "sentiment-analysis",
                model=model,
                device=-1  # CPU
            )
            result = classifier(text.strip())
            if isinstance(result, list):
                result = result[0]
            label = result.get('label', 'NEUTRAL')
            score = result.get('score', 0.0)
            logging.info(f"Intent classified via local model: {label} ({score:.2f})")
            return {'label': label, 'score': score}
        except Exception as e:
            logging.warning(f"Local classification model failed: {e}")
    except ImportError:
        logging.warning("transformers library not installed for local classification")
    except Exception as e:
        logging.error(f"Error in local classification: {e}")
    
    # Default fallback: simple rule-based classification
    text_lower = text.lower()
    if any(word in text_lower for word in ['donate', 'medicine', 'help', 'ngo']):
        return {'label': 'POSITIVE', 'score': 0.7}
    elif any(word in text_lower for word in ['no', 'not', 'cannot', "can't"]):
        return {'label': 'NEGATIVE', 'score': 0.6}
    else:
        return {'label': 'NEUTRAL', 'score': 0.5}


def generate_chat_response(user_text: str, prefer_hf: bool = True) -> str:
    """
    Generate a chat response based on user input.
    Uses rule-based responses for safety, with optional HF API enhancement.
    
    Args:
        user_text: User's input text
        prefer_hf: If True, try HF API for richer responses
    
    Returns:
        Response string
    """
    if not user_text or not user_text.strip():
        return "I'm here to help with medicine donations. What would you like to know?"
    
    user_text_lower = user_text.lower().strip()
    
    # Rule-based responses (safety-first)
    if any(word in user_text_lower for word in ['hello', 'hi', 'hey', 'greetings']):
        return "Hello! I'm the Medicine Donation Assistant. I can help you check if your medicine is eligible for donation and find matching NGOs. How can I assist you today?"
    
    elif any(word in user_text_lower for word in ['donate', 'donation', 'give']):
        return "Great! To donate medicine, please fill out the donation form above. I'll help you check if your medicine is eligible based on expiry dates or shelf life. Make sure your medicine has at least 180 days until expiry."
    
    elif any(word in user_text_lower for word in ['eligibility', 'eligible', 'expiry', 'expire']):
        return "Medicine eligibility depends on expiry dates. If you have a printed expiry date, it must be at least 180 days away. If not, we calculate it from the manufacture date and shelf life. Use the form above to check your specific medicine."
    
    elif any(word in user_text_lower for word in ['ngo', 'organization', 'where', 'who accepts']):
        return "NGOs are matched based on your city location. After checking eligibility, you'll see a list of available NGOs in your area. You can also view all NGOs in the Admin Panel."
    
    elif any(word in user_text_lower for word in ['shelf life', 'shelf', 'how long']):
        return "Shelf life varies by medicine. For example, paracetamol tablets typically last 36 months, while liquid medicines like cough syrup may last 12 months. The system uses this information to estimate expiry if no printed date is available."
    
    elif any(word in user_text_lower for word in ['paracetamol', 'amoxicillin', 'cough syrup']):
        medicine = 'paracetamol' if 'paracetamol' in user_text_lower else \
                  'amoxicillin' if 'amoxicillin' in user_text_lower else 'cough syrup'
        return f"Great! {medicine.title()} can be donated if it meets the eligibility criteria. Please fill out the donation form with the medicine name '{medicine}' and your manufacture date to check eligibility."
    
    elif any(word in user_text_lower for word in ['help', 'how', 'what']):
        return "I can help you with: 1) Checking medicine donation eligibility, 2) Finding NGOs in your area, 3) Understanding shelf life requirements. Use the donation form above to get started, or ask me a specific question!"
    
    elif any(word in user_text_lower for word in ['thank', 'thanks']):
        return "You're welcome! I'm here to help make medicine donations easier. If you have more questions, feel free to ask!"
    
    # Try HF API for richer responses (if enabled)
    if prefer_hf and USE_HF_API and HF_API_TOKEN:
        try:
            headers = {
                'Authorization': f'Bearer {HF_API_TOKEN}',
                'Content-Type': 'application/json'
            }
            # Use a conversational model
            payload = {
                'inputs': {
                    'past_user_inputs': [],
                    'generated_responses': [],
                    'text': user_text.strip()
                }
            }
            response = requests.post(
                'https://api-inference.huggingface.co/models/microsoft/DialoGPT-small',
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'generated_text' in result:
                    hf_response = result['generated_text']
                    # Combine with rule-based for safety
                    return f"{hf_response} (Note: For medicine donation eligibility, please use the form above for accurate results.)"
        except Exception as e:
            logging.warning(f"HF API chat generation failed, using rule-based: {e}")
    
    # Default fallback response
    return "I understand you're asking about medicine donations. For specific eligibility checks, please use the donation form above. For general questions, I can help explain the donation process, NGO matching, or shelf life requirements. What would you like to know?"

