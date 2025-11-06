# 🧠 Safe-Vision-Hub  
> A deep-learning powered visual content safety system for detecting NSFW / unsafe images and videos.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Framework-green)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Build](https://img.shields.io/github/actions/workflow/status/Sachin-deepak-S/Safe-Vision-Hub/python-app.yml?label=Build)

---

## 📚 Table of Contents
- [Project Overview](#-project-overview)
- [Key Features](#-key-features)
- [Repository Structure](#-repository-structure)
- [Installation & Setup](#-installation--setup)
- [How to Run](#-how-to-run-the-application)
- [Model & Weights](#-model--weights)
- [Demo / Usage Example](#-demo--usage-example)
- [Dependencies](#-dependencies--technology-stack)
- [Deployment](#-deployment-eg-on-hugging-face-spaces)
- [API Documentation](#-api-documentation)
- [Logging](#-logging)
- [Security Notes](#-security-notes)
- [Contributing](#-contributing)
- [License](#-license)
- [Roadmap](#-roadmap)
- [Acknowledgements](#-acknowledgements)
- [Author](#-author)
- [Disclaimer](#-disclaimer--ethical-use)

---

## 📌 Project Overview
**Safe-Vision-Hub** is a FastAPI-based AI system built to help detect and filter visual content that may be *Not Safe For Work (NSFW)* or otherwise unsafe.  
It supports uploading images (and optionally videos), classifies them using AI models, and allows automatic blurring or masking of detected unsafe regions.  

The system includes an admin dashboard, authentication, feedback loop for model retraining, and optional integration with external APIs for secondary validation.

---

## 🔍 Key Features
- 🔎 Detect NSFW and unsafe content in images/videos  
- 🧱 Modular design: FastAPI backend + Jinja2 frontend  
- 👥 User authentication and management system  
- 📊 Admin dashboard with analytics and logs  
- 🔁 Feedback collection and model retraining pipeline  
- 🔐 API key management for external AI models (DeepAI, PicPurify, Sightengine)  
- 🧰 REST API for integration with external services  
- ☁️ Cloud-ready, easily deployable via Docker or Hugging Face Spaces  

---

## 🧱 Repository Structure
Safe-Vision-Hub/
├── app.py ← Legacy entry-point (use app/main.py)
├── app/
│ ├── main.py ← FastAPI app
│ ├── config.py ← Environment config
│ ├── auth.py ← Authentication utilities
│ ├── model_utils.py ← Primary model inference
│ ├── secondary_model.py ← External API integrations
│ ├── feedback_system.py ← Feedback collection & processing
│ ├── api_keys.py ← API key management
│ ├── utils.py ← Helper utilities
│ ├── logger.py ← Logging setup
│ ├── scheduler.py ← Background tasks
│ └── train_model.py ← Model training
├── models/
│ └── final_model/
│ ├── model.h5 ← Primary NSFW detection model
│ └── metadata.json ← Model metadata
├── data/
│ ├── uploads/ ← Uploaded images/videos
│ ├── feedback.json ← User feedback data
│ ├── users.json ← User data
│ └── ...
├── app/templates/ ← Jinja2 templates
│ ├── static/ ← CSS, JS, images
│ └── ...
├── requirements.txt
├── runtime.txt
├── Dockerfile
├── .env.example
├── .gitignore
├── README.md
└── LICENSE

yaml
Copy code

---

## 🚀 Installation & Setup
1. **Clone the repository**
   ```bash
   git clone https://github.com/Sachin-deepak-S/Safe-Vision-Hub.git
   cd Safe-Vision-Hub
Create a virtual environment

bash
Copy code
python -m venv venv
source venv/bin/activate        # macOS/Linux
# Windows: venv\Scripts\activate
Install dependencies

bash
Copy code
pip install -r requirements.txt
Set up environment variables
Copy .env.example → .env and fill:

ini
Copy code
JWT_SECRET=your_secret_key
ADMIN_EMAIL=you@example.com
GMAIL_USER=you@gmail.com
GMAIL_APP_PASS=your_app_password
Optional API keys:

makefile
Copy code
DEEPAI_API_KEY=
PICPURIFY_API_KEY=
SIGHTENGINE_API_KEY=
Add your primary model
Place your model files under:

bash
Copy code
models/final_model/
├── model.h5
└── metadata.json
🧪 How to Run the Application
Local Development
bash
Copy code
python app/main.py
Then visit 👉 http://localhost:8000

Production (Gunicorn)
bash
Copy code
gunicorn -w 4 -b 0.0.0.0:8000 app.main:app
CLI Example
bash
Copy code
python app/main.py --input path/to/image.jpg --output results/
📁 Model & Weights
Primary model: models/final_model/model.h5

Secondary models: Integrated via API (DeepAI, PicPurify, Sightengine)

You may also specify a Hugging Face model path if you want to load directly from transformers.

📷 Demo / Usage Example

(Add a screenshot or GIF showing the upload & detection process.)

Example:

bash
Copy code
python app/main.py --input examples/sample1.jpg --output results/
Output → results/sample1_output.jpg

🧰 Dependencies & Technology Stack
Backend: FastAPI, Uvicorn

Frontend: Jinja2 templates

ML Frameworks: TensorFlow / PyTorch / Torchvision

Image Processing: OpenCV, Pillow, NumPy

Utilities: python-dotenv, requests, logging

Deployment: Docker, Hugging Face Spaces (Gradio optional)

Python Version: 3.10+

See requirements.txt for the full package list.

📦 Deployment (e.g., on Hugging Face Spaces)
Option 1 – Using Docker (Recommended for FastAPI)
Select “Docker” as the SDK when creating a new Space.

Connect this GitHub repository or upload files manually.

Ensure Dockerfile, requirements.txt, and runtime.txt are present.

Add any required environment variables under Settings → Secrets & Variables.

Click Deploy.

Option 2 – Using Gradio/Streamlit Wrapper
If you prefer to deploy using Hugging Face’s native SDKs, wrap the FastAPI app with Gradio for demo purposes.

📖 API Documentation
Once the app is running:

Swagger UI: http://localhost:8000/docs

ReDoc: http://localhost:8000/redoc

🪵 Logging
Logs are automatically created and managed via logger.py.
Default log file: logs/app.log
You can configure verbosity or log rotation inside logger.py.

🔐 Security Notes
Never commit .env to GitHub.

Use Gmail App Passwords instead of real credentials.

Keep your JWT secret safe.

Rotate API keys regularly.

Validate all uploads to avoid malicious file injections.

👍 Contributing
Contributions are welcome!

Fork this repository

Create your feature branch

bash
Copy code
git checkout -b feature/my-feature
Commit & push changes

bash
Copy code
git commit -m "Add my feature"
git push origin feature/my-feature
Open a Pull Request 🚀

📝 License
Licensed under the MIT License.
You may freely use, modify, and distribute with attribution.

🎯 Roadmap
 Image upload + NSFW detection

 User authentication and management

 Admin dashboard

 Feedback & retraining system

 Video upload support

 Batch image processing

 Responsive UI for mobile

 Cloud storage integration (AWS S3, GCS)

 Real-time webcam detection

🙏 Acknowledgements
DeepAI NSFW Detection API

PicPurify API

Sightengine

Hugging Face Transformers

FastAPI Framework

👤 Author
Sachin Deepak S
📧 [sachindeepak4181.com]
🌐 LinkedIn | GitHub

⚠️ Disclaimer & Ethical Use
This tool is intended for educational and research purposes only.
Detection results are probabilistic and not guaranteed 100% accurate.
Always ensure ethical use and compliance with privacy laws, data protection standards, and platform policies.

yaml
Copy code
