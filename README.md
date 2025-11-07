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
- [Building and Integrating Your Own Model](#-building-and-integrating-your-own-model)
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
│
├── app.py # Legacy entry-point (use app/main.py)
│
├── app/
│ ├── main.py # FastAPI app
│ ├── config.py # Environment config
│ ├── auth.py # Authentication utilities
│ ├── model_utils.py # Primary model inference
│ ├── secondary_model.py # External API integrations
│ ├── feedback_system.py # Feedback collection & processing
│ ├── api_keys.py # API key management
│ ├── utils.py # Helper utilities
│ ├── logger.py # Logging setup
│ ├── scheduler.py # Background tasks
│ └── train_model.py # Model training
│
├── models/
│ └── final_model/
│ ├── model.h5 # Primary NSFW detection model
│ └── metadata.json # Model metadata
│
├── data/
│ ├── uploads/ # Uploaded images/videos
│ ├── feedback.json # User feedback data
│ ├── users.json # User data
│ └── ...
│
├── app/templates/
│ ├── static/ # CSS, JS, images
│ └── ...
│
├── requirements.txt # Dependencies
├── runtime.txt # Python version for deployment
├── Dockerfile # Docker configuration
├── .env.example # Example environment file
├── .gitignore # Git ignore rules
├── README.md # Project documentation
└── LICENSE # License file

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
📁 Model & Weights
Primary model: models/final_model/model.h5

Secondary models: Integrated via APIs (DeepAI, PicPurify, Sightengine)

You can also create and use your own custom model — see the next section.

🧩 Building and Integrating Your Own Model
If you’d like to train your own NSFW detection or content-classification model instead of using a pre-trained one, you can easily integrate it into this project.

🧠 Step 1 — Train or Prepare Your Model
Train your own model using TensorFlow, PyTorch, or any ML framework.
Here’s an example using TensorFlow Keras:

python
Copy code
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# Example: Build a simple CNN model
model = Sequential([
    Conv2D(32, (3,3), activation='relu', input_shape=(128,128,3)),
    MaxPooling2D(2,2),
    Conv2D(64, (3,3), activation='relu'),
    MaxPooling2D(2,2),
    Flatten(),
    Dense(128, activation='relu'),
    Dropout(0.5),
    Dense(1, activation='sigmoid')  # Binary classification: Safe / NSFW
])

model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

# Load and train on your dataset
train_datagen = ImageDataGenerator(rescale=1./255, validation_split=0.2)

train_data = train_datagen.flow_from_directory(
    'dataset/',
    target_size=(128,128),
    batch_size=32,
    class_mode='binary',
    subset='training'
)

val_data = train_datagen.flow_from_directory(
    'dataset/',
    target_size=(128,128),
    batch_size=32,
    class_mode='binary',
    subset='validation'
)

model.fit(train_data, validation_data=val_data, epochs=10)

# Save model
model.save('models/final_model/model.h5')
🧩 Step 2 — Integrate Your Model
Place your trained model inside:

bash
Copy code
models/final_model/model.h5
Update your model loading logic in app/model_utils.py:

python
Copy code
from tensorflow.keras.models import load_model

def load_local_model():
    model_path = "models/final_model/model.h5"
    model = load_model(model_path)
    print("✅ Custom model loaded successfully.")
    return model
Now your app will use your own model during predictions.

🧪 Step 3 — Test in the App
Run locally:

bash
Copy code
python app/main.py
Upload an image in the web UI and verify model predictions.

💡 Tips for Model Development
Use a diverse dataset (Safe + NSFW examples)

Preprocess all images to a consistent size (e.g., 128×128)

Evaluate on validation/test data

Consider fine-tuning open models like:

OpenNSFW2 (TensorFlow)

Yahoo OpenNSFW

Keep model size <100 MB for easy deployment (Hugging Face compatible)

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

📦 Deployment (e.g., on Hugging Face Spaces)
Option 1 – Using Docker (Recommended for FastAPI)
Select “Docker” as SDK in Hugging Face Spaces.

Upload or connect your GitHub repo.

Ensure Dockerfile, requirements.txt, and runtime.txt exist.

Add environment variables under Settings → Secrets & Variables.

Click Deploy.

Option 2 – Using Gradio/Streamlit Wrapper
Wrap the FastAPI app using Gradio for quick demos.

📖 API Documentation
Once running:

Swagger UI → http://localhost:8000/docs

ReDoc → http://localhost:8000/redoc

🪵 Logging
Logs are managed via logger.py.
Default: logs/app.log.
Edit log level or rotation inside that file.

🔐 Security Notes
Don’t commit your .env file.

Use Gmail App Passwords, not real credentials.

Keep your JWT secret safe.

Rotate API keys regularly.

Sanitize and validate file uploads.

👍 Contributing
Fork the repo

Create a branch:

bash
Copy code
git checkout -b feature/my-feature
Commit & push:

bash
Copy code
git commit -m "Add new feature"
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

## 👤 Author
**Sachin Deepak S**  
📧 [sachindeepak4181@gmail.com](mailto:sachindeepak4181@gmail.com)  
🌐 [LinkedIn](https://www.linkedin.com/in/sachin-deepak-s/) | [GitHub](https://github.com/Sachin-deepak-S)

⚠️ Disclaimer & Ethical Use
This tool is intended for educational and research purposes only.
Detection results are probabilistic and not guaranteed 100% accurate.
Always ensure ethical use and compliance with privacy laws, data protection standards, and platform policies.
