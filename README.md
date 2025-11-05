# NSFW AI Hub

NSFW classification hub (CPU, JSON-backed) with web interface and API.

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd nsfw_ai_hub
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Copy `.env.example` to `.env` and fill in your values:
   ```bash
   cp .env.example .env
   ```

   **Required environment variables:**
   - `JWT_SECRET`: Secret key for JWT tokens
   - `ADMIN_EMAIL`: Admin email address
   - `GMAIL_USER`: Gmail address for sending reports
   - `GMAIL_APP_PASS`: Gmail app password

   **Optional API keys:**
   - `DEEPAI_API_KEY`: DeepAI API key for secondary model
   - `PICPURIFY_API_KEY`: PicPurify API key for secondary model
   - `SIGHTENGINE_API_KEY`: Sightengine API key for secondary model

5. **Add your primary model**

   Put your primary NSFW detection model under `models/final_model/` (Hugging Face format).

## Running

**Development:**
```bash
python app/main.py
```

**Production (with Gunicorn):**
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app.main:app
```

## Deployment

- **Hugging Face Spaces**: Use the provided deployment scripts
- **Docker**: Build and run using the Dockerfile
- **Local**: Follow the setup instructions above

## Security Notes

- Never commit `.env` file or any sensitive data to version control
- All sensitive configuration is loaded from environment variables
- The `.gitignore` file excludes sensitive files and directories

## Features

- Web interface for NSFW image/video classification
- REST API for programmatic access
- User management and authentication
- Admin dashboard with analytics
- Secondary model rotation for validation
- Feedback collection and model retraining
