import os, json, time, hashlib
from pathlib import Path
from filelock import FileLock
from .config import DATA_DIR, UPLOADS_DIR, API_USAGE_FILE, CACHE_FILE, UPLOAD_RETENTION_DAYS
from .logger import app_logger
from datetime import datetime, timedelta
from cachetools import TTLCache

def _atomic_read(path, default):
    path = str(path)
    lock = FileLock(path + ".lock")
    with lock:
        if not os.path.exists(path):
            return default
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                app_logger.error("Failed to parse JSON %s; returning default", path)
                return default

def _atomic_write(path, data):
    path = str(path)
    lock = FileLock(path + ".lock")
    with lock:
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)

def read_json(path, default=None):
    if default is None:
        default = {} if str(path).endswith('.json') else []
    return _atomic_read(path, default)

def write_json(path, data):
    _atomic_write(path, data)

def append_json(path, entry):
    arr = read_json(path, [])
    arr.append(entry)
    write_json(path, arr)

def ensure_json(path, default):
    path = str(path)
    if not os.path.exists(path):
        write_json(path, default)

def save_upload(filename, content_bytes):
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    safe_name = f"{int(time.time()*1000)}_{filename}"
    path = Path(UPLOADS_DIR) / safe_name
    with open(path, 'wb') as f:
        f.write(content_bytes)
    return path.name

def file_sha256_bytes(content_bytes):
    h = hashlib.sha256()
    h.update(content_bytes)
    return h.hexdigest()

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def log_api_usage(api_calls=0, disagreements=0, api_key=None):
    today = datetime.utcnow().date().isoformat()
    d = read_json(API_USAGE_FILE, {})
    if not isinstance(d, dict):
        d = {}
    if today not in d:
        d[today] = {"api_calls": 0, "disagreements": 0, "keys": {}}
    d[today]["api_calls"] += int(api_calls)
    d[today]["disagreements"] += int(disagreements)
    if api_key:
        if api_key not in d[today]["keys"]:
            d[today]["keys"][api_key] = {"api_calls": 0, "disagreements": 0}
        d[today]["keys"][api_key]["api_calls"] += int(api_calls)
        d[today]["keys"][api_key]["disagreements"] += int(disagreements)
    write_json(API_USAGE_FILE, d)

def cleanup_uploads(retention_days=UPLOAD_RETENTION_DAYS):
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    removed = []
    p = Path(UPLOADS_DIR)
    for f in p.glob("*"):
        try:
            mtime = datetime.utcfromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                removed.append(str(f.name))
        except Exception as e:
            app_logger.exception("cleanup_uploads error: %s", e)
    return removed

# Simple in-memory rate limiter per key/ip with TTL
_rate_cache = TTLCache(maxsize=10000, ttl=60)  # 1 minute TTL

def rate_allow(key, limit=None):
    if limit is None:
        from .config import RATE_LIMIT_REQUESTS_PER_MIN
        limit = RATE_LIMIT_REQUESTS_PER_MIN
    # key can be api_key or ip or user
    count = _rate_cache.get(key, 0)
    if count + 1 > limit:
        return False
    _rate_cache[key] = count + 1
    return True
