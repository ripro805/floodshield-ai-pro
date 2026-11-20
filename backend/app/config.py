"""
Central configuration for the FloodShield AI backend.
All file paths are resolved relative to the project root, so the app
works the same whether run locally, in Docker, or on Railway/Render.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # reads .env in local dev; on Railway/Render, real env vars are used instead

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")
GEO_EXPORTS_DIR = os.path.join(DATA_DIR, "geo_exports")
SAR_DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data", "sen1floods11", "S1Hand")
SAR_LABEL_DIR = os.path.join(os.path.dirname(BASE_DIR), "data", "sen1floods11", "LabelHand")

# Composite risk score weights (Model 5) -- disease outbreak matters more
# than raw flood depth for this platform's core purpose (disease early warning)
OUTBREAK_WEIGHT = 0.6
FLOOD_WEIGHT = 0.4

# outbreak_risk class -> numeric score used in the composite formula
OUTBREAK_SCORE_MAP = {"Medium": 1, "High": 2, "Critical": 3}

# risk score thresholds -> final_risk_level label
RISK_LEVEL_THRESHOLDS = [
    (1.0, "Low"),
    (2.0, "Medium"),
    (2.5, "High"),
]  # anything >= 2.5 falls through to "Critical"

# ---------- Database + Auth ----------
# Set these in a .env file locally (see .env.example) or as real environment
# variables in production. Never commit a .env file with real credentials.
DATABASE_URL = os.getenv("DATABASE_URL", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ---------- One-time bootstrap ----------
# If set, any authenticated user can call /auth/promote-me with this token to
# flip their own role to admin.  The endpoint is idempotent: once any admin
# exists in the DB, the bootstrap is disabled (regardless of whether
# BOOTSTRAP_TOKEN is still set), so the env var can be left in place.
# Leave empty in production.  Generate via: openssl rand -hex 24
BOOTSTRAP_TOKEN = os.getenv("BOOTSTRAP_TOKEN", "").strip()
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_REFRESH_INTERVAL_SECONDS = int(os.getenv("WEATHER_REFRESH_INTERVAL_SECONDS", "21600"))

from app.district_names import EN_TO_BN
_ALL_64_DISTRICTS_STR = ",".join(EN_TO_BN.keys())

WEATHER_REFRESH_DISTRICTS = tuple(
    item.strip() for item in os.getenv("WEATHER_REFRESH_DISTRICTS", _ALL_64_DISTRICTS_STR).split(",")
    if item.strip()
)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "https://ripro821.app.n8n.cloud/webhook/floodshield-monitoring")
N8N_ENABLED = os.getenv("N8N_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
N8N_TIMEOUT = float(os.getenv("N8N_TIMEOUT", "15"))
N8N_HEALTH_CACHE_SECONDS = int(os.getenv("N8N_HEALTH_CACHE_SECONDS", "30"))
N8N_WEBHOOK_HEADER_NAME = os.getenv("N8N_WEBHOOK_HEADER_NAME", "X-N8N-Webhook-Secret").strip()
N8N_WEBHOOK_SECRET = os.getenv("N8N_WEBHOOK_SECRET", "").strip()
FLOODSHIELD_BACKEND_BASE_URL = os.getenv("FLOODSHIELD_BACKEND_BASE_URL", "").strip().rstrip("/")
AUTOMATION_MODE = os.getenv("AUTOMATION_MODE", "auto").strip().lower()

HF_INFERENCE_API_URL = os.getenv("HF_INFERENCE_API_URL", "")
HF_INFERENCE_TOKEN = os.getenv("HF_INFERENCE_TOKEN", "")

# Hugging Face model hub -- used to download Model 2B (disease breakdown)
# artifacts that are too large / too volatile to bundle locally.
HF_MODEL_REPO_ID = os.getenv("HF_MODEL_REPO_ID", "ripro805/floodshield-ai-models")
HF_TOKEN = os.getenv("HF_TOKEN", "")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and fill in your "
        "Neon (or other Postgres) connection string."
    )
if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set. Generate one (e.g. `openssl rand -hex 32`) "
        "and put it in your .env file."
    )

# Model 4B U-Net and Earth Engine configuration
HF_MODEL_REPO = os.getenv("HF_MODEL_REPO", os.getenv("HF_MODEL_REPO_ID", "ripro805/floodshield-ai-models"))
HF_MODEL_REVISION = os.getenv("HF_MODEL_REVISION", None)
GEE_SERVICE_ACCOUNT_JSON = os.getenv("GEE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")


