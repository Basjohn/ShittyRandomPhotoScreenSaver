"""Tests for image queue."""
import pytest
from engine.image_queue import ImageQueue
from sources.base_provider import ImageMetadata, ImageSourceType


@pytest.fixture
def sample_images():
    """Create sample image metadata for testing."""
    from pathlib import Path
    images = []
    for i in range(10):
        img = ImageMetadata(
            source_type=ImageSourceType.FOLDER,
            source_id=f"/test/folder{i}",
            image_id=f"image_{i}",
            local_path=Path(f"/test/image_{i}.jpg"),
            title=f"Image {i}",
            file_size=1024 * (i + 1),
            format="JPEG"
        )
        images.append(img)
    return images


def test_image_queue_initialization():
    """Test image queue initialization."""
    queue = ImageQueue(shuffle=True, history_size=20)
    
    assert queue.shuffle_enabled is True
    assert queue.history_size == 20
    assert queue.size() == 0
    assert queue.total_images() == 0
    assert queue.is_empty() is True


def test_add_images_no_shuffle(sample_images):
    """Test adding images without shuffle."""
    queue = ImageQueue(shuffle=False)
    
    count = queue.add_images(sample_images)
    
    assert count == 10
    assert queue.total_images() == 10
    assert queue.size() == 10
    assert queue.is_empty() is False


def test_add_images_with_shuffle(sample_images):
    """Test adding images with shuffle enabled."""
    queue = ImageQueue(shuffle=True)
    
    count = queue.add_images(sample_images)
    
    assert count == 10
    assert queue.total_images() == 10
    assert queue.size() == 10
    
    # Images should be in different order (not guaranteed but extremely likely)
    first_img = queue.peek()
    # Can't guarantee shuffle order, just verify it works


def test_next_image(sample_images):
    """Test getting next image."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    # Get first image
    img = queue.next()
    
    assert img is not None
    assert img.local_path.as_posix() == "/test/image_0.jpg"
    assert queue.size() == 9  # One removed
    assert queue.current() == img


def test_next_multiple_images(sample_images):
    """Test advancing through multiple images."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    images_seen = []
    for i in range(5):
        img = queue.next()
        images_seen.append(img.local_path.as_posix())
    
    assert len(images_seen) == 5
    assert images_seen[0] == "/test/image_0.jpg"
    assert images_seen[4] == "/test/image_4.jpg"
    assert queue.size() == 5


def test_queue_wraparound(sample_images):
    """Test queue wraparound when all images consumed."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images[:3])  # Only 3 images
    
    # Consume all images
    img1 = queue.next()
    img2 = queue.next()
    img3 = queue.next()
    
    assert queue.size() == 0
    assert queue.get_wrap_count() == 0
    
    # Next should wrap around
    img4 = queue.next()
    
    assert img4 is not None
    assert queue.get_wrap_count() == 1
    assert queue.size() == 2  # 3 - 1


def test_current_image(sample_images):
    """Test getting current image without advancing."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    # No current before next() is called
    assert queue.current() is None
    
    # Get first image
    img1 = queue.next()
    
    # Current should return same image multiple times
    assert queue.current() == img1
    assert queue.current() == img1
    assert queue.size() == 9  # Size doesn't change


def test_peek_next_image(sample_images):
    """Test peeking at next image without consuming."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    # Peek at first image
    peeked = queue.peek()
    
    assert peeked is not None
    assert peeked.local_path.as_posix() == "/test/image_0.jpg"
    assert queue.size() == 10  # Size unchanged
    
    # Next should return peeked image
    next_img = queue.next()
    assert next_img == peeked


def test_history_tracking(sample_images):
    """Test image history tracking."""
    queue = ImageQueue(shuffle=False, history_size=5)
    queue.add_images(sample_images)
    
    # Advance through several images
    for i in range(3):
        queue.next()
    
    history = queue.get_history()
    
    assert len(history) == 3
    # History stores Path as string, need to normalize for comparison
    from pathlib import Path
    assert Path(history[0]).as_posix() == "/test/image_0.jpg"
    assert Path(history[2]).as_posix() == "/test/image_2.jpg"


def test_history_max_size(sample_images):
    """Test history size limit."""
    queue = ImageQueue(shuffle=False, history_size=3)
    queue.add_images(sample_images)
    
    # Advance through 5 images
    for i in range(5):
        queue.next()
    
    history = queue.get_history()
    
    # History should only contain last 3
    assert len(history) == 3
    from pathlib import Path
    assert Path(history[0]).as_posix() == "/test/image_2.jpg"
    assert Path(history[2]).as_posix() == "/test/image_4.jpg"


def test_is_in_recent_history(sample_images):
    """Test checking if image in recent history."""
    from pathlib import Path
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    # Show first 3 images
    queue.next()  # image_0
    queue.next()  # image_1
    queue.next()  # image_2
    
    # Use actual path format from platform
    img0_path = str(Path("/test/image_0.jpg"))
    img1_path = str(Path("/test/image_1.jpg"))
    img5_path = str(Path("/test/image_5.jpg"))
    
    assert queue.is_in_recent_history(img0_path, lookback=5) is True
    assert queue.is_in_recent_history(img1_path, lookback=5) is True
    assert queue.is_in_recent_history(img5_path, lookback=5) is False


def test_shuffle_method(sample_images):
    """Test manual shuffle of queue."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    # Get first image before shuffle
    first_before = queue.peek()
    
    # Shuffle
    queue.shuffle()
    
    # Queue size should be same
    assert queue.size() == 10
    
    # Order likely changed (not guaranteed but extremely likely with 10 items)
    # Just verify shuffle doesn't crash and size is maintained


