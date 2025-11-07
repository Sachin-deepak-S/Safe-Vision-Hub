# 🧠 Safe-Vision-Hub  
> A deep-learning powered visual content safety system for detecting and filtering NSFW / unsafe images and videos.

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
- [How to Run](#-how-to-run)
- [Model & Weights](#-model--weights)
- [Building and Integrating Your Own Model](#-building-and-integrating-your-own-model)
- [Usage Example](#-usage-example)
- [Deployment](#-deployment)
- [API Documentation](#-api-documentation)
- [Contributing](#-contributing)
- [License](#-license)
- [Roadmap](#-roadmap)
- [Acknowledgements](#-acknowledgements)
- [Author](#-author)
- [Disclaimer](#-disclaimer--ethical-use)

---

## 📌 Project Overview
**Safe-Vision-Hub** is an AI-powered system built using **FastAPI** for safe and responsible content moderation.  
It detects NSFW (Not Safe For Work) or unsafe images and videos, allowing automatic blurring or blocking of inappropriate content.  
The system supports user authentication, feedback loops, admin dashboards, and model retraining.

---

## 🔍 Key Features
- 🚫 Detect NSFW and unsafe visual content  
- 🧱 Modular design: FastAPI backend + Jinja2 templates  
- 👥 User authentication and management  
- 📊 Admin dashboard with analytics  
- 🔁 Feedback collection and model retraining pipeline  
- 🔐 API key management for external AI APIs (DeepAI, Sightengine, PicPurify)  
- ☁️ Cloud-ready and deployable on Hugging Face Spaces or Docker  

---

## 🧱 Repository Structure
Safe-Vision-Hub/
│
├── app.py # Legacy entry-point
│
├── app/
│ ├── main.py # FastAPI app
│ ├── config.py # Configuration and environment variables
│ ├── auth.py # Authentication utilities
│ ├── model_utils.py # Model inference logic
│ ├── secondary_model.py # External API integrations
│ ├── feedback_system.py # Feedback collection & processing
│ ├── api_keys.py # API key management
│ ├── utils.py # Helper functions
│ ├── logger.py # Logging setup
│ ├── scheduler.py # Background tasks
│ └── train_model.py # Model training script
│
├── models/
│ └── final_model/
│ ├── model.h5 # Primary model file
│ └── metadata.json # Model metadata
│
├── data/
│ ├── uploads/ # Uploaded files
│ ├── feedback.json # User feedback data
│ ├── users.json # User accounts
│ └── ...
│
├── app/templates/ # Jinja2 templates
│ ├── static/ # CSS, JS, and assets
│ └── ...
│
├── requirements.txt # Dependencies
├── runtime.txt # Python version for deployment
├── Dockerfile # Docker configuration
├── .env.example # Example environment file
├── .gitignore # Git ignore rules
├── README.md # Documentation
└── LICENSE # License

yaml
Copy code

---

## 🚀 Installation & Setup

### 1️⃣ Clone the Repository
``bash
git clone https://github.com/Sachin-deepak-S/Safe-Vision-Hub.git
cd Safe-Vision-Hub
2️⃣ Create a Virtual Environment
bash
Copy code
python -m venv venv
source venv/bin/activate      # macOS/Linux
# Windows: venv\Scripts\activate
3️⃣ Install Dependencies
bash
Copy code
pip install -r requirements.txt
4️⃣ Configure Environment Variables
Copy .env.example → .env and fill in your values:

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
▶️ How to Run
Local Development
bash
Copy code
python app/main.py
Then visit → http://localhost:8000

Production (Gunicorn)
bash
Copy code
gunicorn -w 4 -b 0.0.0.0:8000 app.main:app
📁 Model & Weights
Default model path: models/final_model/model.h5

Secondary API-based models: DeepAI, PicPurify, Sightengine

You can also train your own model (see next section).

Add the model file path to .gitignore to prevent large uploads.

🧩 Building and Integrating Your Own Model
If you’d like to train your own NSFW detection or classification model, you can easily integrate it into this project.

Step 1 — Train a Model (Example using TensorFlow)
python
Copy code
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout
from tensorflow.keras.preprocessing.image import ImageDataGenerator

model = Sequential([
    Conv2D(32, (3,3), activation='relu', input_shape=(128,128,3)),
    MaxPooling2D(2,2),
    Conv2D(64, (3,3), activation='relu'),
    MaxPooling2D(2,2),
    Flatten(),
    Dense(128, activation='relu'),
    Dropout(0.5),
    Dense(1, activation='sigmoid')
])

model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

train_datagen = ImageDataGenerator(rescale=1./255, validation_split=0.2)
train_data = train_datagen.flow_from_directory(
    'dataset/', target_size=(128,128), batch_size=32, class_mode='binary', subset='training'
)
val_data = train_datagen.flow_from_directory(
    'dataset/', target_size=(128,128), batch_size=32, class_mode='binary', subset='validation'
)

model.fit(train_data, validation_data=val_data, epochs=10)
model.save('models/final_model/model.h5')
Step 2 — Integrate the Model
In app/model_utils.py:

python
Copy code
from tensorflow.keras.models import load_model

def load_local_model():
    model = load_model("models/final_model/model.h5")
    print("✅ Custom model loaded successfully.")
    return model
Step 3 — Test
bash
Copy code
python app/main.py
Upload an image in the web UI to verify your model predictions.

🧪 Usage Example
Web UI
Open the app in your browser (localhost:8000).

Upload an image or video.

View detection results (safe/unsafe classification).

CLI Example
bash
Copy code
python app/main.py --input path/to/image.jpg --output results/
(Add a screenshot or demo GIF here to show visual output)

☁️ Deployment
Hugging Face Spaces (Docker or Gradio)
Create a new Space and select Docker SDK.

Connect your GitHub repository.

Ensure the following files exist:

Dockerfile

requirements.txt

runtime.txt

Set your environment variables under Settings → Secrets.

Click Deploy and test your app live.

📖 API Documentation
FastAPI auto-generates interactive documentation:

Swagger → http://localhost:8000/docs

ReDoc → http://localhost:8000/redoc

🤝 Contributing
Contributions are always welcome!

Fork this repository

Create your feature branch

bash
Copy code
git checkout -b feature/my-feature
Commit your changes

bash
Copy code
git commit -m "Add new feature"
Push and open a pull request 🚀

📝 License
This project is licensed under the MIT License.
You are free to use, modify, and distribute it with attribution.

🎯 Roadmap
 Image upload + NSFW detection

 Admin dashboard & user management

 Feedback system & retraining

 Video detection support

 Batch image analysis

 Cloud integration (AWS, GCS)

 Mobile-friendly UI

 Real-time webcam support

🙏 Acknowledgements
DeepAI NSFW Detection API

PicPurify API

Sightengine

Hugging Face Transformers

FastAPI Framework

👤 Author
Sachin Deepak S
📧 sachindeepak4181@gmail.com
🌐 LinkedIn | GitHub

⚠️ Disclaimer & Ethical Use
This project is intended for educational and research purposes only.
The results are probabilistic and may not always be accurate.
Do not use this tool for unethical or illegal content screening.
Always follow applicable laws, data privacy regulations, and platform guidelines.

## 👤 Author
**Sachin Deepak S**  
📧 [sachindeepak4181@gmail.com](mailto:sachindeepak4181@gmail.com)  
🌐 [LinkedIn](https://www.linkedin.com/in/sachin-deepak-s/) | [GitHub](https://github.com/Sachin-deepak-S)

⚠️ Disclaimer & Ethical Use
This project is intended for educational and research purposes only.
The results are probabilistic and may not always be accurate.
Do not use this tool for unethical or illegal content screening.
Always follow applicable laws, data privacy regulations, and platform guidelines.
