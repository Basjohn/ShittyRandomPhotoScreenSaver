import json
from pathlib import Path

def expand_dotted_keys(flat):
    result = {}
    for key, value in flat.items():
        parts = key.split('.')
        target = result
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return result

root = Path(r"f:/Programming/Apps/ShittyRandomPhotoScreenSaver2_5")
data = json.loads((root / "SRPSS_Settings_MC.json").read_text())
snapshot = data["snapshot"]

# Ensure blank sources and weather location
sources = snapshot.setdefault("sources", {})
sources["folders"] = []
sources["rss_feeds"] = []
weather = snapshot.get("widgets", {}).get("weather")
if isinstance(weather, dict):
    weather["location"] = ""
    weather.pop("latitude", None)
    weather.pop("longitude", None)

# Clean preserved keys inside custom preset backup if present
cpb = snapshot.get("custom_preset_backup")
if isinstance(cpb, dict):
    if "sources.folders" in cpb:
        cpb["sources.folders"] = []
    if "sources.rss_feeds" in cpb:
        cpb["sources.rss_feeds"] = []
    if "widgets.weather.location" in cpb:
        cpb["widgets.weather.location"] = ""
    if "widgets.weather.latitude" in cpb:
        cpb["widgets.weather.latitude"] = ""
    if "widgets.weather.longitude" in cpb:
        cpb["widgets.weather.longitude"] = ""

for section in ("accessibility", "mc", "workers"):
    flat = snapshot.get(section)
    if isinstance(flat, dict) and any('.' in k for k in flat.keys()):
        snapshot[section] = expand_dotted_keys(flat)

(root / "defaults_payload.json").write_text(json.dumps(snapshot, indent=4), encoding="utf-8")
