import uuid, os, json
from datetime import datetime, timedelta
from .utils import append_json, read_json, write_json, now_iso
from .config import FEEDBACK_FILE, MODEL_COMPARISON_FILE, RETRAINING_FILE, PRIORITY_DIR, FEEDBACK_SECTORS_FILE, ADMIN_AUDIT_FILE
from .logger import feedback_logger, priority_logger, audit_logger

def record_prediction(user_id, path, primary, secondary, secondary_model_used="unknown", auto_retrain=False, correct_label=None):
    if not user_id or not path:
        feedback_logger.error("Invalid user_id or path for prediction recording")
        return None
    if not isinstance(primary, dict) or not isinstance(secondary, dict):
        feedback_logger.error("Invalid primary or secondary prediction data")
        return None

    entry = {
        "id": uuid.uuid4().hex[:12],
        "user": user_id,
        "path": path,
        "primary": primary,
        "secondary": secondary,
        "secondary_model_used": secondary_model_used,
        "chosen": None,
        "suggested_label": None,
        "admin_approved": False,
        "auto_retrain": auto_retrain,
        "correct_label": correct_label,
        "feedback_type": None,  # New field for perfect/okay/wrong
        "ts": now_iso()
    }
    try:
        append_json(FEEDBACK_FILE, entry)
        feedback_logger.info("Recorded prediction %s user=%s path=%s secondary=%s auto_retrain=%s",
                             entry["id"], user_id, path, secondary_model_used, auto_retrain)
    except Exception as e:
        feedback_logger.exception(f"Failed to record prediction: {e}")
        return None

    compare = {"id": entry["id"], "path": path, "primary": primary,
               "secondary": secondary, "secondary_model_used": secondary_model_used,
               "ts": entry["ts"]}
    try:
        append_json(MODEL_COMPARISON_FILE, compare)
    except Exception as e:
        feedback_logger.exception(f"Failed to record model comparison: {e}")

    if primary.get("label") != secondary.get("label"):
        try:
            os.makedirs(PRIORITY_DIR, exist_ok=True)
            pr_path = os.path.join(PRIORITY_DIR, f"{entry['id']}.json")
            with open(pr_path, "w", encoding="utf-8") as f:
                json.dump({
                    "id": entry["id"],
                    "path": path,
                    "primary": primary,
                    "secondary": secondary,
                    "secondary_model_used": secondary_model_used,
                    "correct_label": correct_label,
                    "ts": entry["ts"]
                }, f, indent=2)
            priority_logger.info("Saved priority feedback %s", pr_path)
        except Exception as e:
            priority_logger.exception(f"Failed to save priority feedback: {e}")

    return entry

def submit_feedback(user_id, feedback_id, chosen_label, suggested_label=None, correct_label=None):
    if not user_id or not feedback_id or not chosen_label:
        feedback_logger.error("Invalid parameters for feedback submission")
        return False

    # Validate chosen_label is one of the allowed types
    if chosen_label not in ["perfect", "okay", "wrong"]:
        feedback_logger.error("Invalid feedback type: %s", chosen_label)
        return False

    # Validate correct_label if provided
    if correct_label and correct_label not in ["safe", "moderate", "high"]:
        feedback_logger.error("Invalid correct label: %s", correct_label)
        return False

    try:
        arr = read_json(FEEDBACK_FILE, [])
        updated = False
        for e in arr:
            if e.get("id") == feedback_id:
                e["chosen"] = chosen_label
                e["feedback_type"] = chosen_label  # Store in new field too
                e["suggested_label"] = suggested_label
                e["correct_label"] = correct_label if chosen_label == "wrong" else None
                e["user_feedback_ts"] = now_iso()
                # Set approval deadline to 7 days from now
                e["approval_deadline"] = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
                e["admin_reviewed"] = False
                updated = True
                break
        if updated:
            write_json(FEEDBACK_FILE, arr)
            feedback_logger.info("User %s submitted feedback %s -> %s", user_id, feedback_id, chosen_label)
            return True
        else:
            feedback_logger.warning("Feedback ID %s not found", feedback_id)
    except Exception as e:
        feedback_logger.exception(f"Failed to submit feedback: {e}")
    return False

def admin_approve(feedback_id, admin_user=None, override_label=None, reason=None):
    if not feedback_id:
        audit_logger.error("Invalid feedback_id for admin approval")
        return False

    try:
        arr = read_json(FEEDBACK_FILE, [])
        sectors = read_json(FEEDBACK_SECTORS_FILE, {"safe": [], "moderate": [], "high": []})
        audit_log = read_json(ADMIN_AUDIT_FILE, [])
        for e in arr:
            if e.get("id") == feedback_id:
                original_label = e.get("chosen")
                e["admin_approved"] = True
                e["admin_reviewed"] = True
                if override_label:
                    e["chosen"] = override_label
                    e["override_reason"] = reason
                e["admin_approved_ts"] = now_iso()
                write_json(FEEDBACK_FILE, arr)

                # Store in sectors based on final label
                final_label = e.get("chosen")
                if final_label in sectors:
                    sectors[final_label].append(e)
                    write_json(FEEDBACK_SECTORS_FILE, sectors)

                # Log audit
                audit_entry = {
                    "id": uuid.uuid4().hex[:12],
                    "feedback_id": feedback_id,
                    "action": "approve",
                    "admin_user": admin_user,
                    "original_label": original_label,
                    "final_label": final_label,
                    "override": override_label is not None,
                    "reason": reason,
                    "ts": now_iso()
                }
                audit_log.append(audit_entry)
                write_json(ADMIN_AUDIT_FILE, audit_log)

                audit_logger.info("Admin %s approved feedback %s with label %s", admin_user, feedback_id, final_label)
                return True
        audit_logger.warning("Feedback ID %s not found for approval", feedback_id)
    except Exception as e:
        audit_logger.exception(f"Failed to approve feedback: {e}")
    return False

