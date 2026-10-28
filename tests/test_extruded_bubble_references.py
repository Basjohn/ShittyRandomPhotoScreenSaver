import json
from pathlib import Path

import pytest

from tools.labs.extruded_bubble_references import resolve_references


def test_registry_selects_renamed_target_without_guessing_recipe_filename(tmp_path):
    target = tmp_path / 'Preset1Goal.png'
    target.write_bytes(b'reference')
    (tmp_path / 'asset_manifest.json').write_text(json.dumps({'assets': [
        {'lab_recipe': 'ExBubble3', 'path': target.name}]}))
    assert resolve_references(['ExBubble3'], tmp_path) == {'ExBubble3': target}
    target.unlink()
    with pytest.raises(FileNotFoundError):
        resolve_references(['ExBubble3'], tmp_path)


@pytest.mark.parametrize('assets', [[], [
    {'lab_recipe': 'scene', 'path': '../outside.png'}], [
    {'lab_recipe': 'scene', 'path': 'a.png'}, {'lab_recipe': 'scene', 'path': 'b.png'}]])
def test_bad_reference_associations_fail_before_render_admission(tmp_path, assets):
    (tmp_path / 'asset_manifest.json').write_text(json.dumps({'assets': assets}))
    with pytest.raises(ValueError):
        resolve_references(['scene'], tmp_path)
