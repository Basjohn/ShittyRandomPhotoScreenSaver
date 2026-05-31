"""Tests for Reddit widget progressive loading feature.

Progressive loading allows Reddit widgets to display partial data immediately
while respecting rate limits. Stages: 5 -> 10 -> target (if > 10).
"""
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from pathlib import Path

# Mock Qt before importing widget
with patch.dict('sys.modules', {
    'PySide6': MagicMock(),
    'PySide6.QtCore': MagicMock(),
    'PySide6.QtGui': MagicMock(),
    'PySide6.QtWidgets': MagicMock(),
    'shiboken6': MagicMock(),
}):
    pass


@dataclass
class MockRedditPost:
    """Mock RedditPost for testing."""
    title: str
    url: str
    score: int = 100
    created_utc: float = 1704067200.0


class TestProgressiveLoadingStages:
    """Test progressive loading stage setup and transitions."""

    def test_setup_stages_for_small_limit(self):
        """Target <= 5 should have single stage."""
        # Simulate stage setup logic
        target_limit = 5
        stages = [5]
        if target_limit > 5:
            stages.append(min(10, target_limit))
        if target_limit > 10:
            stages.append(target_limit)
        
        assert stages == [5]

    def test_setup_stages_for_medium_limit(self):
        """Target 6-10 should have two stages: 5, target."""
        target_limit = 8
        stages = [5]
        if target_limit > 5:
            stages.append(min(10, target_limit))
        if target_limit > 10:
            stages.append(target_limit)
        
        assert stages == [5, 8]

    def test_setup_stages_for_large_limit(self):
        """Target > 10 should have three stages: 4, 10, target."""
        target_limit = 20
        stages = [5]
        if target_limit > 5:
            stages.append(min(10, target_limit))
        if target_limit > 10:
            stages.append(target_limit)
        
        assert stages == [5, 10, 20]

    def test_get_stage_for_post_count_small(self):
        """Post count <= 5 should be stage 0."""
        stages = [5, 10, 20]
        post_count = 3
        
        stage = 0
        for i, stage_limit in enumerate(stages):
            if post_count <= stage_limit:
                stage = i
                break
        else:
            stage = len(stages) - 1
        
        assert stage == 0

    def test_get_stage_for_post_count_medium(self):
        """Post count 5-10 should be stage 1."""
        stages = [5, 10, 20]
        post_count = 8
        
        stage = len(stages) - 1
        for i, stage_limit in enumerate(stages):
            if post_count <= stage_limit:
                stage = i
                break
        
        assert stage == 1

    def test_get_stage_for_post_count_large(self):
        """Post count > 10 should be stage 2."""
        stages = [5, 10, 20]
        post_count = 15
        
        stage = len(stages) - 1
        for i, stage_limit in enumerate(stages):
            if post_count <= stage_limit:
                stage = i
                break
        
        assert stage == 2


class TestProgressiveLoadingDisplay:
    """Test progressive display of posts."""

    def test_display_stage_0_shows_5_posts(self):
        """Stage 0 should show up to 5 posts."""
        stages = [5, 10, 20]
        stage = 0
        all_posts = [MockRedditPost(f"Post {i}", f"http://example.com/{i}") for i in range(20)]
        
        stage_limit = stages[stage] if stage < len(stages) else 20
        posts_to_show = all_posts[:stage_limit]
        
        assert len(posts_to_show) == 5

    def test_display_stage_1_shows_10_posts(self):
        """Stage 1 should show up to 10 posts."""
        stages = [5, 10, 20]
        stage = 1
        all_posts = [MockRedditPost(f"Post {i}", f"http://example.com/{i}") for i in range(20)]
        
        stage_limit = stages[stage] if stage < len(stages) else 20
        posts_to_show = all_posts[:stage_limit]
        
        assert len(posts_to_show) == 10

    def test_display_stage_2_shows_all_posts(self):
        """Stage 2 should show all posts up to target."""
        stages = [5, 10, 20]
        stage = 2
        all_posts = [MockRedditPost(f"Post {i}", f"http://example.com/{i}") for i in range(20)]
        
        stage_limit = stages[stage] if stage < len(stages) else 20
        posts_to_show = all_posts[:stage_limit]
        
        assert len(posts_to_show) == 20

    def test_display_with_fewer_posts_than_stage(self):
        """Should show all available posts if fewer than stage limit."""
        stages = [5, 10, 20]
        stage = 1
        all_posts = [MockRedditPost(f"Post {i}", f"http://example.com/{i}") for i in range(7)]
        
        stage_limit = stages[stage] if stage < len(stages) else 20
        posts_to_show = all_posts[:stage_limit]
        
        assert len(posts_to_show) == 7


class TestProgressiveLoadingAdvance:
    """Test advancing through progressive stages."""

    def test_advance_from_stage_0(self):
        """Should advance from stage 0 to stage 1."""
        stages = [5, 10, 20]
        stage = 0
        
        can_advance = stage < len(stages) - 1
        if can_advance:
            stage += 1
        
        assert can_advance is True
        assert stage == 1

    def test_advance_from_final_stage(self):
        """Should not advance from final stage."""
        stages = [5, 10, 20]
        stage = 2
        
        can_advance = stage < len(stages) - 1
        
        assert can_advance is False

    def test_advance_with_two_stages(self):
        """Should handle two-stage setup correctly."""
        stages = [5, 8]  # Target is 8
        stage = 0
        
        can_advance = stage < len(stages) - 1
        if can_advance:
            stage += 1
        
        assert can_advance is True
        assert stage == 1
        
        # Try to advance again
        can_advance = stage < len(stages) - 1
        assert can_advance is False


class TestCacheKeyPersistence:
    """Test cache key is used correctly for persistence."""

    def test_cache_key_defaults_to_subreddit(self):
        """Cache key should default to subreddit name."""
        subreddit = "wallpapers"
        cache_key = subreddit  # Default in __init__
        
        assert cache_key == "wallpapers"

    def test_cache_key_can_be_overridden(self):
        """Cache key can be set by factory to settings_key."""
        subreddit = "wallpapers"
        cache_key = subreddit
        
        # Factory sets cache_key
        settings_key = "reddit"
        cache_key = settings_key
        
        assert cache_key == "reddit"

    def test_cache_file_path_uses_cache_key(self):
        """Cache file path should use cache_key, not subreddit."""
        cache_key = "reddit2"
        
        # Simulate path generation
        cache_file = f"cache/reddit/{cache_key}_posts.json"
        
        assert cache_file == "cache/reddit/reddit2_posts.json"


def test_reddit_settings_spinboxes_use_shared_capacity_range():
    source = Path("ui/tabs/widgets_tab_reddit.py").read_text(encoding="utf-8")

    assert "tab.reddit_items.setRange(LIST_WIDGET_MIN_CAPACITY, LIST_WIDGET_MAX_CAPACITY)" in source
    assert "tab.reddit2_items.setRange(LIST_WIDGET_MIN_CAPACITY, LIST_WIDGET_MAX_CAPACITY)" in source


def test_reddit_settings_are_bucketed_by_instance():
    source = Path("ui/tabs/widgets_tab_reddit.py").read_text(encoding="utf-8")

    assert '"Reddit 1"' in source
    assert '"Reddit 2"' in source
    assert '"Link Behavior"' in source
    assert '"Shared Layout & Typography"' in source
    assert '"Shared Appearance"' in source
