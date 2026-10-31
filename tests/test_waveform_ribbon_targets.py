import json

import pytest
from PIL import Image

from tools.labs import waveform_ribbon_targets as targets


def cards(tmp_path, sizes=((640, 709), (638, 709))):
    folder = tmp_path/'cards'
    folder.mkdir()
    for name, size in zip(('low', 'high'), sizes):
        Image.new('RGB', size, (20, 30, 90)).save(folder/f'{name}.png')
    return folder


def test_masks_exclude_annotations_and_receipt_records_estimates(tmp_path):
    folder = cards(tmp_path)
    high = Image.open(folder/'high.png')
    high.paste((255, 255, 255), targets.MASKS['high'][3])  # white callout overlapping the crest ROI
    high.save(folder/'high.png')
    receipt = targets.run(folder, tmp_path/'out')
    stored = json.loads((tmp_path/'out'/'targets.json').read_text())
    assert stored['traced']['status'].startswith('estimate')
    assert receipt['camera']['status'].startswith('analytic proposal')
    for name, panel in receipt['panels'].items():
        for stats in panel['rois'].values():
            assert stats['pixels'] > 0 and stats['clipped_fraction'] == 0
    assert (tmp_path/'out'/'targets_sheet.png').exists()
    with pytest.raises(FileExistsError):
        targets.run(folder, tmp_path/'out')


def test_changed_card_geometry_is_refused(tmp_path):
    with pytest.raises(ValueError):
        targets.run(cards(tmp_path, ((640, 708), (638, 709))), tmp_path/'out')


def test_traced_points_stay_inside_their_cards():
    for name, size in (('low', (640, 709)), ('high', (638, 709))):
        for x, (top, bottom) in targets.ENVELOPE[name].items():
            assert 0 <= x < size[0] and 0 <= top < bottom < size[1]
        for box in (*targets.MASKS[name], *targets.ROIS[name].values()):
            assert 0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1]
