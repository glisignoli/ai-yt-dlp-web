# AI YT-DLP Web

A web-based video download manager built with NiceGUI and yt-dlp.

## Features

- Add videos to a download queue via URL
- Real-time download progress tracking
- Download status indicators (Queued, Downloading, Completed, Failed)
- Remove individual downloads or clear all completed ones
- Clean and modern UI

## Installation

This project uses `uv` for package management. Make sure you have `uv` installed.

## Running the Application

```bash
cd ai-yt-dlp-web
uv run app.py
```

The application will start on http://localhost:8080

## Running Tests

```bash
# Run all tests
uv run pytest test_app.py -v

# Run tests excluding slow integration tests
uv run pytest test_app.py -v -m "not slow"

# Run with coverage
uv run pytest test_app.py --cov=app --cov-report=html
```

## Usage

1. Paste a video URL (YouTube, etc.) into the input field
2. Click "Add to Queue" to start the download
3. Monitor download progress in real-time
4. Use "Clear Completed" to remove finished downloads from the queue
5. Downloads are saved to the `./downloads` directory

## Requirements

- Python 3.10+
- nicegui
- yt-dlp
