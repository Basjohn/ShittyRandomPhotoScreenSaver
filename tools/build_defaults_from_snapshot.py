import importlib.util
import pathlib
import pprint
import sys
from copy import deepcopy

ROOT = pathlib.Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / 'core' / 'settings' / 'defaults_snapshot.py'

spec = importlib.util.spec_from_file_location('defaults_snapshot', SNAPSHOT_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def sanitize(data: dict) -> dict:
    defaults = deepcopy(data)

    # Ensure blank sources and weather location for canonical baseline
    sources = defaults.setdefault('sources', {})
    sources['folders'] = []
    sources['rss_feeds'] = []

    widgets = defaults.setdefault('widgets', {})
    weather = widgets.setdefault('weather', {})
    weather['location'] = ''
    weather.pop('latitude', None)
    weather.pop('longitude', None)

    cpb = defaults.get('custom_preset_backup')
    if isinstance(cpb, dict):
        cpb.pop('sources.folders', None)
        cpb.pop('sources.rss_feeds', None)
        cpb.pop('widgets.weather.location', None)
        cpb.pop('widgets.weather.latitude', None)
        cpb.pop('widgets.weather.longitude', None)

    # Purge eco mode
    mc = defaults.get('mc')
    if isinstance(mc, dict):
        mc.clear()

    # Disable FFT worker
    workers = defaults.setdefault('workers', {})
    fft = workers.setdefault('fft', {})
    fft['enabled'] = False

    return defaults


def main() -> int:
    sanitized = sanitize(module.DEFAULTS)
    sys.stdout.write('DEFAULT_SETTINGS = ' + pprint.pformat(sanitized, width=100) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
