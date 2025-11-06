"""Fix corrupted settings file."""
import json
from pathlib import Path

# Settings file location
settings_path = Path.home() / ".screensaver" / "settings.json"

print(f"Settings file: {settings_path}")
print(f"Exists: {settings_path.exists()}")

if settings_path.exists():
    print("\nCurrent settings:")
    with open(settings_path, 'r') as f:
        settings = json.load(f)
        print(json.dumps(settings, indent=2))
    
    # Check if sources config looks wrong
    if 'sources' in settings:
        sources = settings['sources']
        print(f"\nSources config:")
        print(f"  folders: {sources.get('folders', [])}")
        print(f"  rss_feeds: {sources.get('rss_feeds', [])}")
        
        # Fix if needed
        if not isinstance(sources.get('folders'), list):
            print("\n⚠️  ERROR: 'folders' is not a list!")
            sources['folders'] = []
        
        if not isinstance(sources.get('rss_feeds'), list):
            print("\n⚠️  ERROR: 'rss_feeds' is not a list!")
            sources['rss_feeds'] = []
        
        # Make sure both exist
        if 'folders' not in sources:
            sources['folders'] = []
        if 'rss_feeds' not in sources:
            sources['rss_feeds'] = []
        
        # Write back
        settings['sources'] = sources
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)
        
        print("\n✅ Settings fixed!")
        print("\nNew settings:")
        print(json.dumps(settings, indent=2))
else:
    print("\nNo settings file exists yet - will be created on first run")
