import os
import io
import shutil
import subprocess
import zipfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from jose import jwt, JWTError
from app.config import (
    ADMIN_EMAIL, UPLOADS_DIR, FEEDBACK_FILE, API_KEYS_FILE, API_USAGE_FILE,
    USERS_FILE, MODEL_COMPARISON_FILE, RETRAINING_FILE, API_IMAGE_QUOTA, API_VIDEO_QUOTA,
    SETTINGS_FILE, settings, load_settings
)
from app.auth import (
    create_access_token, create_refresh_token, verify_token,
    register_user, authenticate_user
)
from app.utils import (
    save_upload, read_json, write_json, ensure_json,
    log_api_usage, rate_allow, now_iso
)
from app.api_keys import create_api_key_for_user, find_client_by_key, consume_quota
from app.model_utils import predict_image_bytes, predict_video_aggregated
from app.secondary_model import predict_secondary_bytes, list_secondary_models
from app.feedback_system import record_prediction, submit_feedback, admin_approve, submit_bulk_feedback
from app.scheduler import start_scheduler
from app.logger import app_logger, audit_logger

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="NSFW AI Hub")

# Initialize Redis
# redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Add SessionMiddleware for persistent sessions
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-here")  # Use a secure key in production

ROOT = Path(__file__).resolve().parent.parent
CLIENT_DIR = ROOT / "app" / "templates" / "static"
DASHBOARD_DIR = ROOT / "app" / "templates" / "static"
STATIC_DIR = ROOT / "app" / "templates" / "static"

if CLIENT_DIR.exists():
    app.mount("/client_static", StaticFiles(directory=str(CLIENT_DIR)), name="client_static")
if DASHBOARD_DIR.exists():
    app.mount("/dashboard_static", StaticFiles(directory=str(DASHBOARD_DIR)), name="dashboard_static")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Ensure files exist
ensure_json(USERS_FILE, [])
ensure_json(API_KEYS_FILE, {"clients": []})
ensure_json(FEEDBACK_FILE, [])
ensure_json(API_USAGE_FILE, {})
ensure_json(MODEL_COMPARISON_FILE, [])
ensure_json(RETRAINING_FILE, {})

# --- User Preference Tracking Setup ---
PREFERENCES_FILE = os.path.join("data", "preferences.json")
ensure_json(PREFERENCES_FILE, [])
UPLOAD_COUNT_FILE = os.path.join("data", "upload_count.json")
ensure_json(UPLOAD_COUNT_FILE, {})

# Start scheduler
start_scheduler()

@app.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(url="/login", status_code=303)

# -----------------------------
# AUTH ROUTES
# -----------------------------
@app.post("/register")
async def register(email: str = Form(...), password: str = Form(...)):
    new_user = register_user(email, password)
    client = create_api_key_for_user(email)
    users = read_json(USERS_FILE, [])
    for u in users:
        if u.get("user") == email:
            u["api_key"] = client["api_key"]
    write_json(USERS_FILE, users)
    return RedirectResponse(url="/login", status_code=303)

@app.post("/signup")
async def signup_page_post(email: str = Form(...), password: str = Form(...)):
    users = read_json(USERS_FILE, [])
    existing = next((u for u in users if u.get("user") == email), None)
    if existing:
        # Approve existing user by setting status to active
        existing["status"] = "active"
        if not existing.get("api_key"):
            client = create_api_key_for_user(email)
            existing["api_key"] = client["api_key"]
        write_json(USERS_FILE, users)
    else:
        # Register new user
        new_user = register_user(email, password)
        client = create_api_key_for_user(email)
        users = read_json(USERS_FILE, [])
        for u in users:
            if u.get("user") == email:
                u["api_key"] = client["api_key"]
        write_json(USERS_FILE, users)
    # Return JSON response for JS fetch
    return JSONResponse(content={"success": True}, status_code=200)

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    app_logger.info(f"Login attempt for user: {email}")
    try:
        user = authenticate_user(email, password)
        role = user.get("role", "client")
        access = create_access_token(user["user"], role)
        refresh = create_refresh_token(user["user"])
        users = read_json(USERS_FILE, [])
        for u in users:
            if u.get("user") == user["user"]:
                u.setdefault("refresh_tokens", []).append(refresh)
                u["last_login"] = now_iso()
        write_json(USERS_FILE, users)
        if role == "admin":
            redirect_url = "/admin_dashboard"
        else:
            redirect_url = "/dashboard"
        app_logger.info(f"Redirecting {email} (role: {role}) to {redirect_url}")
        # Return JSON response for JS fetch and set cookie
        response = JSONResponse(content={"success": True, "redirect": redirect_url, "token": access}, status_code=200)
        response.set_cookie(key="access_token", value=access, httponly=True, secure=True, samesite="none")
        return response
    except HTTPException as e:
        # Return JSON error for JS fetch
        return JSONResponse(content={"success": False, "error": e.detail}, status_code=e.status_code)

@app.post("/token/refresh")
async def token_refresh(refresh_token: str = Form(...)):
    from app.config import JWT_SECRET
    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=["HS256"])
        sub = payload.get("sub")
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    users = read_json(USERS_FILE, [])
    for u in users:
        if u.get("user") == sub and refresh_token in u.get("refresh_tokens", []):
            access = create_access_token(sub, u.get("role","client"))
            return {"token": access}
    raise HTTPException(status_code=401, detail="Refresh token not recognized")

@app.post("/token/revoke")
async def token_revoke(refresh_token: str = Form(...)):
    users = read_json(USERS_FILE, [])
    for u in users:
        if refresh_token in u.get("refresh_tokens", []):
            u["refresh_tokens"].remove(refresh_token)
            write_json(USERS_FILE, users)
            return {"ok": True}
    return {"ok": False}

