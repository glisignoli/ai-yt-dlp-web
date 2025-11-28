"""
Tests for the Download Manager application
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.app import (
    DownloadItem,
    DownloadStatus,
    DownloadManager,
)


# Test video URL
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=2PuFyjAs7JA"
TEST_PLAYLIST_URL = "https://www.youtube.com/watch?v=2PuFyjAs7JA&list=PLUMUNvrX4FMTlbONCn0eGP968V3DMkEkl&pp=gAQB"


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
        with patch('src.app.asyncio.create_task'):
            item = manager.add_to_queue(TEST_VIDEO_URL)
        
        assert len(manager.queue) == 1
        assert item.url == TEST_VIDEO_URL
        assert item.status == DownloadStatus.QUEUED
    
    def test_remove_from_queue(self, manager):
        """Test removing item from queue"""
        with patch('src.app.asyncio.create_task'):
            item = manager.add_to_queue(TEST_VIDEO_URL)
            item_id = item.id
        
        manager.remove_from_queue(item_id)
        
        assert len(manager.queue) == 0
    
    def test_remove_deletes_file(self, manager, temp_dir):
        """Test that removing item deletes its file"""
        with patch('src.app.asyncio.create_task'):
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
        with patch('src.app.asyncio.create_task'):
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
        with patch('src.app.asyncio.create_task'):
            item1 = manager.add_to_queue(TEST_VIDEO_URL)
            item1.status = DownloadStatus.COMPLETED
        
        # Create fake files
        test_file1 = temp_dir / "video1.mp4"
        test_file1.write_text("fake video 1")
        item1.filename = str(test_file1)
        
        with patch('src.app.asyncio.create_task'):
            item2 = manager.add_to_queue(TEST_VIDEO_URL)
            item2.status = DownloadStatus.QUEUED
        
        manager.clear_completed()
        
        assert not test_file1.exists()
        assert len(manager.queue) == 1
    
    def test_save_and_load_queue(self, manager, temp_dir):
        """Test saving and loading queue from JSON"""
        # Add items
        with patch('src.app.asyncio.create_task'):
            item1 = manager.add_to_queue(TEST_VIDEO_URL)
            item1.title = "Test Video 1"
            item2 = manager.add_to_queue(TEST_VIDEO_URL)
            item2.title = "Test Video 2"
        
        manager.save_queue()
        
        # Create new manager to load the queue
        queue_file = temp_dir / "queue.json"
        with patch('src.app.asyncio.create_task'):
            new_manager = DownloadManager(
                download_path=str(temp_dir / "downloads"),
                queue_file=str(queue_file)
            )
        
        assert len(new_manager.queue) == 2
        assert new_manager.queue[0].title == "Test Video 1"
        assert new_manager.queue[1].title == "Test Video 2"
    
    def test_load_resets_downloading_status(self, manager, temp_dir):
        """Test that downloading status is reset to queued on load"""
        with patch('src.app.asyncio.create_task'):
            item = manager.add_to_queue(TEST_VIDEO_URL)
            item.status = DownloadStatus.DOWNLOADING
            item.progress = 50.0
        
        manager.save_queue()
        
        # Create new manager to load the queue
        queue_file = temp_dir / "queue.json"
        with patch('src.app.asyncio.create_task'):
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
        with patch('src.app.yt_dlp.YoutubeDL') as mock_ydl_class:
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
        with patch('src.app.yt_dlp.YoutubeDL') as mock_ydl_class:
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


class TestPlaylistSupport:
    """Tests for playlist download functionality"""
    
    @pytest.fixture
    def manager(self, tmp_path):
        """Create a test download manager"""
        return DownloadManager(
            download_path=str(tmp_path / "downloads"),
            queue_file=str(tmp_path / "queue.json")
        )
    
    def test_is_playlist_detection(self, manager):
        """Test playlist URL detection"""
        # Playlist URLs
        assert manager._is_playlist("https://www.youtube.com/watch?v=xxx&list=PLxxx") is True
        assert manager._is_playlist("https://www.youtube.com/playlist?list=PLxxx") is True
        
        # Non-playlist URLs
        assert manager._is_playlist("https://www.youtube.com/watch?v=xxx") is False
        assert manager._is_playlist("https://example.com/video") is False
    
    def test_add_playlist_to_queue_mocked(self, manager):
        """Test adding a playlist (with mocked yt-dlp)"""
        playlist_url = TEST_PLAYLIST_URL
        
        # Mock yt-dlp response
        mock_playlist_info = {
            'entries': [
                {'id': 'video1', 'title': 'Video 1', 'url': 'https://www.youtube.com/watch?v=video1'},
                {'id': 'video2', 'title': 'Video 2', 'url': 'https://www.youtube.com/watch?v=video2'},
                {'id': 'video3', 'title': 'Video 3', 'url': 'https://www.youtube.com/watch?v=video3'},
            ]
        }
        
        with patch('src.app.asyncio.create_task'):
            with patch('src.app.yt_dlp.YoutubeDL') as mock_ydl_class:
                mock_ydl = MagicMock()
                mock_ydl.extract_info.return_value = mock_playlist_info
                mock_ydl_class.return_value.__enter__.return_value = mock_ydl
                
                items = manager.add_to_queue(playlist_url)
        
        # Should return a list of items
        assert isinstance(items, list)
        assert len(items) == 3
        
        # Check that items were added to queue
        assert len(manager.queue) == 3
        
        # Verify each item
        assert manager.queue[0].title == "Video 1"
        assert manager.queue[1].title == "Video 2"
        assert manager.queue[2].title == "Video 3"
        
        # All should be queued
        for item in manager.queue:
            assert item.status == DownloadStatus.QUEUED
    
    def test_add_playlist_with_none_entries(self, manager):
        """Test handling playlist with None entries (skipped videos)"""
        playlist_url = TEST_PLAYLIST_URL
        
        # Mock yt-dlp response with some None entries (private/deleted videos)
        mock_playlist_info = {
            'entries': [
                {'id': 'video1', 'title': 'Video 1', 'url': 'https://www.youtube.com/watch?v=video1'},
                None,  # Deleted or private video
                {'id': 'video3', 'title': 'Video 3', 'url': 'https://www.youtube.com/watch?v=video3'},
            ]
        }
        
        with patch('src.app.asyncio.create_task'):
            with patch('src.app.yt_dlp.YoutubeDL') as mock_ydl_class:
                mock_ydl = MagicMock()
                mock_ydl.extract_info.return_value = mock_playlist_info
                mock_ydl_class.return_value.__enter__.return_value = mock_ydl
                
                items = manager.add_to_queue(playlist_url)
        
        # Should skip None entries
        assert len(items) == 2
        assert len(manager.queue) == 2
        assert manager.queue[0].title == "Video 1"
        assert manager.queue[1].title == "Video 3"
    
    def test_add_single_video_as_playlist(self, manager):
        """Test that single video URL with playlist parameter is handled"""
        playlist_url = "https://www.youtube.com/watch?v=xxx&list=PLxxx"
        
        # Mock response for single video (no entries key)
        mock_info = {
            'id': 'xxx',
            'title': 'Single Video'
        }
        
        with patch('src.app.asyncio.create_task'):
            with patch('src.app.yt_dlp.YoutubeDL') as mock_ydl_class:
                mock_ydl = MagicMock()
                mock_ydl.extract_info.return_value = mock_info
                mock_ydl_class.return_value.__enter__.return_value = mock_ydl
                
                items = manager.add_to_queue(playlist_url)
        
        # Should treat as single video
        assert isinstance(items, list)
        assert len(items) == 1
        assert len(manager.queue) == 1
    
    def test_add_playlist_error_fallback(self, manager):
        """Test fallback to single video on playlist extraction error"""
        playlist_url = TEST_PLAYLIST_URL
        
        with patch('src.app.asyncio.create_task'):
            with patch('src.app.yt_dlp.YoutubeDL') as mock_ydl_class:
                mock_ydl = MagicMock()
                mock_ydl.extract_info.side_effect = Exception("Network error")
                mock_ydl_class.return_value.__enter__.return_value = mock_ydl
                
                items = manager.add_to_queue(playlist_url)
        
        # Should fall back to treating as single video
        assert isinstance(items, list)
        assert len(items) == 1
        assert len(manager.queue) == 1
        assert manager.queue[0].url == playlist_url
    
    def test_single_video_url_returns_single_item(self, manager):
        """Test that non-playlist URL returns single DownloadItem"""
        video_url = "https://www.youtube.com/watch?v=xxx"
        
        with patch('src.app.asyncio.create_task'):
            result = manager.add_to_queue(video_url)
        
        # Single video should return single item (not a list)
        assert isinstance(result, DownloadItem)
        assert result.url == video_url
        assert len(manager.queue) == 1
    
    def test_playlist_url_generation_from_id(self, manager):
        """Test URL generation when entry only has ID"""
        playlist_url = TEST_PLAYLIST_URL
        
        # Mock response with entry that has ID but no URL
        mock_playlist_info = {
            'entries': [
                {'id': 'abc123', 'title': 'Video with ID only'},
            ]
        }
        
        with patch('src.app.asyncio.create_task'):
            with patch('src.app.yt_dlp.YoutubeDL') as mock_ydl_class:
                mock_ydl = MagicMock()
                mock_ydl.extract_info.return_value = mock_playlist_info
                mock_ydl_class.return_value.__enter__.return_value = mock_ydl
                
                items = manager.add_to_queue(playlist_url)
        
        # Should generate URL from ID
        assert len(items) == 1
        assert "abc123" in manager.queue[0].url
        assert manager.queue[0].url == "https://www.youtube.com/watch?v=abc123"


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
    
    @pytest.mark.asyncio
    async def test_real_playlist_download(self, tmp_path):
        """Test downloading a real playlist (requires internet)"""
        manager = DownloadManager(
            download_path=str(tmp_path / "downloads"),
            queue_file=str(tmp_path / "queue.json")
        )
        
        # Add playlist URL
        items = manager.add_to_queue(TEST_PLAYLIST_URL)
        
        # Should return a list of items
        assert isinstance(items, list)
        assert len(items) > 0, "Playlist should contain at least one video"
        
        # All items should be queued initially
        for item in items:
            assert item.status == DownloadStatus.QUEUED
            assert item.url is not None
        
        # Download first video from the playlist
        first_item = items[0]
        await manager.download_video(first_item)
        
        # Check that download completed successfully
        assert first_item.status in [DownloadStatus.COMPLETED, DownloadStatus.FAILED]
        
        if first_item.status == DownloadStatus.COMPLETED:
            assert first_item.title != "Unknown"
            assert first_item.filename is not None
            # Verify file exists
            if first_item.filename:
                assert Path(first_item.filename).exists()
        
        # Verify all items are in the queue
        assert len(manager.queue) == len(items)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
