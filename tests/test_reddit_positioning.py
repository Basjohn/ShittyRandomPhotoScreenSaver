"""Test script to debug Reddit widget positioning issue.

Run this to see what positions are being loaded from settings.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.settings.manager import SettingsManager
from core.settings.normalization import normalize_widget_position
from core.settings.models import RedditWidgetSettings, WidgetPosition

def test_reddit_positioning():
    """Test Reddit widget position loading."""
    settings = SettingsManager()
    
    print("=" * 80)
    print("REDDIT WIDGET POSITIONING TEST")
    print("=" * 80)
    
    # Test Reddit 1
    print("\n--- Reddit 1 ---")
    reddit1_config = settings.get('widgets.reddit', {})
    print(f"Raw config: {reddit1_config}")
    
    reddit1_model = RedditWidgetSettings.from_mapping(reddit1_config, prefix="widgets.reddit")
    print(f"Model position: {reddit1_model.position}")
    print(f"Model position value: {reddit1_model.position.value}")
    print(f"Model monitor: {reddit1_model.monitor}")
    print(f"Model enabled: {reddit1_model.enabled}")
    
    # Test normalization
    raw_pos = reddit1_config.get('position', 'TOP_RIGHT')
    print(f"Raw position string: {raw_pos}")
    normalized = normalize_widget_position(raw_pos, WidgetPosition.TOP_RIGHT)
    print(f"Normalized position: {normalized}")
    print(f"Normalized value: {normalized.value}")
    
    # Test Reddit 2
    print("\n--- Reddit 2 ---")
    reddit2_config = settings.get('widgets.reddit2', {})
    print(f"Raw config: {reddit2_config}")
    
    reddit2_model = RedditWidgetSettings.from_mapping(reddit2_config, prefix="widgets.reddit2")
    print(f"Model position: {reddit2_model.position}")
    print(f"Model position value: {reddit2_model.position.value}")
    print(f"Model monitor: {reddit2_model.monitor}")
    print(f"Model enabled: {reddit2_model.enabled}")
    
    # Test normalization
    raw_pos2 = reddit2_config.get('position', 'TOP_LEFT')
    print(f"Raw position string: {raw_pos2}")
    normalized2 = normalize_widget_position(raw_pos2, WidgetPosition.TOP_LEFT)
    print(f"Normalized position: {normalized2}")
    print(f"Normalized value: {normalized2.value}")
    
    print("\n" + "=" * 80)
    print("EXPECTED vs ACTUAL")
    print("=" * 80)
    print(f"Reddit 1 Expected: MIDDLE_RIGHT (middle_right)")
    print(f"Reddit 1 Actual:   {reddit1_model.position.name} ({reddit1_model.position.value})")
    print(f"Reddit 2 Expected: BOTTOM_RIGHT (bottom_right)")
    print(f"Reddit 2 Actual:   {reddit2_model.position.name} ({reddit2_model.position.value})")
    
    if reddit1_model.position.value != "middle_right":
        print("\n⚠️  Reddit 1 position MISMATCH!")
    else:
        print("\n✅ Reddit 1 position correct")
        
    if reddit2_model.position.value != "bottom_right":
        print("⚠️  Reddit 2 position MISMATCH!")
    else:
        print("✅ Reddit 2 position correct")

if __name__ == "__main__":
    test_reddit_positioning()
