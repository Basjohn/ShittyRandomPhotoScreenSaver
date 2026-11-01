"""WR-00 reference custody and projection fixtures; no scene or mode renderer yet."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image
from core.settings.framed_camera import orthographic_matrix, perspective_matrix

PRIMARY = 'waveform_ribbon_package/Waveform_Ribbon_Concept.png'
CROPS = {'low': (0, 108, 640, 817), 'high': (651, 108, 1289, 817)}
FOG_CROPS = {'low': (11, 104, 831, 822), 'high': (841, 104, 1661, 822)}


def projection_fixture(width: int, height: int, projection: str = 'orthographic', *,
                       half_height: float = 4., reference_depth: float = 10.) -> dict:
    """Diagnostic scale only, not an admitted artistic camera pose or new camera owner.

    Perspective matches Orthographic at reference_depth. Resize preserves vertical
    world coverage; widening reveals more world without scaling actors or changing FOV.
    """
    if width <= 0 or height <= 0 or not all(math.isfinite(x) and x > 0 for x in (half_height, reference_depth)):
        raise ValueError('Positive dimensions and finite camera scale/depth required')
    half_extent = (half_height * width / height, half_height)
    near, far = .1, 100.
    if projection == 'orthographic':
        span = half_extent
        matrix = orthographic_matrix(span, near, far)
    elif projection == 'perspective':
        span = tuple(x / reference_depth for x in half_extent)
        matrix = perspective_matrix(span, near, far)
    else:
        raise ValueError(f'Unknown projection: {projection}')
    return dict(projection=projection, viewport=[width, height], span=list(span),
                near=near, far=far, reference_depth=reference_depth, matrix=list(matrix),
                matrix_layout='OpenGL column-major', pose_status='not fitted to reference',
                ray_authority='rendering/gl_programs/framed_camera.py:FRAMED_CAMERA_GLSL')


def prepare(archive: Path, output: Path, *, fog_board: Path | None = None) -> dict:
    source = fog_board or archive
    source_bytes = source.read_bytes()
    if fog_board is None:
        with ZipFile(io.BytesIO(source_bytes)) as bundle:
            primary = bundle.read(PRIMARY)
    else:
        primary = source_bytes
    crops = FOG_CROPS if fog_board else CROPS
    with Image.open(io.BytesIO(primary)) as image:
        image.load()
        if image.size != (1672, 941):
            raise ValueError('Primary board dimensions changed; review crop authority before extraction')
        if output.exists() and any(output.iterdir()):
            raise FileExistsError(f'Refusing to overwrite existing evidence: {output}')
        output.mkdir(parents=True, exist_ok=True)
        (output / 'primary.png').write_bytes(primary)
        for name, box in crops.items():
            image.crop(box).save(output / f'{name}.png')
    receipt = dict(stage='WR-00 partial: custody and diagnostic projection only',
                   source=str(source.resolve()), source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                   producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   board='fog' if fog_board else 'primary', primary_member=None if fog_board else PRIMARY,
                   primary_sha256=hashlib.sha256(primary).hexdigest(),
                   crops=crops, crop_status='native pixels; panel border excluded for fog board',
                   image_conversion='PNG source mode preserved; no stretching or colour conversion',
                   projections={kind: projection_fixture(crops['low'][2]-crops['low'][0], crops['low'][3]-crops['low'][1], kind)
                                for kind in ('orthographic', 'perspective')},
                   scene_rendered=False, gpu_cost_measured=False, audio_windows_selected=False)
    receipt['artifacts'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob('*.png'))}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ROOT / 'references/waveform_ribbon_concept_package.zip')
    parser.add_argument('--fog-board', type=Path, help='Extract the operator whole-scene fog board instead of the original archive')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = prepare(args.archive, args.output, fog_board=args.fog_board)
    receipt['source_revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    diff = subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)
    receipt['tracked_diff_sha256'] = hashlib.sha256(diff).hexdigest()
    receipt['workspace_status'] = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True).splitlines()
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(f'WR-00 preflight: {args.output}; Orthographic default; scene/likeness gates remain open')


if __name__ == '__main__':
    main()
