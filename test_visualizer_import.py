"""Test script to verify visualizer imports correctly with fresh modules."""
import sys
import shutil
from pathlib import Path

# Clean all pycache BEFORE importing
print("Cleaning __pycache__ directories...")
project_root = Path(__file__).parent
removed = 0
for pycache_dir in project_root.rglob("__pycache__"):
    try:
        shutil.rmtree(pycache_dir)
        removed += 1
    except Exception as e:
        print(f"Failed to remove {pycache_dir}: {e}")

print(f"Removed {removed} __pycache__ directories")

# Now import
print("\nImporting beat_engine...")
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
import inspect

# Check signature
sig = inspect.signature(_SpotifyBeatEngine.get_smoothed_bars)
print(f"get_smoothed_bars signature: {sig}")

# Verify segments parameter exists
params = list(sig.parameters.keys())
print(f"Parameters: {params}")

if 'segments' in params:
    print("✅ SUCCESS: segments parameter found")
    
    # Test instantiation
    engine = _SpotifyBeatEngine(bar_count=21)
    result = engine.get_smoothed_bars(segments=18)
    print(f"✅ SUCCESS: Called with segments=18, returned {len(result)} bars")
else:
    print("❌ FAILURE: segments parameter NOT found")
    sys.exit(1)
