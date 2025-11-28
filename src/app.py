#!/usr/bin/env python3
"""
Download Manager - A web interface for managing video downloads using yt-dlp
"""
import asyncio
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
import yt_dlp
from nicegui import ui, app
from fastapi.responses import FileResponse


class DownloadStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DownloadItem:
    url: str
    title: str = "Unknown"
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0
    id: str = field(default_factory=lambda: datetime.now().isoformat())
    error_message: Optional[str] = None
    filename: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DownloadItem':
        """Create DownloadItem from dictionary"""
        data = data.copy()
        data['status'] = DownloadStatus(data['status'])
        return cls(**data)


class DownloadManager:
    def __init__(self, download_path: str = "./downloads", queue_file: str = "queue.json"):
        self.queue: list[DownloadItem] = []
        self.download_path = Path(download_path)
        self.download_path.mkdir(exist_ok=True)
        self.queue_file = Path(queue_file)
        self.is_processing = False
        self._process_task: Optional[asyncio.Task] = None
        self.load_queue()

    def save_queue(self):
        """Save the queue to a JSON file"""
        try:
            data = [item.to_dict() for item in self.queue]
            with open(self.queue_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving queue: {e}")
    
    def load_queue(self):
        """Load the queue from a JSON file"""
        if not self.queue_file.exists():
            return
        
        try:
            with open(self.queue_file, 'r') as f:
                data = json.load(f)
            
            self.queue = [DownloadItem.from_dict(item) for item in data]
            
            # Reset downloading status to queued on restart
            for item in self.queue:
                if item.status == DownloadStatus.DOWNLOADING:
                    item.status = DownloadStatus.QUEUED
                    item.progress = 0.0
            
            # Start processing if there are queued items
            if any(item.status == DownloadStatus.QUEUED for item in self.queue):
                asyncio.create_task(self.process_queue())
        except Exception as e:
            print(f"Error loading queue: {e}")
            self.queue = []
    
    def add_to_queue(self, url: str) -> DownloadItem:
        """Add a URL to the download queue"""
        item = DownloadItem(url=url)
        self.queue.append(item)
        self.save_queue()
        
        # Start processing if not already running
        if not self.is_processing:
            self._process_task = asyncio.create_task(self.process_queue())
        
        return item

    def remove_from_queue(self, item_id: str):
        """Remove an item from the queue and delete its file"""
        # Find the item to get its filename before removing
        item = next((i for i in self.queue if i.id == item_id), None)
        
        if item and item.filename:
            # Delete the file from disk
            try:
                file_path = Path(item.filename)
                if file_path.exists():
                    file_path.unlink()
                    print(f"Deleted file: {file_path}")
            except Exception as e:
                print(f"Error deleting file: {e}")
        
        self.queue = [item for item in self.queue if item.id != item_id]
        self.save_queue()

    def clear_completed(self):
        """Clear all completed and failed downloads from the queue and delete their files"""
        # Delete files for completed/failed items
        for item in self.queue:
            if item.status in [DownloadStatus.COMPLETED, DownloadStatus.FAILED] and item.filename:
                try:
                    file_path = Path(item.filename)
                    if file_path.exists():
                        file_path.unlink()
                        print(f"Deleted file: {file_path}")
                except Exception as e:
                    print(f"Error deleting file: {e}")
        
        self.queue = [
            item for item in self.queue 
            if item.status not in [DownloadStatus.COMPLETED, DownloadStatus.FAILED]
        ]
        self.save_queue()

    async def process_queue(self):
        """Process downloads in the queue"""
        self.is_processing = True
        
        while True:
            # Find next queued item
            next_item = next(
                (item for item in self.queue if item.status == DownloadStatus.QUEUED),
                None
            )
            
            if not next_item:
                # No more items to process
                self.is_processing = False
                break
            
            # Download the item
            await self.download_video(next_item)
            await asyncio.sleep(0.5)  # Small delay between downloads

    async def download_video(self, item: DownloadItem):
        """Download a single video"""
        item.status = DownloadStatus.DOWNLOADING
        item.progress = 0.0

        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    if 'total_bytes' in d:
                        item.progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    elif 'total_bytes_estimate' in d:
                        item.progress = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                except Exception:
                    pass
            elif d['status'] == 'finished':
                item.progress = 100.0
                item.filename = d.get('filename', '')

        ydl_opts = {
            'format': 'best',
            'outtmpl': str(self.download_path / '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            # Run yt-dlp in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._download_with_ytdlp(item, ydl_opts)
            )
            item.status = DownloadStatus.COMPLETED
        except Exception as e:
            item.status = DownloadStatus.FAILED
            item.error_message = str(e)
        finally:
            self.save_queue()

    def _download_with_ytdlp(self, item: DownloadItem, ydl_opts):
        """Execute yt-dlp download (runs in thread pool)"""
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to get title
            info = ydl.extract_info(item.url, download=False)
            title = info.get('title', 'Unknown') if info else 'Unknown'
            item.title = title if title else 'Unknown'
            
            # Now download
            ydl.download([item.url])


# Global download manager instance
download_manager = DownloadManager()


# Add download endpoint
@app.get('/download/{item_id}')
async def download_file(item_id: str):
    """Endpoint to download a completed video file"""
    item = next((i for i in download_manager.queue if i.id == item_id), None)
    
    if not item:
        return {"error": "Item not found"}
    
    if item.status != DownloadStatus.COMPLETED or not item.filename:
        return {"error": "File not available for download"}
    
    file_path = Path(item.filename)
    if not file_path.exists():
        return {"error": "File not found on disk"}
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type='application/octet-stream'
    )


def create_download_item_card(item: DownloadItem, container):
    """Create a card UI element for a download item"""
    
    # Determine status color
    status_colors = {
        DownloadStatus.QUEUED: "grey",
        DownloadStatus.DOWNLOADING: "blue",
        DownloadStatus.COMPLETED: "green",
        DownloadStatus.FAILED: "red",
    }
    
    with ui.card().classes('w-full'):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.column().classes('flex-grow'):
                ui.label(item.title).classes('text-lg font-bold')
                ui.label(item.url).classes('text-sm text-gray-600')
                
                # Status and progress
                with ui.row().classes('items-center gap-2'):
                    ui.badge(
                        item.status.value.upper(),
                        color=status_colors[item.status]
                    )
                    
                    if item.status == DownloadStatus.DOWNLOADING:
                        ui.linear_progress(
                            value=item.progress / 100,
                            show_value=True
                        ).props('instant-feedback').classes('w-48')
                    elif item.status == DownloadStatus.FAILED and item.error_message:
                        ui.label(f'Error: {item.error_message}').classes('text-red-600 text-sm')
            
            # Action buttons
            with ui.row().classes('gap-2'):
                # Download button (only for completed items)
                if item.status == DownloadStatus.COMPLETED and item.filename:
                    ui.button(
                        icon='download',
                        on_click=lambda item_id=item.id: ui.download(f'/download/{item_id}')
                    ).props('flat round color=green').tooltip('Download to computer')
                
                # Remove button (only for queued, completed, or failed items)
                if item.status != DownloadStatus.DOWNLOADING:
                    ui.button(
                        icon='delete',
                        on_click=lambda: handle_remove(item.id, container)
                    ).props('flat round color=red').tooltip('Remove from queue')


def handle_remove(item_id: str, container):
    """Handle removing an item from the queue"""
    download_manager.remove_from_queue(item_id)
    update_queue_display(container)


def update_queue_display(container):
    """Update the queue display"""
    container.clear()
    
    if not download_manager.queue:
        with container:
            ui.label('No downloads in queue').classes('text-gray-500 text-center p-8')
    else:
        with container:
            for item in download_manager.queue:
                create_download_item_card(item, container)


@ui.page('/')
async def main_page():
    """Main page with download manager UI"""
    
    # Auto-refresh the queue display
    queue_container = ui.column().classes('w-full gap-4')
    
    async def refresh_display():
        """Periodically refresh the display"""
        while True:
            update_queue_display(queue_container)
            await asyncio.sleep(1)
    
    # Start refresh task
    ui.timer(1.0, lambda: update_queue_display(queue_container))
    
    with ui.column().classes('w-full max-w-4xl mx-auto p-8 gap-6'):
        # Header
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Video Download Manager').classes('text-3xl font-bold')
            ui.button(
                'Clear Completed',
                on_click=lambda: (
                    download_manager.clear_completed(),
                    update_queue_display(queue_container)
                )
            ).props('outline color=red')
        
        ui.separator()
        
        # Add URL input
        with ui.card().classes('w-full'):
            ui.label('Add Video to Queue').classes('text-xl font-bold mb-4')
            
            with ui.row().classes('w-full gap-4'):
                url_input = ui.input(
                    label='Video URL',
                    placeholder='https://www.youtube.com/watch?v=...'
                ).classes('flex-grow').props('outlined')
                
                async def add_url():
                    url = url_input.value.strip()
                    if url:
                        download_manager.add_to_queue(url)
                        url_input.value = ''
                        update_queue_display(queue_container)
                        ui.notify('Added to queue', type='positive')
                    else:
                        ui.notify('Please enter a URL', type='negative')
                
                ui.button(
                    'Add to Queue',
                    on_click=add_url,
                    icon='add'
                ).props('color=primary')
        
        ui.separator()
        
        # Queue display
        ui.label('Download Queue').classes('text-2xl font-bold')
        queue_container
        
        # Initial display
        update_queue_display(queue_container)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title='Download Manager',
        port=8080,
        reload=False,
        show=True
    )
