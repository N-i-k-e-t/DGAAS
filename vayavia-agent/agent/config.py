import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DB_NAME = os.getenv("DB_NAME", "vayavia_agent")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8090"))

# Scraper Configuration
SCRAPER_DELAY_MIN = 8
SCRAPER_DELAY_MAX = 25
ITEMS_PER_KEYWORD = 10

# Segments
VALID_SEGMENTS = [
    "Luxury Couple", 
    "Digital Nomad", 
    "Spiritual Seeker", 
    "Family Weekend", 
    "Wine Enthusiast", 
    "Corporate Group", 
    "Backpacker", 
    "Irrelevant"
]