def admin_label_feedback(feedback_id, label, admin_user=None):
    """
    Admin labels unlabeled feedback or overrides existing labels.
    """
    if not feedback_id or label not in ["perfect", "okay", "wrong"]:
        feedback_logger.error("Invalid feedback_id or label for admin labeling")
        return False

    try:
        arr = read_json(FEEDBACK_FILE, [])
        for e in arr:
            if e.get("id") == feedback_id:
                e["chosen"] = label
                e["feedback_type"] = label
                e["admin_labeled"] = True
                e["admin_labeled_ts"] = now_iso()
                if admin_user:
                    e["admin_user"] = admin_user
                write_json(FEEDBACK_FILE, arr)
                feedback_logger.info("Admin %s labeled feedback %s as %s", admin_user, feedback_id, label)
                return True
        feedback_logger.warning("Feedback ID %s not found for admin labeling", feedback_id)
    except Exception as e:
        feedback_logger.exception(f"Failed to admin label feedback: {e}")
    return False

def get_recent_feedback(limit=50):
    if limit <= 0:
        return []
    try:
        arr = read_json(FEEDBACK_FILE, [])
        return sorted(arr, key=lambda x: x.get("ts",""), reverse=True)[:limit]
    except Exception as e:
        feedback_logger.exception(f"Failed to get recent feedback: {e}")
        return []

def submit_bulk_feedback(user_id, feedback_list):
    """
    Submit feedback for multiple predictions at once.
    feedback_list: list of dicts with 'feedback_id', 'chosen', 'suggested_label' (optional)
    """
    if not user_id or not isinstance(feedback_list, list):
        feedback_logger.error("Invalid parameters for bulk feedback submission")
        return False

    try:
        arr = read_json(FEEDBACK_FILE, [])
        updated_count = 0
        for fb in feedback_list:
            feedback_id = fb.get("feedback_id")
            chosen_label = fb.get("chosen")
            suggested_label = fb.get("suggested_label")

            if not feedback_id or not chosen_label:
                feedback_logger.warning("Skipping invalid feedback entry: %s", fb)
                continue

            if chosen_label not in ["perfect", "okay", "wrong"]:
                feedback_logger.warning("Invalid feedback type: %s for ID %s", chosen_label, feedback_id)
                continue

            for e in arr:
                if e.get("id") == feedback_id:
                    e["chosen"] = chosen_label
                    e["feedback_type"] = chosen_label
                    e["suggested_label"] = suggested_label
                    e["user_feedback_ts"] = now_iso()
                    # Set approval deadline to 7 days from now
                    e["approval_deadline"] = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
                    e["admin_reviewed"] = False
                    updated_count += 1
                    break

        if updated_count > 0:
            write_json(FEEDBACK_FILE, arr)
            feedback_logger.info("User %s submitted bulk feedback for %d items", user_id, updated_count)
            return True
        else:
            feedback_logger.warning("No valid feedback items updated in bulk submission")
    except Exception as e:
        feedback_logger.exception(f"Failed to submit bulk feedback: {e}")
    return False

def get_approved_feedback_for_retraining():
    """
    Get feedback that is ready for retraining: either admin-reviewed or past 7-day deadline.
    """
    try:
        arr = read_json(FEEDBACK_FILE, [])
        now = datetime.utcnow()
        approved = []
        for e in arr:
            if e.get("chosen") and not e.get("admin_approved"):
                deadline_str = e.get("approval_deadline")
                if deadline_str:
                    try:
                        deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
                        if now >= deadline or e.get("admin_reviewed", False):
                            approved.append(e)
                    except ValueError:
                        # Invalid deadline, treat as ready
                        approved.append(e)
                elif e.get("admin_reviewed", False):
                    approved.append(e)
        return approved
    except Exception as e:
        feedback_logger.exception(f"Failed to get approved feedback: {e}")
        return []

def trigger_retraining_if_ready():
    """
    Check if all sectors have data and trigger retraining.
    """
    try:
        sectors = read_json(FEEDBACK_SECTORS_FILE, {"safe": [], "moderate": [], "high": []})
        if all(len(sectors[sector]) > 0 for sector in ["safe", "moderate", "high"]):
            feedback_logger.info("All sectors have data, triggering retraining")
            # Combine all sector data
            retrain_data = []
            for sector_data in sectors.values():
                retrain_data.extend(sector_data)

            # Write to retraining file
            rt = read_json(RETRAINING_FILE, {})
            batch_name = f"sector_batch_{len(rt)+1}"
            rt[batch_name] = retrain_data
            write_json(RETRAINING_FILE, rt)

            # Clear sectors after triggering
            write_json(FEEDBACK_SECTORS_FILE, {"safe": [], "moderate": [], "high": []})

            feedback_logger.info("Retraining triggered with %d samples from sectors", len(retrain_data))
            return True
        else:
            feedback_logger.info("Not all sectors have data yet")
            return False
    except Exception as e:
        feedback_logger.exception(f"Failed to trigger retraining: {e}")
        return False
