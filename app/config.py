
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
MODELS_DIR = BASE_DIR / "models"
PRIORITY_DIR = MODELS_DIR / "priority_feedback"

USERS_FILE = DATA_DIR / "users.json"
API_KEYS_FILE = DATA_DIR / "api_keys.json"
FEEDBACK_FILE = DATA_DIR / "feedback.json"
MODEL_COMPARISON_FILE = DATA_DIR / "model_comparison.json"
RETRAINING_FILE = DATA_DIR / "retraining.json"
API_USAGE_FILE = DATA_DIR / "api_usage.json"
ADMIN_AUDIT_FILE = DATA_DIR / "admin_audit.json"
FEEDBACK_SECTORS_FILE = DATA_DIR / "feedback_sectors.json"
CACHE_FILE = DATA_DIR / "cache.json"
REPORTS_DIR = DATA_DIR / "reports"
SETTINGS_FILE = DATA_DIR / "settings.json"

# AI & aggregation params
MAX_FRAMES = int(os.environ.get("MAX_FRAMES", 50))
SKIP_FRAMES = int(os.environ.get("SKIP_FRAMES", 5))
FRAME_HIGH_PCT = float(os.environ.get("FRAME_HIGH_PCT", 0.2))
FRAME_MOD_PCT = float(os.environ.get("FRAME_MOD_PCT", 0.2))
BATCH_SIZE_FOR_VOTE = int(os.environ.get("BATCH_SIZE_FOR_VOTE", 4))

UPLOAD_RETENTION_DAYS = int(os.environ.get("UPLOAD_RETENTION_DAYS", 8))
SECONDARY_ROTATION_DAYS = int(os.environ.get("SECONDARY_ROTATION_DAYS", 7))

# Rate-limiter (moved up to avoid circular import)
RATE_LIMIT_REQUESTS_PER_MIN = int(os.environ.get("RATE_LIMIT_REQUESTS_PER_MIN", 30))

# Load settings
def load_settings():
    from .utils import read_json
    settings = read_json(SETTINGS_FILE, {
        "report_day": "Sunday",
        "model_rotation_days": 7,
        "api_image_quota": 5000,
        "api_video_quota": 100
    })
    return settings

settings = load_settings()

# Quotas
API_IMAGE_QUOTA = settings.get("api_image_quota", 5000)
API_VIDEO_QUOTA = settings.get("api_video_quota", 100)
API_DAILY_QUOTA = API_IMAGE_QUOTA  # convenience

# Auth
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable is required")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 60*24))  # 24h
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", 30))

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
if not ADMIN_EMAIL:
    raise ValueError("ADMIN_EMAIL environment variable is required")

# SMTP
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS")
if not GMAIL_USER or not GMAIL_APP_PASS:
    raise ValueError("GMAIL_USER and GMAIL_APP_PASS environment variables are required")

# Ensure directories exist
for d in [DATA_DIR, UPLOADS_DIR, MODELS_DIR, PRIORITY_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
