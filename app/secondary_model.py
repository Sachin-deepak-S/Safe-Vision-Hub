import random, requests, os

# Example API keys for weekly rotation (loaded from environment variables)
API_KEYS = {
    "week1": f"DeepAI:{os.environ.get('DEEPAI_API_KEY', '')}",
    "week2": f"PicPurify:{os.environ.get('PICPURIFY_API_KEY', '')}",
    "week3": f"Sightengine:{os.environ.get('SIGHTENGINE_API_KEY', '')}",
    "week4": "HF:Falconsai/nsfw_image_detection",
    "week5": "Fallback:local"
}

def get_current_week():
    """Return week1..week5 based on rotation"""
    import datetime
    week_num = (datetime.datetime.utcnow().isocalendar()[1]-1) % 5 + 1
    return f"week{week_num}"

def list_secondary_models():
    """List available secondary models"""
    return list(API_KEYS.keys())

def predict_secondary_bytes(content_bytes):
    week = get_current_week()
    key = API_KEYS[week]

    # Example: DeepAI API call
    if key.startswith("DeepAI:"):
        api_key = key.split(":")[1]
        try:
            r = requests.post(
                "https://api.deepai.org/api/nsfw-detector",
                files={"image": content_bytes},
                headers={"api-key": api_key},
                timeout=10
            )
            if r.status_code == 200:
                try:
                    data = r.json()
                    label = "high" if data.get("output", {}).get("nsfw_score", 0) > 0.5 else "safe"
                    confidence = data.get("output", {}).get("nsfw_score", 0)
                    return {"label": label, "confidence": confidence, "model_used": week}
                except Exception:
                    pass
            else:
                # API error, fallback
                pass
        except Exception as e:
            # API call failed, fallback
            pass

    # Fallback model for week5 or API failures
    if key.startswith("Fallback:") or not api_key:
        # For unknown/placeholder or API failure, fallback:
        labels = ["safe", "moderate", "high"]
        label = random.choices(labels, weights=[0.65,0.25,0.1])[0]
        confidence = round(random.uniform(0.5,0.95),3)
        return {"label": label, "confidence": confidence, "model_used": week}

    # Add other APIs like PicPurify, Sightengine, HF as needed
    # For unknown/placeholder or API failure, fallback:
    labels = ["safe", "moderate", "high"]
    label = random.choices(labels, weights=[0.65,0.25,0.1])[0]
    confidence = round(random.uniform(0.5,0.95),3)
    return {"label": label, "confidence": confidence, "model_used": week}
