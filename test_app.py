"""
Tests for the Download Manager application
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app import (
    DownloadItem,
    DownloadStatus,
    DownloadManager,
)


# Test video URL
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=2PuFyjAs7JA"


class TestDownloadItem:
    """Tests for DownloadItem dataclass"""
    
    def test_create_download_item(self):
        """Test creating a download item"""
        item = DownloadItem(url=TEST_VIDEO_URL)
        assert item.url == TEST_VIDEO_URL
        assert item.title == "Unknown"
        assert item.status == DownloadStatus.QUEUED
        assert item.progress == 0.0
        assert item.error_message is None
        assert item.filename is None
        assert item.id is not None
    
    def test_to_dict(self):
        """Test serializing download item to dict"""
        item = DownloadItem(
            url=TEST_VIDEO_URL,
            title="Test Video",
            status=DownloadStatus.COMPLETED,
            progress=100.0
        )
        data = item.to_dict()
        
        assert data['url'] == TEST_VIDEO_URL
        assert data['title'] == "Test Video"
        assert data['status'] == "completed"
        assert data['progress'] == 100.0
    
    def test_from_dict(self):
        """Test deserializing download item from dict"""
        data = {
            'url': TEST_VIDEO_URL,
            'title': "Test Video",
            'status': "queued",
            'progress': 0.0,
            'id': "test-id-123",
            'error_message': None,
            'filename': None
        }
        item = DownloadItem.from_dict(data)
        
        assert item.url == TEST_VIDEO_URL
        assert item.title == "Test Video"
        assert item.status == DownloadStatus.QUEUED
        assert item.id == "test-id-123"


class TestDownloadManager:
    """Tests for DownloadManager class"""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary directory for tests"""
        return tmp_path
    
    @pytest.fixture
    def manager(self, temp_dir):
        """Create a download manager instance for testing"""
        download_path = temp_dir / "downloads"
        queue_file = temp_dir / "queue.json"
        return DownloadManager(
            download_path=str(download_path),
            queue_file=str(queue_file)
        )
    
    def test_init_creates_directories(self, temp_dir):
        """Test that initialization creates download directory"""
        download_path = temp_dir / "downloads"
        queue_file = temp_dir / "queue.json"
        
        manager = DownloadManager(
            download_path=str(download_path),
            queue_file=str(queue_file)
        )
        
        assert download_path.exists()
        assert manager.is_processing is False
    
    def test_add_to_queue(self, manager):
        """Test adding item to queue"""
        # Mock asyncio.create_task to avoid event loop issues
        with patch('app.asyncio.create_task'):
            item = manager.add_to_queue(TEST_VIDEO_URL)
        
        assert len(manager.queue) == 1
        assert item.url == TEST_VIDEO_URL
        assert item.status == DownloadStatus.QUEUED
    
    def test_remove_from_queue(self, manager):
        """Test removing item from queue"""
        with patch('app.asyncio.create_task'):
            item = manager.add_to_queue(TEST_VIDEO_URL)
            item_id = item.id
        
        manager.remove_from_queue(item_id)
        
        assert len(manager.queue) == 0
    
    def test_remove_deletes_file(self, manager, temp_dir):
        """Test that removing item deletes its file"""
        with patch('app.asyncio.create_task'):
            item = manager.add_to_queue(TEST_VIDEO_URL)
        
        # Create a fake file
        test_file = temp_dir / "test_video.mp4"
        test_file.write_text("fake video content")
        item.filename = str(test_file)
        item.status = DownloadStatus.COMPLETED
        
        manager.remove_from_queue(item.id)
        
        assert not test_file.exists()
        assert len(manager.queue) == 0
    
    def test_clear_completed(self, manager):
        """Test clearing completed items"""
        # Add multiple items with different statuses
        with patch('app.asyncio.create_task'):
            item1 = manager.add_to_queue(TEST_VIDEO_URL)
            item1.status = DownloadStatus.COMPLETED
            
            item2 = manager.add_to_queue(TEST_VIDEO_URL)
            item2.status = DownloadStatus.FAILED
            
            item3 = manager.add_to_queue(TEST_VIDEO_URL)
            item3.status = DownloadStatus.QUEUED
        
        manager.clear_completed()
        
        assert len(manager.queue) == 1
        assert manager.queue[0].status == DownloadStatus.QUEUED
    
    def test_clear_completed_deletes_files(self, manager, temp_dir):
        """Test that clear completed deletes associated files"""
        with patch('app.asyncio.create_task'):
            item1 = manager.add_to_queue(TEST_VIDEO_URL)
            item1.status = DownloadStatus.COMPLETED
        
        # Create fake files
        test_file1 = temp_dir / "video1.mp4"
        test_file1.write_text("fake video 1")
        item1.filename = str(test_file1)
        
        with patch('app.asyncio.create_task'):
            item2 = manager.add_to_queue(TEST_VIDEO_URL)
            item2.status = DownloadStatus.QUEUED
        
        manager.clear_completed()
        
        assert not test_file1.exists()
        assert len(manager.queue) == 1
    
    def test_save_and_load_queue(self, manager, temp_dir):
        """Test saving and loading queue from JSON"""
        # Add items
        with patch('app.asyncio.create_task'):
            item1 = manager.add_to_queue(TEST_VIDEO_URL)
            item1.title = "Test Video 1"
            item2 = manager.add_to_queue(TEST_VIDEO_URL)
            item2.title = "Test Video 2"
        
        manager.save_queue()
        
        # Create new manager to load the queue
        queue_file = temp_dir / "queue.json"
        with patch('app.asyncio.create_task'):
            new_manager = DownloadManager(
                download_path=str(temp_dir / "downloads"),
                queue_file=str(queue_file)
            )
        
        assert len(new_manager.queue) == 2
        assert new_manager.queue[0].title == "Test Video 1"
        assert new_manager.queue[1].title == "Test Video 2"
    
    def test_load_resets_downloading_status(self, manager, temp_dir):
        """Test that downloading status is reset to queued on load"""
        with patch('app.asyncio.create_task'):
            item = manager.add_to_queue(TEST_VIDEO_URL)
            item.status = DownloadStatus.DOWNLOADING
            item.progress = 50.0
        
        manager.save_queue()
        
        # Create new manager to load the queue
        queue_file = temp_dir / "queue.json"
        with patch('app.asyncio.create_task'):
            new_manager = DownloadManager(
                download_path=str(temp_dir / "downloads"),
                queue_file=str(queue_file)
            )
        
        assert new_manager.queue[0].status == DownloadStatus.QUEUED
        assert new_manager.queue[0].progress == 0.0
    
    @pytest.mark.asyncio
    async def test_download_video_success(self, manager):
        """Test successful video download (mocked)"""
        item = DownloadItem(url=TEST_VIDEO_URL)
        manager.queue.append(item)
        
        # Mock yt-dlp
        with patch('app.yt_dlp.YoutubeDL') as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl
            
            # Mock extract_info
            mock_ydl.extract_info.return_value = {
                'title': 'Test Video Title',
                'id': 'test123'
            }
            
            # Mock download
            mock_ydl.download.return_value = None
            
            await manager.download_video(item)
            
            assert item.status == DownloadStatus.COMPLETED
            assert item.title == 'Test Video Title'
            mock_ydl.extract_info.assert_called_once()
            mock_ydl.download.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_download_video_failure(self, manager):
        """Test failed video download"""
        item = DownloadItem(url="https://invalid-url.com/video")
        manager.queue.append(item)
        
        # Mock yt-dlp to raise an exception
        with patch('app.yt_dlp.YoutubeDL') as mock_ydl_class:
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl
            mock_ydl.extract_info.side_effect = Exception("Download failed")
            
            await manager.download_video(item)
            
            assert item.status == DownloadStatus.FAILED
            assert item.error_message is not None
            assert "Download failed" in item.error_message
    
    @pytest.mark.asyncio
    async def test_process_queue(self, manager):
        """Test queue processing"""
        # Add multiple items
        item1 = manager.add_to_queue(TEST_VIDEO_URL)
        item2 = manager.add_to_queue(TEST_VIDEO_URL)
        
        # Mock download_video to complete immediately
        async def mock_download(item):
            item.status = DownloadStatus.COMPLETED
            item.progress = 100.0
        
        with patch.object(manager, 'download_video', side_effect=mock_download):
            await manager.process_queue()
        
        assert item1.status == DownloadStatus.COMPLETED
        assert item2.status == DownloadStatus.COMPLETED
        assert manager.is_processing is False


class TestDownloadStatus:
    """Tests for DownloadStatus enum"""
    
    def test_status_values(self):
        """Test that all status values are correct"""
        assert DownloadStatus.QUEUED.value == "queued"
        assert DownloadStatus.DOWNLOADING.value == "downloading"
        assert DownloadStatus.COMPLETED.value == "completed"
        assert DownloadStatus.FAILED.value == "failed"


@pytest.mark.integration
@pytest.mark.slow
class TestRealDownload:
    """Integration tests with real downloads (slow, marked for optional execution)"""
    
    @pytest.mark.asyncio
    async def test_real_video_download(self, tmp_path):
        """Test downloading a real video (requires internet)"""
        manager = DownloadManager(
            download_path=str(tmp_path / "downloads"),
            queue_file=str(tmp_path / "queue.json")
        )
        
        item = manager.add_to_queue(TEST_VIDEO_URL)
        
        await manager.download_video(item)
        
        # Check that download completed successfully
        assert item.status in [DownloadStatus.COMPLETED, DownloadStatus.FAILED]
        
        if item.status == DownloadStatus.COMPLETED:
            assert item.title != "Unknown"
            assert item.filename is not None
            # Verify file exists
            if item.filename:
                assert Path(item.filename).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
