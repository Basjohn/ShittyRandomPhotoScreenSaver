import hashlib
import io
import json
from zipfile import ZipFile

from PIL import Image
import pytest

from tools.labs.waveform_ribbon_preflight import PRIMARY, prepare, projection_fixture


def ndc(camera, point):
    m = camera['matrix']
    x, y, z = point
    w = m[11] * z + m[15]
    return ((m[0]*x+m[12])/w, (m[5]*y+m[13])/w, (m[10]*z+m[14])/w)


def test_orthographic_default_preserves_world_scale_and_clip_depth_under_resize():
    base = projection_fixture(640, 709)
    wide = projection_fixture(1280, 709)
    assert base['projection'] == 'orthographic'
    assert ndc(base, (1, 1, -5))[:2] == ndc(base, (1, 1, -20))[:2]
    assert ndc(base, (1, 1, -5))[0] * 640 == pytest.approx(ndc(wide, (1, 1, -5))[0] * 1280)
    assert ndc(base, (1, 1, -5))[1] == ndc(wide, (1, 1, -5))[1]
    for depth, expected in ((base['near'], -1), (base['far'], 1)):
        assert ndc(base, (0, 0, -depth))[2] == pytest.approx(expected)


def test_optional_perspective_matches_only_the_reference_plane():
    ortho = projection_fixture(640, 709)
    perspective = projection_fixture(640, 709, 'perspective')
    assert ndc(ortho, (1, 1, -10))[:2] == pytest.approx(ndc(perspective, (1, 1, -10))[:2])
    assert ndc(perspective, (1, 1, -5))[0] == pytest.approx(2 * ndc(perspective, (1, 1, -10))[0])
    with pytest.raises(ValueError):
        projection_fixture(640, 709, 'unknown')


def test_source_bytes_and_panel_aspects_survive_custody_without_overwrite(tmp_path):
    image = Image.new('RGB', (1672, 941), (19, 41, 63))
    data = io.BytesIO()
    image.save(data, format='PNG')
    archive = tmp_path / 'concept.zip'
    with ZipFile(archive, 'w') as bundle:
        bundle.writestr(PRIMARY, data.getvalue())
    output = tmp_path / 'proof'
    receipt = prepare(archive, output)
    assert (output / 'primary.png').read_bytes() == data.getvalue()
    assert receipt['primary_sha256'] == hashlib.sha256(data.getvalue()).hexdigest()
    assert Image.open(output / 'low.png').size == (640, 709)
    assert Image.open(output / 'high.png').size == (638, 709)
    assert not json.loads((output / 'receipt.json').read_text())['scene_rendered']
    with pytest.raises(FileExistsError):
        prepare(archive, output)
