import threading, time, smtplib, ssl, json, os, requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from .utils import cleanup_uploads, read_json, write_json, now_iso
from .config import (
    UPLOAD_RETENTION_DAYS,
    API_USAGE_FILE,
    RETRAINING_FILE,
    SECONDARY_ROTATION_DAYS,
    REPORTS_DIR,
    ADMIN_EMAIL,
    GMAIL_USER,
    SMTP_SERVER,
    SMTP_PORT,
    GMAIL_APP_PASS,
    settings,
)
from .logger import app_logger
from .feedback_system import trigger_retraining_if_ready

STOP = False
scheduler = BackgroundScheduler()

# =====================================================
# 🧾 PDF Weekly Summary Report
# =====================================================
def generate_weekly_summary():
    """
    Generate a weekly PDF summary report of usage stats.
    """
    try:
        report_dir = REPORTS_DIR if REPORTS_DIR else "reports"
        os.makedirs(report_dir, exist_ok=True)
        filename = os.path.join(report_dir, f"weekly_report_{datetime.now().strftime('%Y%m%d')}.pdf")

        # Create PDF canvas
        c = canvas.Canvas(filename, pagesize=A4)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 800, "NSFW AI Weekly Summary Report")
        c.setFont("Helvetica", 12)
        c.drawString(100, 770, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Usage stats
        usage = read_json(API_USAGE_FILE, {})
        total_images = sum([v.get("image_count", 0) for v in usage.values()])
        total_videos = sum([v.get("video_count", 0) for v in usage.values()])
        total_requests = sum([v.get("requests", 0) for v in usage.values()])

        c.drawString(100, 740, f"Total image scans: {total_images}")
        c.drawString(100, 720, f"Total video scans: {total_videos}")
        c.drawString(100, 700, f"Total API requests: {total_requests}")

        # Retraining info
        retrain_data = read_json(RETRAINING_FILE, {})
        feedback_count = len(retrain_data) if isinstance(retrain_data, dict) else 0
        c.drawString(100, 670, f"Feedback entries collected: {feedback_count}")

        # Add a separator line
        c.line(100, 650, 500, 650)

        # Footer
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(100, 620, "Generated automatically by NSFW AI Hub Scheduler.")
        c.showPage()
        c.save()

        app_logger.info(f"✅ Weekly PDF report generated at {filename}")
        return filename
    except Exception as e:
        app_logger.exception(f"Failed to generate weekly report PDF: {e}")
        return None


# =====================================================
# 📧 Email Weekly Report
# =====================================================
def _send_weekly_report():
    """
    Send a lightweight HTML summary + attach PDF.
    """
    try:
        usage = read_json(API_USAGE_FILE, {})
        today = datetime.utcnow().date().isoformat()
        summary = f"Weekly report: generated at {now_iso()}<br>Total days stored: {len(usage)}"

        # Generate PDF before sending
        pdf_file = generate_weekly_summary()

        msg = MIMEMultipart()
        msg["Subject"] = "NSFW AI Hub Weekly Report"
        msg["From"] = GMAIL_USER
        msg["To"] = ADMIN_EMAIL
        msg.attach(MIMEText(summary, "html"))

        # Attach PDF if exists
        if pdf_file and os.path.exists(pdf_file):
            with open(pdf_file, "rb") as f:
                from email.mime.application import MIMEApplication
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header("Content-Disposition", "attachment", filename=os.path.basename(pdf_file))
                msg.attach(attach)

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(GMAIL_USER, GMAIL_APP_PASS)
            server.sendmail(GMAIL_USER, ADMIN_EMAIL, msg.as_string())

        app_logger.info("📤 Weekly report email sent to %s", ADMIN_EMAIL)
    except Exception as e:
        app_logger.exception(f"Failed to send weekly report: {e}")


# =====================================================
# 🔄 Auto-Update Mechanism
# =====================================================
def check_for_updates():
    """
    Check for updates from a remote repository or API.
    """
    try:
        # Example: Check GitHub for latest release
        response = requests.get("https://api.github.com/repos/your-repo/nsfw-ai-hub/releases/latest", timeout=10)
        if response.status_code == 200:
            latest_version = response.json().get("tag_name")
            current_version = "1.0.0"  # Hardcoded for now; could read from a version file
            if latest_version and latest_version != current_version:
                app_logger.info(f"New version available: {latest_version}")
                # Trigger update process (e.g., download and restart)
                # For now, just log
            else:
                app_logger.info("No updates available")
        else:
            app_logger.warning("Failed to check for updates")
    except Exception as e:
        app_logger.exception(f"Update check failed: {e}")


# =====================================================
# 🔄 Auto-Retraining Mechanism
# =====================================================
def auto_retrain():
    """
    Automatically retrain the model using auto-retrain flagged entries.
    """
    try:
        from .feedback_system import get_recent_feedback
        from .config import FEEDBACK_FILE
        import subprocess

        feedback_data = read_json(FEEDBACK_FILE, [])
        auto_retrain_entries = [e for e in feedback_data if e.get("auto_retrain")]

        if not auto_retrain_entries:
            app_logger.info("No auto-retrain entries found.")
            return

        # Prepare retrain data
        retrain_path = "data/auto_retrain_data.json"
        write_json(retrain_path, auto_retrain_entries)
        app_logger.info(f"Prepared {len(auto_retrain_entries)} entries for auto-retraining.")

        # Run training script
        trainer_script = os.path.join(os.path.dirname(__file__), "..", "train_model.py")
        trainer_script = os.path.normpath(trainer_script)
        if not os.path.exists(trainer_script):
            trainer_script = os.path.join(os.getcwd(), "train_model.py")

        if not os.path.exists(trainer_script):
            app_logger.error("train_model.py not found; cannot start auto-retraining.")
            return

        cmd = ["python", trainer_script, "--data", retrain_path]
        app_logger.info("Starting auto-retraining subprocess: %s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        stdout = proc.stdout
        stderr = proc.stderr
        exitcode = proc.returncode
        app_logger.info("Auto-retraining finished with exit code %s", exitcode)

        if exitcode == 0:
            app_logger.info("Auto-retraining successful.")
            # Mark entries as retrained
            for e in auto_retrain_entries:
                e["auto_retrained"] = True
            write_json(FEEDBACK_FILE, feedback_data)
        else:
            app_logger.error(f"Auto-retraining failed: {stderr}")

    except Exception as e:
        app_logger.exception(f"Auto-retraining failed: {e}")


# =====================================================
# 🔄 Weekly Retraining with Admin Approved Feedback
# =====================================================
def weekly_retrain():
    """
    Weekly retraining using all admin-approved feedback, then clear used data.
    """
    try:
        from .config import FEEDBACK_FILE, RETRAINING_FILE
        import subprocess

        feedback_data = read_json(FEEDBACK_FILE, [])
        approved_entries = [e for e in feedback_data if e.get("admin_approved")]

        if not approved_entries:
            app_logger.info("No admin-approved feedback for weekly retraining.")
            return

        # Prepare retrain data
        retrain_path = "data/weekly_retrain_data.json"
        write_json(retrain_path, approved_entries)
        app_logger.info(f"Prepared {len(approved_entries)} approved entries for weekly retraining.")

        # Run training script
        trainer_script = os.path.join(os.path.dirname(__file__), "..", "train_model.py")
        trainer_script = os.path.normpath(trainer_script)
        if not os.path.exists(trainer_script):
            trainer_script = os.path.join(os.getcwd(), "train_model.py")

        if not os.path.exists(trainer_script):
            app_logger.error("train_model.py not found; cannot start weekly retraining.")
            return

        cmd = ["python", trainer_script, "--data", retrain_path]
        app_logger.info("Starting weekly retraining subprocess: %s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        stdout = proc.stdout
        stderr = proc.stderr
        exitcode = proc.returncode
        app_logger.info("Weekly retraining finished with exit code %s", exitcode)

        if exitcode == 0:
            app_logger.info("Weekly retraining successful.")
            # Remove used feedback entries
            remaining_feedback = [e for e in feedback_data if not e.get("admin_approved")]
            write_json(FEEDBACK_FILE, remaining_feedback)
            app_logger.info(f"Cleared {len(approved_entries)} approved feedback entries after retraining.")
        else:
            app_logger.error(f"Weekly retraining failed: {stderr}")

    except Exception as e:
        app_logger.exception(f"Weekly retraining failed: {e}")


# =====================================================
# ⏰ APScheduler Jobs Setup
# =====================================================
def setup_scheduler():
    """
    Setup APScheduler jobs.
    """
    report_day = settings.get("report_day", "Sunday").lower()
    day_map = {"monday": "mon", "tuesday": "tue", "wednesday": "wed", "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun"}
    cron_day = day_map.get(report_day, "sun")

    # Cleanup uploads hourly
    scheduler.add_job(cleanup_uploads, IntervalTrigger(hours=1), id='cleanup_uploads')

    # Send weekly report on configurable day at 9 AM
    scheduler.add_job(_send_weekly_report, CronTrigger(day_of_week=cron_day, hour=9), id='weekly_report')

    # Check for updates daily at 2 AM
    scheduler.add_job(check_for_updates, CronTrigger(hour=2), id='check_updates')

    # Auto-retrain weekly on Monday at 3 AM
    scheduler.add_job(auto_retrain, CronTrigger(day_of_week='mon', hour=3), id='auto_retrain')

    # Weekly retrain with approved feedback on Tuesday at 4 AM
    scheduler.add_job(weekly_retrain, CronTrigger(day_of_week='tue', hour=4), id='weekly_retrain')

    # Check for sector-based retraining daily at 5 AM
    scheduler.add_job(trigger_retraining_if_ready, CronTrigger(hour=5), id='sector_retrain_check')

    app_logger.info("APScheduler jobs set up")


# =====================================================
# 🚀 Start Scheduler
# =====================================================
def start_scheduler():
    setup_scheduler()
    scheduler.start()
    app_logger.info("APScheduler started")


# =====================================================
# 🛑 Stop Scheduler
# =====================================================
def stop_scheduler():
    scheduler.shutdown()
    app_logger.info("APScheduler stopped")
