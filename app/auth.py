from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
import bcrypt
from .config import JWT_SECRET, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, ADMIN_EMAIL, USERS_FILE
from .utils import read_json, write_json, ensure_json, now_iso
from datetime import datetime, timedelta
from .logger import app_logger, audit_logger

security = HTTPBearer()

def create_access_token(sub: str, role: str, expires_minutes=ACCESS_TOKEN_EXPIRE_MINUTES):
    exp = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {"sub": sub, "role": role, "exp": int(exp.timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def create_refresh_token(sub: str, days=REFRESH_TOKEN_EXPIRE_DAYS):
    exp = datetime.utcnow() + timedelta(days=days)
    payload = {"sub": sub, "type": "refresh", "exp": int(exp.timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(request: Request):
    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ",1)[1]
    else:
        # Check for token in cookies
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        app_logger.info("Token verified for user %s", payload.get("sub"))
        return payload
    except JWTError as e:
        app_logger.error("Token verify failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid token")

def get_user(email):
    users = read_json(USERS_FILE, [])
    for u in users:
        if u.get("user") == email:
            return u
    return None

def register_user(email, password, role="client"):
    ensure_json(USERS_FILE, [])
    users = read_json(USERS_FILE, [])
    if any(u.get("user") == email for u in users):
        raise HTTPException(status_code=400, detail="Already exists")
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new = {"user": email, "password": hashed, "role": role, "status": "active", "api_key": "", "usage": {"images":0,"videos":0}, "refresh_tokens": [], "created_at": now_iso(), "last_login": None}
    users.append(new)
    write_json(USERS_FILE, users)
    app_logger.info("Registered user %s", email)
    return new

def authenticate_user(email, password):
    user = get_user(email)
    if not user and email == ADMIN_EMAIL:
        user = register_user(email, password, role="admin")
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("status") == "blocked":
        raise HTTPException(status_code=403, detail="Blocked")
    if not bcrypt.checkpw(password.encode('utf-8'), user.get("password").encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Set role based on email
    if email == ADMIN_EMAIL:
        user["role"] = "admin"
    else:
        user["role"] = "client"
    return user

def revoke_refresh_token(email, token):
    users = read_json(USERS_FILE, [])
    for u in users:
        if u.get("user") == email:
            tokens = u.setdefault("refresh_tokens", [])
            if token in tokens:
                tokens.remove(token)
                write_json(USERS_FILE, users)
                return True
    return False

def ensure_admin(email):
    return email == ADMIN_EMAIL
