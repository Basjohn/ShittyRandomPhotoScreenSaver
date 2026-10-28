"""Directory authority and explicit, transactional curated-preset replacement.

Reading a catalogue never writes or prunes it. Only an explicit replacement
owns numbered preset targets; Custom and unnumbered operator files survive.
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from collections.abc import Mapping

from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
from core.utils.atomic_files import atomic_write_bytes

_NUMBERED = re.compile(r'^preset[_-]*(\d+)(?:[_-].+)?\.json$', re.IGNORECASE)


def is_managed_curated_preset_path(path: Path) -> bool:
    """The narrow namespace an explicit replacement may remove."""
    return (len(path.parts) == 2 and path.parts[0] in VISUALIZER_MODE_IDS
            and 'custom' not in path.stem.lower() and bool(_NUMBERED.fullmatch(path.name)))


def scan_curated_visualizer_preset_tree(root: Path) -> set[str]:
    """Enumerate existing authored JSON files, without an inventory sidecar."""
    root = Path(root)
    if not root.is_dir():
        return set()
    return {p.relative_to(root).as_posix()
            for mode in VISUALIZER_MODE_IDS for p in (root / mode).glob('*.json')
            if p.is_file() and 'custom' not in p.stem.lower()}


def _safe_path(root: Path, entry: str) -> Path:
    relative = Path(entry)
    if (relative.is_absolute() or len(relative.parts) != 2 or '..' in relative.parts
            or relative.parts[0] not in VISUALIZER_MODE_IDS or relative.suffix.lower() != '.json'
            or 'custom' in relative.stem.lower()):
        raise ValueError(f'Not an authored visualizer preset path: {entry}')
    path = root / relative
    if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Preset path escapes its owned tree: {path}')
    return path


def snapshot_curated_visualizer_preset_tree(root: Path) -> dict[str, bytes]:
    """Validate every incoming file before a replacement can touch its target."""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f'Visualizer preset source tree does not exist: {root}')
    entries = scan_curated_visualizer_preset_tree(root)
    if not entries:
        raise ValueError(f'No authored visualizer presets under {root}')
    files = {}
    slots = set()
    for entry in sorted(entries):
        path = _safe_path(root, entry)
        data = path.read_bytes()
        payload = json.loads(data.decode('utf-8'))
        if not isinstance(payload, dict):
            raise ValueError(f'Preset root must be an object: {path}')
        mode = Path(entry).parts[0]
        for key in ('mode', 'visualizer_preset_mode'):
            if key in payload and payload[key] != mode:
                raise ValueError(f'Preset mode disagrees with directory: {path}')
        # Use the actual reader's admission, including legacy settings forms.
        from core.settings import visualizer_presets as vp
        parsed = vp._parse_preset_payload(path, payload, mode, prefer_filename_index=True)
        if parsed is None:
            raise ValueError(f'No readable {mode} preset in {path}')
        slot = (mode, parsed[0])
        if slot in slots:
            raise ValueError(f'Ambiguous duplicate preset slot {slot}: {path}')
        slots.add(slot)
        files[entry] = data
    return files


def apply_curated_preset_files(root: Path, files: Mapping[str, bytes], *, remove: set[str]) -> None:
    """Atomically replace individual files; restore all before-images on failure.

    The caller has already snapshotted/validated the complete incoming source.
    Removals are restricted to numbered curated files, never arbitrary JSON.
    """
    root = Path(root)
    if not files:
        raise ValueError('An empty replacement cannot erase the preset catalogue')
    if any(not is_managed_curated_preset_path(Path(entry)) for entry in remove):
        raise ValueError('Removal outside the numbered curated preset namespace')
    paths = {entry: _safe_path(root, entry) for entry in set(files) | remove}
    before = {entry: path.read_bytes() if path.exists() else None for entry, path in paths.items()}
    for entry, data in files.items():
        if (before[entry] is not None and not is_managed_curated_preset_path(Path(entry))
                and before[entry] != data):
            raise ValueError(f'Refusing to overwrite unnumbered operator preset: {paths[entry]}')
    touched = []
    expected_after = {}
    def current(entry):
        path = _safe_path(root, entry)
        return path.read_bytes() if path.exists() else None
    try:
        for entry in sorted(files):
            if current(entry) != before[entry]:
                raise RuntimeError(f'Preset changed during replacement: {paths[entry]}')
            if before[entry] != files[entry]:
                touched.append(entry)
                expected_after[entry] = files[entry]
                atomic_write_bytes(paths[entry], files[entry])
        for entry in sorted(remove - set(files)):
            if current(entry) != before[entry]:
                raise RuntimeError(f'Preset changed during replacement: {paths[entry]}')
            touched.append(entry)
            expected_after[entry] = None
            paths[entry].unlink()
    except Exception as failure:
        errors = []
        for entry in reversed(touched):
            try:
                value = current(entry)
                if value == before[entry]:
                    continue
                if value != expected_after[entry]:
                    raise RuntimeError('Newer edit preserved; automatic rollback refused')
                if before[entry] is None:
                    paths[entry].unlink(missing_ok=True)
                else:
                    atomic_write_bytes(paths[entry], before[entry])
            except Exception as exc:
                errors.append(f'{paths[entry]}: {exc}')
        if errors:
            recovery = None
            try:
                recovery = Path(tempfile.mkdtemp(prefix='srpss_preset_recovery_'))
                records = []
                for index, entry in enumerate(touched):
                    backup = f'{index}.before'
                    if before[entry] is not None:
                        atomic_write_bytes(recovery / backup, before[entry])
                    records.append({'path': str(paths[entry].absolute()),
                                    'before': backup if before[entry] is not None else None})
                atomic_write_bytes(recovery / 'recovery.json', json.dumps(records, indent=2).encode('utf-8'))
            except Exception as recovery_failure:
                errors.append(f'Could not finish recovery snapshot {recovery}: {recovery_failure}')
            raise RuntimeError(f'Preset replacement rollback failed; before-images at {recovery}: '
                               + '; '.join(errors)) from failure
        raise


def replace_curated_visualizer_preset_tree(source_root: Path, target_root: Path) -> set[str]:
    """Explicitly replace numbered targets from a validated immutable snapshot."""
    source_root, target_root = Path(source_root), Path(target_root)
    source, target = source_root.resolve(), target_root.resolve()
    if source != target and (source.is_relative_to(target) or target.is_relative_to(source)):
        raise ValueError('Preset source and target trees must not overlap')
    files = snapshot_curated_visualizer_preset_tree(source_root)
    if source == target:
        return set(files)
    stale = {entry for entry in scan_curated_visualizer_preset_tree(target_root)
             if is_managed_curated_preset_path(Path(entry)) and entry not in files}
    apply_curated_preset_files(target_root, files, remove=stale)
    return set(files)


def refresh_shipped_visualizer_presets(repo_root: Path | None = None) -> dict[str, object]:
    """Explicit source-to-release copy; never rewrite source preset artwork."""
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    source = root / 'presets' / 'visualizer_modes'
    release = root / 'release' / 'media_center' / 'presets' / 'visualizer_modes'
    entries = replace_curated_visualizer_preset_tree(source, release)
    return {'source_root': source, 'release_root': release, 'entries': entries, 'entry_count': len(entries)}
