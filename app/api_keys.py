import uuid, time
from .utils import read_json, write_json
from .config import API_KEYS_FILE, API_IMAGE_QUOTA, API_VIDEO_QUOTA
from .logger import app_logger, audit_logger

def ensure_api_file():
    d = read_json(API_KEYS_FILE, {"clients":[]})
    if "clients" not in d:
        d = {"clients": d}
    write_json(API_KEYS_FILE, d)
    return d

def create_api_key_for_user(email):
    d = read_json(API_KEYS_FILE, {"clients":[]})
    key = uuid.uuid4().hex
    client = {
        "kid": uuid.uuid4().hex[:8],
        "email": email,
        "api_key": key,
        "status": "active",
        "quota": {"image_limit": API_IMAGE_QUOTA, "video_limit": API_VIDEO_QUOTA, "image_used": 0, "video_used": 0, "reset_ts": None},
        "created": int(time.time())
    }
    d.setdefault("clients", []).append(client)
    write_json(API_KEYS_FILE, d)
    app_logger.info("API key created for %s", email)
    return client

def find_client_by_key(key):
    d = read_json(API_KEYS_FILE, {"clients":[]})
    for c in d.get("clients", []):
        if c.get("api_key") == key:
            return c
    return None

def consume_quota(client, media_type):
    import time
    d = read_json(API_KEYS_FILE, {"clients":[]})
    quota = client.setdefault("quota", {})
    now = int(time.time())
    reset = quota.get("reset_ts") or now + 86400
    if now >= reset:
        quota["image_used"] = 0
        quota["video_used"] = 0
        quota["reset_ts"] = now + 86400
    if media_type == "image":
        if quota.get("image_used", 0) + 1 > quota.get("image_limit", API_IMAGE_QUOTA):
            return False
        quota["image_used"] = quota.get("image_used", 0) + 1
    else:
        if quota.get("video_used", 0) + 1 > quota.get("video_limit", API_VIDEO_QUOTA):
            return False
        quota["video_used"] = quota.get("video_used", 0) + 1
    # persist
    for i, c in enumerate(d.get("clients", [])):
        if c.get("api_key") == client.get("api_key"):
            d["clients"][i] = client
            break
    write_json(API_KEYS_FILE, d)
    return True

def block_client(email):
    d = read_json(API_KEYS_FILE, {"clients":[]})
    changed = False
    for c in d.get("clients", []):
        if c.get("email") == email:
            c["status"] = "blocked"
            changed = True
    if changed:
        write_json(API_KEYS_FILE, d)
        audit_logger = audit_logger if 'audit_logger' in globals() else None
    return changed