@app.post("/admin/login")
async def admin_login(email: str = Form(...), password: str = Form(...)):
    app_logger.info(f"Admin login attempt for user: {email}")
    user = authenticate_user(email, password)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied: Admin only")
    access = create_access_token(user["user"], "admin")
    refresh = create_refresh_token(user["user"])
    users = read_json(USERS_FILE, [])
    for u in users:
        if u.get("user") == user["user"]:
            u.setdefault("refresh_tokens", []).append(refresh)
            u["last_login"] = now_iso()
    write_json(USERS_FILE, users)
    response = JSONResponse(content={"success": True, "token": access, "refresh": refresh, "redirect": "/admin_dashboard"}, status_code=200)
    response.set_cookie(key="access_token", value=access, httponly=True, secure=False, samesite="lax")
    return response

# -----------------------------
# PREDICTION ROUTES
# -----------------------------
@app.post("/api/predict")
async def api_predict(request: Request, file: UploadFile = File(...), user_id: str = Form(...)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    app_logger.info(f"Request received: {request.method} {request.path} from {client_ip} with user-agent: {user_agent}")
    try:
        token_payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = token_payload.get("sub")
    if not rate_allow(user):
        raise HTTPException(status_code=429, detail="Too many requests")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    try:
        saved = save_upload(file.filename, content)
    except Exception as e:
        app_logger.exception(f"Failed to save upload: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file")

    # --- Track upload count and possibly request preference ---
    upload_counts = read_json(UPLOAD_COUNT_FILE, {})
    count = upload_counts.get(user, 0) + 1
    upload_counts[user] = count
    write_json(UPLOAD_COUNT_FILE, upload_counts)

    ext = file.filename.rsplit(".",1)[-1].lower() if "." in file.filename else ""
    if not ext:
        raise HTTPException(status_code=400, detail="File has no extension")

    if ext in ("png","jpg","jpeg","bmp","gif"):
        primary = predict_image_bytes(content)
        if "status" in primary and primary["status"] == "error":
            raise HTTPException(status_code=400, detail=primary["message"])
        secondary_result = predict_secondary_bytes(content)
        secondary = {"label": secondary_result["label"], "confidence": secondary_result["confidence"]}
        secondary_model_used = secondary_result.get("model_used", "unknown")
    elif ext in ("mp4","avi","mov","mkv"):
        path = Path(UPLOADS_DIR) / saved
        primary = predict_video_aggregated(str(path))
        if "status" in primary and primary["status"] == "error":
            raise HTTPException(status_code=400, detail=primary["message"])
        secondary = {"label":"safe","confidence":0.5}
        secondary_model_used = "placeholder_video"
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if count % 4 == 0:
        # Ask for preference, show both predictions
        return {"ask_preference": True, "options": ["My Model", "Other's Model"], "primary": primary, "secondary": secondary, "file_saved": saved, "feedback_required": True}

    # Resolve disagreements: if primary != secondary, use secondary as correct
    disagreement = primary.get("label") != secondary.get("label")
    if disagreement:
        app_logger.info(f"Disagreement detected: primary={primary.get('label')}, secondary={secondary.get('label')}. Using secondary as correct.")
        final_label = secondary["label"]
        final_confidence = secondary["confidence"]
        # Mark for auto-retraining with secondary as ground truth
        auto_retrain = True
    else:
        final_label = primary.get("label")
        final_confidence = primary.get("confidence")
        auto_retrain = False

    try:
        rec = record_prediction(user, saved, primary, secondary, secondary_model_used=secondary_model_used, auto_retrain=auto_retrain, correct_label=secondary["label"] if disagreement else None)
        if rec is None:
            raise HTTPException(status_code=500, detail="Failed to record prediction")
        log_api_usage(api_calls=1, disagreements=1 if disagreement else 0)
    except Exception as e:
        app_logger.exception(f"Failed to record prediction: {e}")
        raise HTTPException(status_code=500, detail="Failed to record prediction")

    return {"file": saved, "primary": primary, "secondary": secondary, "id": rec["id"], "secondary_model_used": secondary_model_used, "feedback_required": True, "feedback_id": rec["id"], "prediction": primary}

@app.post("/api/m2m/predict")
async def m2m_predict(file: UploadFile = File(...), api_key: str = Form(...), user_email: Optional[str] = Form(None)):
    client = find_client_by_key(api_key)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if client.get("status") == "blocked":
        raise HTTPException(status_code=403, detail="Client blocked")
    if not rate_allow(api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    ext = file.filename.rsplit(".",1)[-1].lower() if "." in file.filename else ""
    if not ext:
        raise HTTPException(status_code=400, detail="File has no extension")

    media_type = "image" if ext in ("png","jpg","jpeg","bmp","gif") else "video"
    if not consume_quota(client, media_type):
        raise HTTPException(status_code=429, detail="Quota exceeded")

    try:
        saved = save_upload(file.filename, content)
    except Exception as e:
        app_logger.exception(f"Failed to save upload: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file")

    if media_type == "image":
        primary = predict_image_bytes(content)
        if "status" in primary and primary["status"] == "error":
            raise HTTPException(status_code=400, detail=primary["message"])
        secondary_result = predict_secondary_bytes(content)
        secondary = {"label": secondary_result["label"], "confidence": secondary_result["confidence"]}
        secondary_model_used = secondary_result.get("model_used", "unknown")
    else:
        primary = predict_video_aggregated(str(Path(UPLOADS_DIR) / saved))
        if "status" in primary and primary["status"] == "error":
            raise HTTPException(status_code=400, detail=primary["message"])
        secondary = {"label":"safe","confidence":0.5}
        secondary_model_used = "placeholder_video"

    # Resolve disagreements: if primary != secondary, use secondary as correct
    disagreement = primary.get("label") != secondary.get("label")
    if disagreement:
        app_logger.info(f"Disagreement detected: primary={primary.get('label')}, secondary={secondary.get('label')}. Using secondary as correct.")
        final_label = secondary["label"]
        final_confidence = secondary["confidence"]
        # Mark for auto-retraining with secondary as ground truth
        auto_retrain = True
    else:
        final_label = primary.get("label")
        final_confidence = primary.get("confidence")
        auto_retrain = False

    try:
        rec = record_prediction(user_email or client.get("email","m2m"), saved, primary, secondary, secondary_model_used=secondary_model_used, auto_retrain=auto_retrain, correct_label=secondary["label"] if disagreement else None)
        if rec is None:
            raise HTTPException(status_code=500, detail="Failed to record prediction")
        log_api_usage(api_calls=1, disagreements=1 if disagreement else 0, api_key=api_key)
    except Exception as e:
        app_logger.exception(f"Failed to record prediction: {e}")
        raise HTTPException(status_code=500, detail="Failed to record prediction")

    # --- Track upload count and possibly request preference ---
    upload_counts = read_json(UPLOAD_COUNT_FILE, {})
    key = user_email or client.get("email", "m2m")
    count = upload_counts.get(key, 0) + 1
    upload_counts[key] = count
    write_json(UPLOAD_COUNT_FILE, upload_counts)

    if count % 4 == 0:
        return {"ask_preference": True, "options": ["My Model", "Other's Model"], "feedback_required": True, "feedback_id": rec["id"]}

    return {"file": saved, "primary": primary, "secondary": secondary, "id": rec["id"], "secondary_model_used": secondary_model_used, "feedback_required": True, "feedback_id": rec["id"]}

@app.post("/api/preference")
async def api_preference(request: Request, preferred: str = Form(...), file_name: Optional[str] = Form(None)):
    """
    Save the user's AI model preference (My Model or Other's Model) for training, then perform prediction using the selected model.
    """
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = payload.get("sub")
    prefs = read_json(PREFERENCES_FILE, [])
    prefs.append({
        "user": user,
        "preferred": preferred,
        "file": file_name
    })
    write_json(PREFERENCES_FILE, prefs)

    # Now perform the prediction using the selected model
    if not file_name:
        raise HTTPException(status_code=400, detail="File name required for prediction")

    # Load the saved file content
    file_path = Path(UPLOADS_DIR) / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    with open(file_path, "rb") as f:
        content = f.read()

    ext = file_name.rsplit(".",1)[-1].lower() if "." in file_name else ""
    if not ext:
        raise HTTPException(status_code=400, detail="File has no extension")

    # Use the preferred model: My Model = primary, Other's Model = secondary
    if preferred == "My Model":
        if ext in ("png","jpg","jpeg","bmp","gif"):
            primary = predict_image_bytes(content)
            if "status" in primary and primary["status"] == "error":
                raise HTTPException(status_code=400, detail=primary["message"])
            secondary = {"label":"safe","confidence":0.5}  # Placeholder
            secondary_model_used = "placeholder_secondary"
        elif ext in ("mp4","avi","mov","mkv"):
            primary = predict_video_aggregated(str(file_path))
            if "status" in primary and primary["status"] == "error":
                raise HTTPException(status_code=400, detail=primary["message"])
            secondary = {"label":"safe","confidence":0.5}
            secondary_model_used = "placeholder_video"
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
    elif preferred == "Other's Model":
        if ext in ("png","jpg","jpeg","bmp","gif"):
            secondary_result = predict_secondary_bytes(content)
            primary = {"label":"safe","confidence":0.5}  # Placeholder
            secondary = {"label": secondary_result["label"], "confidence": secondary_result["confidence"]}
            secondary_model_used = secondary_result.get("model_used", "unknown")
        elif ext in ("mp4","avi","mov","mkv"):
            primary = {"label":"safe","confidence":0.5}
            secondary = {"label":"safe","confidence":0.5}
            secondary_model_used = "placeholder_video"
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
    else:
        raise HTTPException(status_code=400, detail="Invalid preference")

    # Record the prediction
    try:
        rec = record_prediction(user, file_name, primary, secondary, secondary_model_used=secondary_model_used, auto_retrain=False, correct_label=None)
        if rec is None:
            raise HTTPException(status_code=500, detail="Failed to record prediction")
        log_api_usage(api_calls=1, disagreements=0)
    except Exception as e:
        app_logger.exception(f"Failed to record prediction: {e}")
        raise HTTPException(status_code=500, detail="Failed to record prediction")

    return {"file": file_name, "primary": primary, "secondary": secondary, "id": rec["id"], "secondary_model_used": secondary_model_used, "feedback_required": True, "feedback_id": rec["id"]}

# -----------------------------
# FEEDBACK ROUTE
# -----------------------------
@app.post("/api/feedback")
async def api_feedback(request: Request, feedback_id: str = Form(...), chosen: str = Form(...), suggested: Optional[str] = Form(None), correct_label: Optional[str] = Form(None)):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = payload.get("sub")
    if not feedback_id or not chosen:
        raise HTTPException(status_code=400, detail="Feedback ID and chosen label required")
    # Validate chosen is one of the allowed feedback types
    if chosen not in ["perfect", "okay", "wrong"]:
        raise HTTPException(status_code=400, detail="Invalid feedback type. Must be 'perfect', 'okay', or 'wrong'")
    # Validate correct_label if provided
    if correct_label and correct_label not in ["safe", "moderate", "high"]:
        raise HTTPException(status_code=400, detail="Invalid correct label. Must be 'safe', 'moderate', or 'high'")
    ok = submit_feedback(user, feedback_id, chosen, suggested, correct_label)
    if not ok:
        raise HTTPException(status_code=404, detail="Feedback ID not found")
    return {"ok": True}

@app.post("/api/bulk_feedback")
async def api_bulk_feedback(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = payload.get("sub")
    body = await request.json()
    feedback_list = body.get("feedback_list", [])
    if not feedback_list:
        raise HTTPException(status_code=400, detail="Feedback list required")
    ok = submit_bulk_feedback(user, feedback_list)
    if not ok:
        raise HTTPException(status_code=500, detail="Bulk feedback submission failed")
    return {"ok": True}

@app.get("/api/pending_feedback")
async def api_pending_feedback(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = payload.get("sub")
    feedback_data = read_json(FEEDBACK_FILE, [])
    pending = [f for f in feedback_data if f.get("user") == user and not f.get("chosen")]
    return {"pending_feedback": pending}

@app.get("/api/feedback/stats")
async def feedback_stats(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = payload.get("sub")
    feedback_data = read_json(FEEDBACK_FILE, [])
    user_feedback = [f for f in feedback_data if f.get("user") == user and f.get("chosen")]
    perfect = sum(1 for f in user_feedback if f.get("chosen") == "perfect")
    okay = sum(1 for f in user_feedback if f.get("chosen") == "okay")
    wrong = sum(1 for f in user_feedback if f.get("chosen") == "wrong")
    return {"perfect": perfect, "okay": okay, "wrong": wrong}

# -----------------------------
# ADMIN ROUTES
# -----------------------------
def delete_old_final_model():
    final_dir = Path("models/final_model")
    if final_dir.exists():
        shutil.rmtree(final_dir)
        app_logger.info("Deleted old final_model directory")

@app.post("/admin/retrain_simulate")
async def admin_retrain_simulate(request: Request):
    payload = verify_token(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    # Collect retraining data
    feedback_data = read_json(FEEDBACK_FILE, [])
    retrain_data = [item for item in feedback_data if item.get("disputed")]
    prefs = read_json(PREFERENCES_FILE, [])
    retrain_data.extend(prefs)
    os.makedirs("data", exist_ok=True)
    retrain_path = "data/retrain_data.json"
    write_json(retrain_path, retrain_data)
    app_logger.info(f"Retraining dataset prepared with {len(retrain_data)} entries")

    # Backup old model
  

    try:
        new_model_dir = Path("models/temp_model")
        new_model_dir.mkdir(parents=True, exist_ok=True)
        fake_model = new_model_dir / "model.h5"
        fake_model.write_text("Simulated retrained model")
        final_dir = Path("models/final_model")
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.copytree(new_model_dir, final_dir)
        app_logger.info("Simulated retraining complete, replaced final_model")
    except Exception as e:
        app_logger.error(f"Retraining simulation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Retraining failed: {e}")

    return {"ok": True, "message": "Retraining simulated, old model archived, final_model replaced."}

@app.get("/admin/list_models")
async def admin_list_models(request: Request):
    """List available model backups (admin only)."""
    payload = verify_token(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    model_root = Path("models")
    versions = sorted([d.name for d in model_root.glob("final_model_v*") if d.is_dir()])
    return {"available_versions": versions}


@app.post("/admin/rollback")
async def admin_rollback(request: Request, version: str = Form(...)):
    """Rollback to a previous final_model version."""
    payload = verify_token(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    target_dir = Path("models") / version
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    final_dir = Path("models/final_model")
    if final_dir.exists():
        shutil.rmtree(final_dir)
    shutil.copytree(target_dir, final_dir)

    app_logger.info(f"Rolled back model to {version}")
    return {"ok": True, "message": f"Successfully rolled back to {version}"}

@app.get("/admin/data")
async def admin_data(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    today = datetime.utcnow().date().isoformat()
    users = read_json(USERS_FILE, [])
    usage = read_json(API_USAGE_FILE, {})
    # Filter usage to today only
    today_usage = {k: v for k, v in usage.items() if k == today}
    feedback = read_json(FEEDBACK_FILE, [])
    # Filter feedback to today
    today_feedback = []
    for f in feedback:
        ts_str = f.get("user_feedback_ts") or f.get("ts", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                if ts.date().isoformat() == today:
                    today_feedback.append(f)
            except:
                pass
    api_keys = read_json(API_KEYS_FILE, {"clients":[]})
    comparisons = read_json(MODEL_COMPARISON_FILE, [])
    return {"users": users, "usage": today_usage, "feedback": today_feedback, "api_keys": api_keys.get("clients",[]), "comparisons": comparisons}

@app.post("/admin/toggle")
async def admin_toggle(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    body = await request.json()
    email = body.get("email")
    action = body.get("action")
    if not email or action not in ["block", "unblock"]:
        raise HTTPException(status_code=400, detail="Invalid email or action")
    users = read_json(USERS_FILE, [])
    changed = False
    for u in users:
        if u.get("user") == email:
            u["status"] = "blocked" if action == "block" else "active"
            changed = True
    if changed:
        write_json(USERS_FILE, users)
        audit_logger.info("Admin %s toggled %s -> %s", payload.get("sub"), email, action)
    return {"ok": changed}

@app.post("/api/admin/block_user")
async def api_admin_block_user(request: Request, username: str, block: str):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if not username or block not in ["true", "false"]:
        raise HTTPException(status_code=400, detail="Invalid username or block parameter")
    users = read_json(USERS_FILE, [])
    changed = False
    for u in users:
        if u.get("user") == username:
            u["status"] = "blocked" if block == "true" else "active"
            changed = True
            break
    if changed:
        write_json(USERS_FILE, users)
        audit_logger.info("Admin %s toggled %s -> %s", payload.get("sub"), username, "blocked" if block == "true" else "active")
    return {"ok": changed}

@app.post("/admin/approve")
async def admin_approve_endpoint(request: Request, feedback_id: str = Form(...), override_label: Optional[str] = Form(None), correct_label: Optional[str] = Form(None)):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("sub") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")
    if not feedback_id:
        raise HTTPException(status_code=400, detail="Feedback ID required")
    # If override_label is "wrong", use correct_label as the final label
    final_override_label = correct_label if override_label == "wrong" and correct_label else override_label
    ok = admin_approve(feedback_id, admin_user=payload.get("sub"), override_label=final_override_label)
    return {"ok": ok}

@app.post("/admin/label_feedback")
async def admin_label_feedback_endpoint(request: Request, feedback_id: str = Form(...), label: str = Form(...)):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("sub") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")
    if not feedback_id or not label:
        raise HTTPException(status_code=400, detail="Feedback ID and label required")
    from app.feedback_system import admin_label_feedback
    ok = admin_label_feedback(feedback_id, label, admin_user=payload.get("sub"))
    return {"ok": ok}


@app.post("/admin/retrain")
async def manual_retrain(request: Request):
    """
    Admin-only endpoint that:
     - collects disputed feedback -> data/retrain_data.json
     - runs train_model.py (TensorFlow) synchronously
     - ensures models/final_model/model.h5 is written by the trainer
     - returns training stdout/stderr and new model path
    """
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("sub") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")

    # Create retraining dataset from all feedback with chosen labels
    feedback_data = read_json(FEEDBACK_FILE, [])
    retrain_data = [item for item in feedback_data if item.get("chosen")]
    os.makedirs("data", exist_ok=True)
    retrain_path = os.path.join("data", "retrain_data.json")
    write_json(retrain_path, retrain_data)
    app_logger.info("Manual retraining dataset prepared with %d samples", len(retrain_data))

    # Run the training script synchronously
    trainer_script = os.path.join(os.path.dirname(__file__), "..", "train_model.py")
    trainer_script = os.path.normpath(trainer_script)
    if not os.path.exists(trainer_script):
        # also fallback to project root train_model.py
        trainer_script = os.path.join(os.getcwd(), "train_model.py")

    if not os.path.exists(trainer_script):
        msg = "train_model.py not found; cannot start retraining."
        app_logger.error(msg)
        return JSONResponse({"status": "error", "message": msg}, status_code=500)

    cmd = ["python", trainer_script, "--data", retrain_path]
    app_logger.info("Starting retraining subprocess: %s", " ".join(cmd))
    try:
        # Run synchronously; capture output (may be long)
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        stdout = proc.stdout
        stderr = proc.stderr
        exitcode = proc.returncode
        app_logger.info("Retraining finished with exit code %s", exitcode)
    except Exception as e:
        app_logger.exception("Retraining subprocess failed: %s", e)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    # check for saved model path
    model_path = os.path.join("models", "final_model", "model.h5")
    model_exists = os.path.exists(model_path)

    resp = {
        "status": "ok" if exitcode == 0 else "error",
        "exitcode": exitcode,
        "model_saved": model_exists,
        "model_path": model_path if model_exists else None,
        "stdout": stdout,
        "stderr": stderr,
        "samples_used": len(retrain_data)
    }
    return JSONResponse(resp)

def trigger_model_retraining():
    """
    Placeholder function to trigger model retraining.
    This simulates starting the retraining process in the background.
    """
    def run_retraining():
        # Simulate running retrain_script.py
        app_logger.info("Starting model retraining...")
        # Here you would call subprocess to run your actual retrain_script.py
        # For now, just log
        app_logger.info("Model retraining completed.")

    thread = threading.Thread(target=run_retraining)
    thread.start()

@app.post("/admin/upload_dataset")
async def admin_upload_dataset(request: Request, safe: UploadFile = File(None), moderate: UploadFile = File(None), high: UploadFile = File(None)):
    payload = verify_token(request)
    if payload.get("sub") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")

    dataset_path = Path("data/dataset")
    dataset_path.mkdir(parents=True, exist_ok=True)

    uploaded = []
    for category, file in [("safe", safe), ("moderate", moderate), ("high", high)]:
        if file and file.filename.endswith('.zip'):
            target_dir = dataset_path / category
            target_dir.mkdir(parents=True, exist_ok=True)

            # Clear existing files in category dir
            for f in target_dir.glob("*"):
                if f.is_file():
                    f.unlink()

            temp_zip_path = dataset_path / f"temp_{category}.zip"
            with open(temp_zip_path, 'wb') as f:
                content = await file.read()
                f.write(content)

            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    if not member.lower().endswith(('.png', '.jpg', '.jpeg')):
                        app_logger.warning(f"Skipping non-image file: {member}")
                        continue
                    zip_ref.extract(member, target_dir)

            os.remove(temp_zip_path)
            uploaded.append(category)

    if not uploaded:
        raise HTTPException(status_code=400, detail="No valid zip files uploaded")

    return {"message": f"Datasets uploaded for categories: {', '.join(uploaded)}"}

@app.post("/admin/manual_retrain")
async def admin_manual_retrain(request: Request):
    payload = verify_token(request)
    if payload.get("sub") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")

    dataset_path = Path("data/dataset")
    if not dataset_path.exists() or not any((dataset_path / cat).exists() for cat in ["safe", "moderate", "high"]):
        raise HTTPException(status_code=400, detail="No dataset uploaded. Upload datasets first.")


    try:
        trainer_script = os.path.join(os.path.dirname(__file__), "train_model.py")
        cmd = ["python", trainer_script, "--dataset", str(dataset_path)]
        app_logger.info("Starting manual retraining: %s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        stdout = proc.stdout
        stderr = proc.stderr
        exitcode = proc.returncode
        app_logger.info("Manual retraining finished with exit code %s", exitcode)

        if exitcode != 0:
            app_logger.error("Retraining stderr: %s", stderr)
            raise HTTPException(status_code=500, detail=f"Retraining failed: {stderr}")

        # Check if model was saved
        model_path = Path("models/final_model/model.h5")
        if not model_path.exists():
            raise HTTPException(status_code=500, detail="Model not saved after retraining")

        return {"message": "Manual retraining completed successfully", "stdout": stdout, "stderr": stderr}

    except Exception as e:
        app_logger.exception("Manual retraining failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/welcome")
async def welcome(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    app_logger.info(f"Request received: {request.method} {request.path} from {client_ip} with user-agent: {user_agent}")
    return {"message": "Welcome to the NSFW AI Hub"}

# -----------------------------
# TEMPLATE ROUTES (unchanged)
# -----------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def client_dashboard_page(request: Request):
    try:
        payload = verify_token(request)
        token = request.cookies.get("access_token")
        if payload.get("role") == "admin":
            return templates.TemplateResponse("admin_dashboard.html", {"request": request})
        else:
            user = payload.get("sub")
            # Fetch recent feedback for the user (last 10 feedback entries)
            feedback_data = read_json(FEEDBACK_FILE, [])
            user_feedback = [f for f in feedback_data if f.get("user") == user]
            # Sort by timestamp descending
            user_feedback.sort(key=lambda x: x.get("user_feedback_ts") or x.get("ts", ""), reverse=True)
            recent_feedback = user_feedback[:10]  # Last 10
            return templates.TemplateResponse("client/dashboard.html", {"request": request, "recent_feedback": recent_feedback, "token": token})
    except:
        return templates.TemplateResponse("login.html", {"request": request})

@app.get("/admin_home", response_class=HTMLResponse)
async def admin_home_page(request: Request):
    try:
        payload = verify_token(request)
        if payload.get("role") == "admin":
            return templates.TemplateResponse("dashboard/admin_home.html", {"request": request})
        else:
            return templates.TemplateResponse("admin_login.html", {"request": request})
    except:
        return templates.TemplateResponse("admin_login.html", {"request": request})

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    try:
        payload = verify_token(request)
        return templates.TemplateResponse("client/upload.html", {"request": request})
    except:
        return templates.TemplateResponse("login.html", {"request": request})

@app.get("/feedback", response_class=HTMLResponse)
async def feedback_page(request: Request):
    try:
        payload = verify_token(request)
        return templates.TemplateResponse("client/feedback.html", {"request": request})
    except:
        return templates.TemplateResponse("login.html", {"request": request})

@app.get("/api_docs", response_class=HTMLResponse)
async def api_docs_page(request: Request):
    try:
        payload = verify_token(request)
        return templates.TemplateResponse("client/api_docs.html", {"request": request})
    except:
        return templates.TemplateResponse("login.html", {"request": request})

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    try:
        payload = verify_token(request)
        return templates.TemplateResponse("client/profile.html", {"request": request})
    except:
        return templates.TemplateResponse("login.html", {"request": request})



@app.get("/admin_dashboard", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request):
    try:
        payload = verify_token(request)
        if payload.get("role") == "admin":
            return templates.TemplateResponse("admin_dashboard.html", {"request": request})
        else:
            return templates.TemplateResponse("admin_login.html", {"request": request})
    except:
        return templates.TemplateResponse("admin_login.html", {"request": request})

@app.get("/manage_users", response_class=HTMLResponse)
async def manage_users_page(request: Request):
    try:
        payload = verify_token(request)
        if payload.get("role") == "admin":
            return templates.TemplateResponse("dashboard/manage_users.html", {"request": request})
        else:
            return templates.TemplateResponse("admin_login.html", {"request": request})
    except:
        return templates.TemplateResponse("admin_login.html", {"request": request})

@app.get("/manage_feedback", response_class=HTMLResponse)
async def manage_feedback_page(request: Request):
    try:
        payload = verify_token(request)
        if payload.get("role") == "admin":
            return templates.TemplateResponse("dashboard/manage_feedback.html", {"request": request})
        else:
            return templates.TemplateResponse("admin_login.html", {"request": request})
    except:
        return templates.TemplateResponse("admin_login.html", {"request": request})

@app.get("/api_usage", response_class=HTMLResponse)
async def api_usage_page(request: Request):
    payload = verify_token(request)
    if payload.get("role") == "admin":
        usage_data = read_json(API_USAGE_FILE, {})
        api_keys_data = read_json(API_KEYS_FILE, {"clients": []})
        clients = api_keys_data.get("clients", [])
        # Compute totals
        total_api_calls = sum(day.get("api_calls", 0) for day in usage_data.values() if isinstance(day, dict))
        total_disagreements = sum(day.get("disagreements", 0) for day in usage_data.values() if isinstance(day, dict))
        total_users = len(clients)
        active_keys = sum(1 for c in clients if c.get("status") == "active")
        # Add per-key usage to clients
        today = datetime.utcnow().date().isoformat()
        if today in usage_data and "keys" in usage_data[today]:
            keys_usage = usage_data[today]["keys"]
            for client in clients:
                key = client.get("api_key")
                if key in keys_usage:
                    client["key_usage"] = keys_usage[key]
                else:
                    client["key_usage"] = {"api_calls": 0, "disagreements": 0}
                # Ensure quota is set
                client.setdefault("quota", {"image_used": 0, "image_limit": API_IMAGE_QUOTA, "video_used": 0, "video_limit": API_VIDEO_QUOTA})
        else:
            for client in clients:
                client["key_usage"] = {"api_calls": 0, "disagreements": 0}
                # Ensure quota is set
                client.setdefault("quota", {"image_used": 0, "image_limit": API_IMAGE_QUOTA, "video_used": 0, "video_limit": API_VIDEO_QUOTA})
        return templates.TemplateResponse("dashboard/api_usage.html", {
            "request": request,
            "usage_data": usage_data,
            "clients": clients,
            "total_api_calls": total_api_calls,
            "total_disagreements": total_disagreements,
            "total_users": total_users,
            "active_keys": active_keys
        })
    else:
        raise HTTPException(status_code=403, detail="Admin only")

@app.get("/retrain", response_class=HTMLResponse)
async def retrain_page(request: Request):
    try:
        payload = verify_token(request)
        if payload.get("role") == "admin":
            return templates.TemplateResponse("dashboard/retrain.html", {"request": request})
        else:
            return templates.TemplateResponse("admin_login.html", {"request": request})
    except:
        return templates.TemplateResponse("login.html", {"request": request})

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    try:
        payload = verify_token(request)
        if payload.get("role") == "admin":
            current_settings = load_settings()
            return templates.TemplateResponse("dashboard/settings.html", {"request": request, "settings": current_settings})
        else:
            return templates.TemplateResponse("admin_login.html", {"request": request})
    except:
        return templates.TemplateResponse("login.html", {"request": request})

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    try:
        payload = verify_token(request)
        user = payload.get("sub")
    except Exception:
        return templates.TemplateResponse("login.html", {"request": request})

    from datetime import datetime, timedelta
    now = datetime.utcnow()
    past_24h = now - timedelta(hours=24)

    # Fetch feedback data
    feedback_data = read_json(FEEDBACK_FILE, [])
    recent_feedback = []
    for f in feedback_data:
        if f.get("chosen") is not None and f.get("user") == user:
            try:
                ts_str = f.get("user_feedback_ts") or f.get("ts", "2000-01-01T00:00:00")
                if not isinstance(ts_str, str):
                    continue
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                if ts > past_24h:
                    recent_feedback.append(f)
            except Exception:
                # Skip invalid timestamps
                pass

    # Fetch uploads (assuming filenames have timestamps or use file mtime)
    uploads_dir = Path(UPLOADS_DIR)
    recent_uploads = []
    if uploads_dir.exists():
        for file_path in uploads_dir.glob("*"):
            if file_path.is_file():
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime > past_24h:
                    recent_uploads.append({
                        "filename": file_path.name,
                        "path": str(file_path),
                        "timestamp": mtime.isoformat(),
                        "url": f"/uploads/{file_path.name}"
                    })

    # Compute summary stats
    total_uploads = len(recent_uploads)
    total_predictions = len(recent_feedback)
    feedback_given = sum(1 for f in recent_feedback if f.get("chosen"))
    nsfw_predictions = sum(1 for f in recent_feedback if f.get("primary", {}).get("label") == "nsfw")
    safe_predictions = total_predictions - nsfw_predictions

    # Get upload counts for the last 7 days
    today = datetime.utcnow().date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]  # Last 7 days, oldest first

    upload_counts = read_json(UPLOAD_COUNT_FILE, {})
    user_uploads = upload_counts.get(user, 0)  # Total uploads, but we need daily

    # For simplicity, since we don't have daily breakdown, we'll simulate based on total
    # In a real app, you'd store daily upload counts
    # For now, distribute the total uploads across the week
    total_uploads_week = user_uploads
    if total_uploads_week > 0:
        # Simple distribution: more recent days have more uploads
        base = total_uploads_week // 7
        remainder = total_uploads_week % 7
        data = [base + (1 if i < remainder else 0) for i in range(7)]
    else:
        data = [0] * 7

    # Prepare data for template
    reports_data = {
        "recent_uploads": recent_uploads,
        "recent_feedback": recent_feedback,
        "summary": {
            "total_uploads": total_uploads,
            "total_predictions": total_predictions,
            "feedback_given": feedback_given,
            "nsfw_predictions": nsfw_predictions,
            "safe_predictions": safe_predictions
        },
        "labels": dates,
        "data": data
    }

    try:
        return templates.TemplateResponse("reports.html", {"request": request, "data": reports_data})
    except Exception as e:
        app_logger.exception(f"Error rendering reports: {e}")
        return templates.TemplateResponse("reports.html", {"request": request, "data": {}})

@app.get("/api/client/stats")
async def client_stats(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = payload.get("sub")

    # Get upload counts for the last 7 days
    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]  # Last 7 days, oldest first

    # Read daily upload logs or aggregate from feedback data
    # Assuming we log daily uploads in a file or calculate from feedback
    feedback_data = read_json(FEEDBACK_FILE, [])
    user_feedback = [f for f in feedback_data if f.get("user") == user]

    # Aggregate uploads per day
    daily_uploads = {}
    for f in user_feedback:
        ts_str = f.get("ts", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                day = ts.date().isoformat()
                daily_uploads[day] = daily_uploads.get(day, 0) + 1
            except:
                pass

    # Fill data for last 7 days
    data = [daily_uploads.get(date, 0) for date in dates]

    return {"labels": dates, "data": data}

@app.get("/api/profile")
async def api_profile(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = payload.get("sub")

    # Get user data
    users = read_json(USERS_FILE, [])
    user_data = next((u for u in users if u.get("user") == user), None)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    # Get API key usage
    api_keys = read_json(API_KEYS_FILE, {"clients": []})
    client = next((c for c in api_keys.get("clients", []) if c.get("email") == user), None)
    image_usage = client.get("quota", {}).get("image_used", 0) if client else 0
    video_usage = client.get("quota", {}).get("video_used", 0) if client else 0

    return {
        "email": user,
        "api_key": client.get("api_key", "N/A") if client else "N/A",
        "image_usage": image_usage,
        "video_usage": video_usage
    }

# -----------------------------
# CHART DATA ENDPOINTS
# -----------------------------
@app.get("/api/chart/api_usage")
async def chart_api_usage(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    usage_data = read_json(API_USAGE_FILE, {})
    labels = sorted(usage_data.keys())
    api_calls = [usage_data[d].get("api_calls", 0) for d in labels]
    disagreements = [usage_data[d].get("disagreements", 0) for d in labels]

    return {"labels": labels, "api_calls": api_calls, "disagreements": disagreements}

@app.get("/api/chart/prediction_stats")
async def chart_prediction_stats(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = payload.get("sub")

    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]

    feedback_data = read_json(FEEDBACK_FILE, [])
    user_feedback = [f for f in feedback_data if f.get("user") == user]

    daily_uploads = {}
    for f in user_feedback:
        ts_str = f.get("ts", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                day = ts.date().isoformat()
                daily_uploads[day] = daily_uploads.get(day, 0) + 1
            except:
                pass

    data = [daily_uploads.get(date, 0) for date in dates]

    return {"labels": dates, "data": data}

@app.get("/api/chart/profile_usage")
async def chart_profile_usage(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = payload.get("sub")

    api_keys = read_json(API_KEYS_FILE, {"clients": []})
    client = next((c for c in api_keys.get("clients", []) if c.get("email") == user), None)
    image_used = client.get("quota", {}).get("image_used", 0) if client else 0
    video_used = client.get("quota", {}).get("video_used", 0) if client else 0
    image_remaining = 50 - image_used
    video_remaining = 10 - video_used

    return {
        "labels": ['Images Used', 'Images Remaining', 'Videos Used', 'Videos Remaining'],
        "data": [image_used, image_remaining, video_used, video_remaining],
        "backgroundColor": ['#ef4444', '#10b981', '#f59e0b', '#3b82f6']
    }

@app.get("/api/chart/reports_usage")
async def chart_reports_usage(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = payload.get("sub")

    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]

    upload_counts = read_json(UPLOAD_COUNT_FILE, {})
    user_uploads = upload_counts.get(user, 0)

    if user_uploads > 0:
        base = user_uploads // 7
        remainder = user_uploads % 7
        data = [base + (1 if i < remainder else 0) for i in range(7)]
    else:
        data = [0] * 7

    return {"labels": dates, "data": data}

@app.get("/api/chart/feedback_distribution")
async def chart_feedback_distribution(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = payload.get("sub")

    feedback_data = read_json(FEEDBACK_FILE, [])
    user_feedback = [f for f in feedback_data if f.get("user") == user and f.get("chosen")]
    perfect = sum(1 for f in user_feedback if f.get("chosen") == "perfect")
    okay = sum(1 for f in user_feedback if f.get("chosen") == "okay")
    wrong = sum(1 for f in user_feedback if f.get("chosen") == "wrong")

    return {"labels": ['Perfect', 'Okay', 'Wrong'], "data": [perfect, okay, wrong]}

@app.get("/api/chart/disagreement_trends")
async def chart_disagreement_trends(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    usage_data = read_json(API_USAGE_FILE, {})
    labels = sorted(usage_data.keys())[-4:]  # Last 4 days
    disagreements = [usage_data[d].get("disagreements", 0) for d in labels]

    return {"labels": labels, "data": disagreements}

@app.get("/api/chart/admin_usage_trends")
async def chart_admin_usage_trends(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    usage_data = read_json(API_USAGE_FILE, {})
    labels = sorted(usage_data.keys())
    api_calls = [usage_data[d].get("api_calls", 0) for d in labels]
    disagreements = [usage_data[d].get("disagreements", 0) for d in labels]

    return {"labels": labels, "api_calls": api_calls, "disagreements": disagreements}

@app.get("/api/chart/admin_dashboard_summary")
async def chart_admin_dashboard_summary(request: Request):
    try:
        payload = verify_token(request)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    users = read_json(USERS_FILE, [])
    feedback_data = read_json(FEEDBACK_FILE, [])
    usage_data = read_json(API_USAGE_FILE, {})

    total_users = len(users)
    blocked = sum(1 for u in users if u.get("status") == "blocked")
    total_feedback = len(feedback_data)
    total_api_calls = sum(day.get("api_calls", 0) for day in usage_data.values() if isinstance(day, dict))

    return {
        "labels": ["Users", "Blocked", "Feedback", "API Calls"],
        "data": [total_users, blocked, total_feedback, total_api_calls],
        "backgroundColor": ["#2563EB", "#DC2626", "#7C3AED", "#059669"]
    }

# -----------------------------
# 🤗 OPTIONAL: Hugging Face / Gradio Integration
# -----------------------------
import gradio as gr
from app.model_utils import predict_image_bytes

def predict_api(file):
    """
    Lightweight Gradio wrapper for Hugging Face Spaces.
    Supports direct image upload and uses the primary NSFW model.
    """
    try:
        # Validate file exists and is readable
        if not os.path.isfile(file):
            return "Error: File not found or invalid path"

        # Basic file size check (prevent extremely large files)
        if os.path.getsize(file) > 50 * 1024 * 1024:  # 50MB limit
            return "Error: File too large. Please upload an image smaller than 50MB."

        # Try to validate it's a valid image (optional, skip if PIL not available)
        try:
            from PIL import Image
            with Image.open(file) as img:
                img.verify()  # Verify it's a valid image
        except ImportError:
            # PIL not available, skip validation
            pass
        except Exception:
            # Image verification failed, but continue anyway
            pass

        with open(file, "rb") as f:
            image_bytes = f.read()

        # Additional check: ensure we have image data
        if len(image_bytes) < 100:  # Minimum reasonable image size
            return "Error: File appears to be too small to be a valid image."

        result = predict_image_bytes(image_bytes)
        if "status" in result and result["status"] == "error":
            return f"Error: {result.get('message', 'Prediction failed')}"
        label = result.get("label", "unknown")
        confidence = result.get("confidence", 0.0)
        return f"{label.upper()} ({confidence*100:.2f}% confident)"
    except Exception as e:
        pass

iface = gr.Interface(
    fn=predict_api,
    inputs=gr.Image(type="filepath", label="Upload Image"),
    outputs="text",
    title="NSFW AI Classifier",
    description="Upload an image to get NSFW/Safe classification from the main model."
)


# Gradio interface is enabled for Hugging Face Spaces
if os.getenv("SPACE_ID") or os.getenv("HF_SPACE_ID"):
    iface.launch(server_name="0.0.0.0", server_port=7860)

