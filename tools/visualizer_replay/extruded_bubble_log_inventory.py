"""Read ZIPs without extracting/mutating them; retain EB-only forensic receipts.

Archive counts include overlapping retained log rotations, not distinct runs.
No EB receipts does not prove EB never ran. Historical logs are not current authority.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import zipfile


def entries(payload):
    """Split a logged mapping by top-level commas, tolerating nonliteral Qt reprs.

    Evaluate only each selected numeric setting, never the entire logged mapping.
    """
    depth, quote, escaped, start = 0, '', False, 1
    if not payload.startswith('{'):
        raise ValueError('settings mapping has no opening brace')
    for i, char in enumerate(payload):
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = ''
        elif char in "'\"":
            quote = char
        elif char in '{[(':
            depth += 1
        elif char in '}])':
            depth -= 1
            if depth == 0:
                yield payload[start:i].strip()
                return
        elif char == ',' and depth == 1:
            yield payload[start:i].strip()
            start = i + 1
    raise ValueError('truncated settings mapping')


def settings_receipts(lines):
    result, errors = [], 0
    marker = 'Section changed: widgets: '
    for line in lines:
        if marker not in line:
            continue
        try:
            section = next(part.partition(':')[2].strip()
                           for part in entries(line.split(marker, 1)[1])
                           if part.startswith("'spotify_visualizer':"))
            selected = {}
            for part in entries(section):
                key, _, value = part.partition(':')
                key = ast.literal_eval(key)
                if key.startswith('extruded_bubble_') or key in ('mode', 'preset_extruded_bubble'):
                    selected[key] = ast.literal_eval(value)
            result.append({'timestamp': line[:19], 'values': selected})
        except (SyntaxError, ValueError, StopIteration):
            errors += 1
    return result, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records = []
    for path in sorted(args.directory.glob('*.zip')):
        entry = {'archive': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'bytes': path.stat().st_size, 'files': []}
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith('screensaver_frame_trace.bin'):
                    entry['trace_bytes'] = archive.getinfo(name).file_size
                if not name.endswith(('.log', '.log.1', '.log.2')):
                    continue
                lines = archive.read(name).decode('utf-8', errors='replace').splitlines()
                configs = [line for line in lines if '[VIS_TECH_CONFIG] mode=extruded_bubble' in line]
                faults = [line for line in lines if '[LIFECYCLE_BARRIER] timeout' in line]
                refs = [line for line in lines if '[PYTHON_OWNER_REFS' in line]
                settings, errors = settings_receipts(lines) if 'settings.log' in name else ([], 0)
                if configs or faults or refs or settings or errors:
                    entry['files'].append({'name': name, 'eb_configs': len(configs),
                                           'configurations': configs, 'barrier_timeouts': faults,
                                           'referrers': refs, 'settings': settings, 'settings_parse_errors': errors})
        records.append(entry)
        print(path.name, 'EB receipts', sum(f['eb_configs'] for f in entry['files']),
              'settings snapshots', sum(len(f['settings']) for f in entry['files']),
              'settings parse failures', sum(f['settings_parse_errors'] for f in entry['files']),
              'owner ref receipts', sum(len(f['referrers']) for f in entry['files']))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
