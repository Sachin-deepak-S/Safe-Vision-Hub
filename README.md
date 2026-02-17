# Safe-Vision-Hub

> **AI-powered visual content moderation** — detect, blur, and filter NSFW images and videos using deep learning.

[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.x-FF6F00?logo=tensorflow&logoColor=white)](https://www.tensorflow.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Build](https://img.shields.io/github/actions/workflow/status/Sachin-deepak-S/Safe-Vision-Hub/python-app.yml?label=CI)](https://github.com/Sachin-deepak-S/Safe-Vision-Hub/actions)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Installation](#installation)
- [Running the App](#running-the-app)
- [Model & Weights](#model--weights)
- [Training Your Own Model](#training-your-own-model)
- [API Reference](#api-reference)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [License](#license)
- [Acknowledgements](#acknowledgements)
- [Author](#author)
- [Disclaimer](#disclaimer)

---

## Overview

**Safe-Vision-Hub** is a production-ready content moderation system that classifies images and videos as **safe** or **NSFW** (Not Safe For Work). It combines a locally trained CNN with optional fallback to commercial APIs (DeepAI, Sightengine, PicPurify), giving you both privacy-first on-device inference and high-accuracy cloud-backed detection.

Built on **FastAPI**, it ships with a full web UI (Jinja2 templates), a REST API, JWT-based user authentication, an admin dashboard, a human feedback loop, and an automated model-retraining pipeline.

---

## Key Features

| Feature | Description |
|---|---|
| 🔍 **NSFW Detection** | Binary safe/unsafe classification with confidence scores |
| 🔄 **Fallback Chain** | Local model → DeepAI → Sightengine → PicPurify |
| 🌀 **Auto-blur** | Gaussian blur applied to flagged images before display |
| 👤 **Auth** | JWT-based login, registration, and role-based access (user / admin) |
| 📊 **Admin Dashboard** | Usage analytics, user management, and feedback stats |
| 🔁 **Feedback Loop** | Users can correct predictions; model retrains automatically |
| ⏱️ **Scheduler** | Cron-driven retraining and upload cleanup via APScheduler |
| ☁️ **Cloud-ready** | Docker + Hugging Face Spaces support out of the box |

---

## Architecture

```
Browser / API Client
        │
        ▼
┌─────────────────────────────┐
│        FastAPI App          │
│  ┌──────────┐ ┌──────────┐  │
│  │  Routers │ │ Jinja2 UI│  │
│  └────┬─────┘ └──────────┘  │
│       │                     │
│  ┌────▼──────────────────┐  │
│  │   Detection Pipeline  │  │
│  │  Local CNN  →  APIs   │  │
│  └───────────────────────┘  │
│  ┌──────────┐ ┌──────────┐  │
│  │ Auth/JWT │ │Scheduler │  │
│  └──────────┘ └──────────┘  │
└─────────────────────────────┘
        │
   ┌────┴────┐
   │  Data   │
   │ uploads │
   │feedback │
   │ users   │
   └─────────┘
```

---

## Repository Structure

```
Safe-Vision-Hub/
│
├── app.py                          # Gunicorn / Uvicorn entry point
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app factory, middleware, lifespan
│   ├── config.py                   # Pydantic-based settings (reads .env)
│   ├── auth.py                     # JWT creation, password hashing, dependencies
│   ├── model_utils.py              # Local Keras model: lazy load + predict
│   ├── secondary_model.py          # External API wrappers + fallback chain
│   ├── feedback_system.py          # Persist & query user feedback
│   ├── utils.py                    # File validation, blur, thumbnails, email
│   ├── logger.py                   # Structured rotating-file logger
│   ├── scheduler.py                # APScheduler: retrain + cleanup jobs
│   ├── train_model.py              # CNN training & retraining pipeline
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py                 # POST /auth/register, /auth/token
│   │   ├── detect.py               # POST /detect/image, /detect/video
│   │   ├── feedback.py             # POST /feedback/submit
│   │   └── admin.py                # GET  /admin/dashboard, /admin/users
│   │
│   └── templates/
│       ├── index.html
│       ├── dashboard.html
│       └── static/
│           ├── css/
│           └── js/
│
├── models/
│   └── final_model/
│       ├── model.h5                # ← download from Releases (not in git)
│       └── metadata.json
│
├── data/
│   ├── uploads/                    # Temporary user uploads
│   ├── feedback.json               # User correction records (JSON-Lines)
│   └── users.json                  # User store
│
├── tests/
│   ├── test_auth.py
│   ├── test_detect.py
│   └── test_feedback.py
│
├── scripts/
│   └── train_local.py              # Standalone training script
│
├── .env.example                    # Environment variable template
├── .gitignore
├── Dockerfile
├── requirements.txt
├── runtime.txt                     # python-3.10.x (for Hugging Face Spaces)
└── README.md
```

---

## Installation

### Prerequisites

- Python 3.10 or higher
- pip

### 1. Clone the repository

```bash
git clone https://github.com/Sachin-deepak-S/Safe-Vision-Hub.git
cd Safe-Vision-Hub
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate       # macOS / Linux
# venv\Scripts\activate        # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Download the model weights

Pre-trained weights are hosted on GitHub Releases (too large for the repo):

```bash
# Download and place the file at:
#   models/final_model/model.h5
#
# → https://github.com/Sachin-deepak-S/Safe-Vision-Hub/releases
```

### 5. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```dotenv
# ── Required ────────────────────────────────────────────
JWT_SECRET=your-strong-secret-key-here
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me

# ── Email notifications (Gmail) ─────────────────────────
GMAIL_USER=you@gmail.com
GMAIL_APP_PASS=your-gmail-app-password

# ── Optional: external API fallbacks ────────────────────
DEEPAI_API_KEY=
PICPURIFY_API_KEY=
SIGHTENGINE_API_KEY=
SIGHTENGINE_API_SECRET=

# ── Tuning ───────────────────────────────────────────────
NSFW_THRESHOLD=0.5        # 0.0–1.0 detection sensitivity
MAX_UPLOAD_MB=10
ENVIRONMENT=development   # development | production
```

---

## Running the App

### Development (Uvicorn with auto-reload)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open → [http://localhost:8000](http://localhost:8000)

### Production (Gunicorn + Uvicorn workers)

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Docker

```bash
docker build -t safe-vision-hub .
docker run -p 8000:8000 --env-file .env safe-vision-hub
```

---

## Model & Weights

| Item | Detail |
|---|---|
| **Default model path** | `models/final_model/model.h5` |
| **Architecture** | Custom CNN (Conv2D → MaxPool → Dense) |
| **Input size** | 128 × 128 × 3 |
| **Output** | Single sigmoid neuron (0 = safe, 1 = NSFW) |
| **Threshold** | Configurable via `NSFW_THRESHOLD` (default `0.5`) |
| **Fallback APIs** | DeepAI, Sightengine, PicPurify (tried in order) |

> ⚠️ Add `models/final_model/model.h5` to `.gitignore` to avoid pushing large binary files to GitHub.

---

## Training Your Own Model

You can train a custom classifier and drop it straight into the project.

### Step 1 — Prepare your dataset

Organise images into two sub-folders:

```
dataset/
├── safe/
│   ├── image1.jpg
│   └── ...
└── nsfw/
    ├── image2.jpg
    └── ...
```

### Step 2 — Train

```python
# Call app.train_model.train_from_directory directly, or use the script:
from app.train_model import train_from_directory

train_from_directory("dataset/", epochs=15)
# Saves to models/final_model/model.h5 automatically
```

Or via the command line:

```bash
python scripts/train_local.py --dataset dataset/ --epochs 15
```

The training pipeline uses this architecture:

```
Conv2D(32)  → MaxPool
Conv2D(64)  → MaxPool
Conv2D(128) → MaxPool
Dense(256)  → Dropout(0.5)
Dense(1, sigmoid)
```

### Step 3 — Verify

Start the app and upload a test image via the web UI or API. The new weights are loaded automatically on the next request.

---

## API Reference

FastAPI generates interactive documentation automatically:

| Interface | URL |
|---|---|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **Health check** | `GET /health` |

### Core endpoints

```
POST  /auth/register          Register a new user
POST  /auth/token             Obtain a JWT (OAuth2 password flow)

POST  /detect/image           Upload an image → classification result
POST  /detect/video           Upload a video → per-frame results

POST  /feedback/submit        Submit a label correction

GET   /admin/dashboard        Aggregated stats (admin only)
GET   /admin/users            List all users (admin only)
```

### Example — detect an image

```bash
# 1. Obtain a token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -d "username=you@example.com&password=yourpassword" \
  | jq -r .access_token)

# 2. Submit an image for detection
curl -X POST http://localhost:8000/detect/image \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@photo.jpg"
```

**Response:**

```json
{
  "label": "SAFE",
  "is_nsfw": false,
  "confidence": 0.9712,
  "source": "local"
}
```

---

## Deployment

### Hugging Face Spaces (Docker SDK)

1. Create a new Space and choose **Docker** as the SDK.
2. Connect your GitHub repository.
3. Confirm these files exist: `Dockerfile`, `requirements.txt`, `runtime.txt`.
4. Add your secrets under **Settings → Repository secrets**.
5. Push to trigger an automatic build and deploy.

### Production environment variables

```dotenv
ENVIRONMENT=production
DEBUG=false
ALLOWED_ORIGINS=https://your-domain.com
ALLOWED_HOSTS=your-domain.com
```

---

## Contributing

Contributions are welcome! Here's the workflow:

```bash
# 1. Fork and clone
git clone https://github.com/your-username/Safe-Vision-Hub.git

# 2. Create a feature branch
git checkout -b feature/your-feature-name

# 3. Make changes and run the tests
pytest tests/

# 4. Commit with a descriptive message
git commit -m "feat: add batch image analysis endpoint"

# 5. Push and open a pull request
git push origin feature/your-feature-name
```

Please follow the existing code style and include tests for any new functionality.

---

## Roadmap

- [x] Image upload & NSFW detection
- [x] Admin dashboard & user management
- [x] Feedback system & automated retraining
- [x] Multi-backend fallback chain (DeepAI, Sightengine, PicPurify)
- [ ] Video frame-by-frame detection
- [ ] Batch image analysis endpoint
- [ ] Cloud storage integration (AWS S3, Google Cloud Storage)
- [ ] Mobile-responsive UI
- [ ] Real-time webcam moderation

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.
You are free to use, modify, and distribute it with attribution.

---

## Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/) — modern, high-performance web framework
- [TensorFlow / Keras](https://www.tensorflow.org/) — deep learning backend
- [DeepAI NSFW Detector](https://deepai.org/machine-learning-model/nsfw-detector)
- [Sightengine](https://sightengine.com/) — visual content moderation API
- [PicPurify](https://www.picpurify.com/) — image moderation API
- [Hugging Face](https://huggingface.co/) — model hosting and deployment

---

## Author

**Sachin Deepak S**

[![Email](https://img.shields.io/badge/Email-sachindeepak4181%40gmail.com-D14836?logo=gmail&logoColor=white)](mailto:sachindeepak4181@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Sachin--Deepak--S-0077B5?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/sachin-deepak-s/)
[![GitHub](https://img.shields.io/badge/GitHub-Sachin--deepak--S-181717?logo=github&logoColor=white)](https://github.com/Sachin-deepak-S)

---

## Disclaimer

This project is intended for **educational and research purposes only**.

- Detection results are probabilistic and may not be 100% accurate.
- Do not use this tool for unlawful surveillance or content screening without proper consent.
- Always comply with applicable data-privacy laws (GDPR, CCPA, etc.) and platform guidelines.
- The author accepts no liability for misuse of this software.