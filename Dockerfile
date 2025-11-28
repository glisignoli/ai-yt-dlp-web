# Use Python 3.14 slim image as base
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies required by yt-dlp
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY app.py ./
COPY main.py ./

# Install Python dependencies
RUN pip install --no-cache-dir .

# Create downloads directory
RUN mkdir -p /app/downloads

# Expose the port the app runs on
EXPOSE 8080

# Set environment variables for NiceGUI
ENV NICEGUI_STORAGE_PATH=/app/.nicegui

# Run the application
CMD ["python", "app.py"]
