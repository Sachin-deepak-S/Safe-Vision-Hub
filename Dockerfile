# ============================================================
# Stage 1 — Base image with system dependencies
# ============================================================
FROM python:3.10-slim AS base

# Set working directory
WORKDIR /home/user

# Copy requirements first for caching
COPY requirements.txt .

# Install system packages and build tools (for pycairo, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    libcairo2-dev \
    pkg-config \
    libffi-dev \
    python3-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libxrender1 \
    curl \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Rust extension removed - no longer needed

# Upgrade pip and install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the project files into the container
COPY . .

# Rust extension removed - no longer needed

# Create necessary directories and fix permissions
RUN mkdir -p app/data app/data/uploads app/models app/models/priority_feedback app/data/reports app/logs && \
    chown -R 1000:1000 /home/user/app

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    UVICORN_PORT=7860 \
    PYTHONPATH=/home/user

# Expose Hugging Face’s default port
EXPOSE 7860

# ============================================================
# Stage 2 — Run the application
# ============================================================

CMD ["sh", "-c", "PYTHONPATH=/home/user uvicorn main:app --host 0.0.0.0 --port 7860"]
