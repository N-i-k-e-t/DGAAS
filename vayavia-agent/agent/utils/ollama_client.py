import requests
import json
from .. import config
from .logging_utils import setup_logger

logger = setup_logger("ollama_client")

def classify_signal(text):
    url = f"{config.OLLAMA_BASE_URL}/api/generate"
    
    prompt = f"""
    Analyze this text from social media and classify its intent for travel to Nashik.
    Text: {text}
    
    Respond STRICTLY in JSON format with these fields:
    - segment: Choose one from {config.VALID_SEGMENTS}
    - score: Integer from 0 to 100 representing intent to book or travel soon.
    - urgency: 'low', 'medium', or 'high' based on the timeline mentioned.
    
    JSON:
    """
    
    payload = {
        "model": config.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Parse the JSON string from the model's response
        classification = json.loads(result.get("response", "{}"))
        
        # Basic validation
        if "segment" not in classification or "score" not in classification:
            logger.warning("Invalid JSON structure from Ollama")
            return None
            
        return classification
        
    except Exception as e:
        logger.error(f"Ollama classification error: {e}")
        return None
