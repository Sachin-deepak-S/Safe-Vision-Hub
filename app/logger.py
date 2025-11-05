import logging, os
BASE = os.path.dirname(os.path.dirname(__file__))
LOG_DIR = os.path.join(BASE, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def _setup(name, filename):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(os.path.join(LOG_DIR, filename))
        fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger

app_logger = _setup("app", "app.log")
feedback_logger = _setup("feedback", "feedback.log")
priority_logger = _setup("priority", "priority.log")
audit_logger = _setup("audit", "admin_audit.log")
