# Dockerfile for YouTube Shorts Video Engine
# Base image with Python 3.11 and FFmpeg pre-installed
FROM python:3.11-slim

# Install system dependencies (FFmpeg is required by MoviePy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-montserrat \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download Whisper tiny model into container cache (so it runs offline instantly)
RUN python -c "import whisper; whisper.load_model('tiny')"

# Copy application source
COPY . .

# Default command: run the orchestrator batch generation
CMD ["python", "-m", "engine.orchestrator"]
