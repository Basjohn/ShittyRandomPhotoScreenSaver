"""Resolve current EB target paths from their sole asset registry, before GL."""
import json
from pathlib import Path


def resolve_references(names, root: Path) -> dict[str, Path]:
    assets = json.loads((root / 'asset_manifest.json').read_text(encoding='utf-8'))['assets']
    registered = {}
    for asset in assets:
        recipe = asset.get('lab_recipe')
        if recipe is None:
            continue
        if recipe in registered:
            raise ValueError(f'Duplicate EB lab reference: {recipe}')
        path = (root / asset['path']).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError(f'EB reference escapes registry root: {path}')
        registered[recipe] = path
    selected = {}
    for name in names:
        if name not in registered:
            raise ValueError(f'No EB reference association for recipe: {name}')
        path = registered[name]
        if not path.is_file():
            raise FileNotFoundError(f'EB lab reference unavailable: {path}')
        selected[name] = path
    return selected