def test_set_shuffle_enabled(sample_images):
    """Test changing shuffle setting."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    # Enable shuffle
    queue.set_shuffle_enabled(True)
    
    assert queue.shuffle_enabled is True
    assert queue.size() == 10


def test_clear_queue(sample_images):
    """Test clearing the queue."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    queue.next()
    queue.next()
    
    queue.clear()
    
    assert queue.size() == 0
    assert queue.total_images() == 0
    assert queue.is_empty() is True
    assert queue.current() is None
    assert len(queue.get_history()) == 0


def test_set_images_replaces_all(sample_images):
    """Test set_images replaces existing images."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images[:5])
    
    assert queue.total_images() == 5
    
    # Replace with different set
    queue.set_images(sample_images[5:])
    
    assert queue.total_images() == 5
    assert queue.size() == 5
    
    img = queue.next()
    assert img.local_path.as_posix() == "/test/image_5.jpg"


def test_remove_image(sample_images):
    """Test removing specific image from queue."""
    from pathlib import Path
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    # Remove image_5 using platform-specific path
    img5_path = str(Path("/test/image_5.jpg"))
    removed = queue.remove_image(img5_path)
    
    assert removed is True
    assert queue.total_images() == 9
    assert queue.size() == 9


def test_remove_nonexistent_image(sample_images):
    """Test removing image that doesn't exist."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    removed = queue.remove_image("/test/nonexistent.jpg")
    
    assert removed is False
    assert queue.total_images() == 10


def test_get_stats(sample_images):
    """Test getting queue statistics."""
    queue = ImageQueue(shuffle=True, history_size=20)
    queue.add_images(sample_images)
    
    queue.next()
    queue.next()
    
    stats = queue.get_stats()
    
    assert stats['total_images'] == 10
    assert stats['remaining'] == 8
    assert stats['current_index'] == 1
    assert stats['wrap_count'] == 0
    assert stats['history_size'] == 2
    assert stats['shuffle_enabled'] is True
    # Current image path should exist (order may vary with shuffle)
    assert stats['current_image'] is not None


def test_empty_queue_behavior():
    """Test behavior with empty queue."""
    queue = ImageQueue()
    
    # Next on empty queue
    img = queue.next()
    assert img is None
    
    # Peek on empty queue
    peeked = queue.peek()
    assert peeked is None
    
    # Current on empty queue
    current = queue.current()
    assert current is None


def test_queue_len_and_bool(sample_images):
    """Test __len__ and __bool__ methods."""
    queue = ImageQueue(shuffle=False)
    
    assert len(queue) == 0
    assert bool(queue) is False
    
    queue.add_images(sample_images)
    
    assert len(queue) == 10
    assert bool(queue) is True
    
    # Consume one
    queue.next()
    assert len(queue) == 9


def test_queue_repr(sample_images):
    """Test string representation."""
    queue = ImageQueue(shuffle=True)
    queue.add_images(sample_images[:3])
    
    repr_str = repr(queue)
    
    assert "ImageQueue" in repr_str
    assert "total=3" in repr_str
    assert "shuffle=True" in repr_str


def test_previous_image(sample_images):
    """Test going back to previous image."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    # Move forward
    img1 = queue.next()  # image_0
    img2 = queue.next()  # image_1
    
    # Go back
    prev = queue.previous()
    
    assert prev is not None
    assert prev.local_path.as_posix() == "/test/image_0.jpg"


def test_previous_with_no_history(sample_images):
    """Test previous() when no history exists."""
    queue = ImageQueue(shuffle=False)
    queue.add_images(sample_images)
    
    # Call previous without calling next first
    prev = queue.previous()
    
    # Should return None or current (which is None)
    assert prev is None


def test_wraparound_preserves_shuffle():
    """Test that wraparound respects shuffle setting."""
    from pathlib import Path
    queue = ImageQueue(shuffle=False)
    
    images = []
    for i in range(3):
        img = ImageMetadata(
            source_type=ImageSourceType.FOLDER,
            source_id="/test",
            image_id=f"img{i}",
            local_path=Path(f"/test/img{i}.jpg"),
            title=f"Image {i}",
            file_size=1024,
            format="JPEG"
        )
        images.append(img)
    
    queue.add_images(images)
    
    # Consume all
    first_round = []
    for _ in range(3):
        img = queue.next()
        first_round.append(img.local_path.as_posix())
    
    # Wrap around
    second_round = []
    for _ in range(3):
        img = queue.next()
        second_round.append(img.local_path.as_posix())
    
    # Without shuffle, order should be identical
    assert first_round == second_round
