# Quick Start Guide

## First Run

When you run the screensaver for the first time with no sources configured:

```bash
python main.py
```

**What happens**:
1. Detects no image sources configured
2. Automatically opens Settings Dialog
3. You configure your sources
4. Close dialog and run again

---

## Adding Image Sources

### Option 1: Local Folders

1. Open Settings Dialog: `python main.py /c`
2. Go to **Sources** tab
3. Click **Add Folder**
4. Select a folder with images (JPG, PNG, etc.)
5. Click **OK**

### Option 2: RSS Feeds

1. Open Settings Dialog: `python main.py /c`
2. Go to **Sources** tab
3. See the **suggested feed**: NASA Image of the Day
4. Copy/paste this URL into the field:
   ```
   https://www.nasa.gov/feeds/iotd-feed
   ```
5. Click **Add Feed**

**Other good RSS feeds:**
- Wikimedia Picture of the Day: `https://commons.wikimedia.org/w/api.php?action=featuredfeed&feed=potd&feedformat=rss&language=en`
- NASA Breaking News: `https://www.nasa.gov/news-release/feed/`

---

## Running the Screensaver

### Run Mode (Normal)
```bash
python main.py
# or
python main.py /s
```

### Config Mode (Settings)
```bash
python main.py /c
```

### Preview Mode (Not implemented yet)
```bash
python main.py /p
```

---

## Hotkeys While Running

- **Z** - Go to previous image
- **X** - Go to next image
- **C** - Cycle through transition modes
- **S** - Stop and open Settings
- **ESC** - Exit screensaver
- **Click** - Exit screensaver

---

## Common Issues

### "Failed to initialize screensaver engine"
**Cause**: No image sources configured  
**Solution**: Settings dialog will open automatically - add folders or RSS feeds

### "Failed to load image" (rare now)
**Cause**: Bad/corrupted image file  
**Solution**: Automatically skips to next image (up to 10 retries)

### No images showing
**Cause**: Empty folders or RSS feeds with no images  
**Solution**: Add more sources or check folder paths

---

## Configuration File Location

Settings are stored in:
```
%USERPROFILE%\.screensaver\settings.json
```

You can manually edit this file if needed, but use the Settings Dialog instead.

---

## Example Configuration

After adding sources, your `settings.json` might look like:

```json
{
  "sources": {
    "folders": [
      "C:\\Users\\YourName\\Pictures\\Wallpapers",
      "D:\\Photos\\Vacation"
    ],
    "rss_feeds": [
      "https://www.nasa.gov/feeds/iotd-feed"
    ]
  },
  "timing": {
    "interval": 10
  },
  "display": {
    "mode": "fill"
  },
  "transitions": {
    "type": "Crossfade",
    "duration": 1000,
    "direction": "Left to Right",
    "easing": "Linear"
  }
}
```

---

## Next Steps

1. **Test it**: Run `python main.py` and add some sources
2. **Customize**: Open settings and adjust transitions, timing, etc.
3. **Enjoy**: Press ESC to close the settings and watch your screensaver!

**Need help?** Check the documentation in `Docs/` folder.
