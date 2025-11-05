import os, cv2, torch, json, random
from pathlib import Path
from .config import MODELS_DIR, CACHE_FILE
from .logger import app_logger

# Load model (placeholder for actual model loading)
def load_model():
    model_path = os.path.join(MODELS_DIR, "final_model", "model.h5")
    if os.path.exists(model_path):
        # Placeholder: In real implementation, load TensorFlow/Keras model
        app_logger.info(f"Model loaded from {model_path}")
        return {"loaded": True, "path": model_path}
    else:
        app_logger.warning(f"Model not found at {model_path}")
        return {"loaded": False}

# Predict image bytes
def predict_image_bytes(content_bytes):
    try:
        # Placeholder prediction logic
        # In real implementation, preprocess image and run model inference
        labels = ["safe", "moderate", "high"]
        label = random.choices(labels, weights=[0.7, 0.2, 0.1])[0]
        confidence = round(random.uniform(0.5, 0.95), 3)
        return {"label": label, "confidence": confidence}
    except Exception as e:
        app_logger.exception(f"Error predicting image: {e}")
        return {"status": "error", "message": "Prediction failed"}

# Predict video aggregated (multi-frame processing)
def predict_video_aggregated(video_path):
    try:
        if not os.path.exists(video_path):
            return {"status": "error", "message": "Video file not found"}

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"status": "error", "message": "Cannot open video file"}

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps if fps > 0 else 0

        # Sample frames (e.g., every 1 second)
        sample_interval = int(fps) if fps > 0 else 30
        frame_results = []
        frame_number = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_number % sample_interval == 0:
                # Convert frame to bytes
                success, buffer = cv2.imencode('.jpg', frame)
                if success:
                    frame_bytes = buffer.tobytes()
                    result = predict_image_bytes(frame_bytes)
                    frame_results.append({
                        "frame": frame_number,
                        "timestamp": frame_number / fps if fps > 0 else 0,
                        "label": result.get("label", "unknown"),
                        "confidence": result.get("confidence", 0.0)
                    })

            frame_number += 1

        cap.release()

        if not frame_results:
            return {"status": "error", "message": "No frames processed"}

        # Aggregate results
        labels = [r["label"] for r in frame_results]
        confidences = [r["confidence"] for r in frame_results]

        # Majority vote for label
        from collections import Counter
        majority_label = Counter(labels).most_common(1)[0][0]

        # Average confidence
        avg_confidence = sum(confidences) / len(confidences)

        return {
            "label": majority_label,
            "confidence": round(avg_confidence, 3),
            "frames_analyzed": len(frame_results),
            "total_frames": frame_count,
            "duration": round(duration, 2),
            "frame_details": frame_results
        }

    except Exception as e:
        app_logger.exception(f"Error predicting video: {e}")
        return {"status": "error", "message": "Video prediction failed"}

# Cache management
def get_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        app_logger.exception(f"Error reading cache: {e}")
        return {}

def set_cache(data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        app_logger.exception(f"Error writing cache: {e}")

# Initialize model on import
MODEL = load_model()
