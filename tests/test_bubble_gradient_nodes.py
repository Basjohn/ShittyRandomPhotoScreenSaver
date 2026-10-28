"""Production two-node input, persistence, recipe isolation and Settings gesture undo."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from core.settings.default_contract import require_canonical_default
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_settings_snapshot import normalize_visualizer_mode_payload
from tests.test_bubble_spec_ui import body
from ui.settings_undo import SettingsUndo
from ui.tabs.media.bubble_settings_binding import collect_bubble_mode_settings, load_bubble_mode_settings


def test_custom_nodes_roundtrip_model_snapshot_import_and_runtime_projection():
    from rendering.quick.visualizer.implementations.bubble import QuickBubbleRenderer
    from core.gradient_geometry import project_linear_gradient
    from types import SimpleNamespace
    points = [.12, .77, .83, .21]
    config = {'bubble_gradient_direction': 'custom', 'bubble_gradient_endpoints': points,
              'bubble_gradient_semantics_version': 2}
    model = SpotifyVisualizerSettings.from_mapping(config, apply_preset_overlay=False)
    assert model.bubble_gradient_direction == 'custom'
    assert model.bubble_gradient_endpoints == points
    saved = model.to_dict()
    reloaded = SpotifyVisualizerSettings.from_mapping(saved, apply_preset_overlay=False)
    assert reloaded.bubble_gradient_endpoints == points
    normalized = normalize_visualizer_mode_payload('bubble', config)
    assert normalized['bubble_gradient_endpoints'] == points
    assert normalize_visualizer_mode_payload('bubble', normalized) == normalized
    renderer = QuickBubbleRenderer()
    from core.settings.bubble_gradient_semantics import project_bubble_gradient
    with pytest.raises(ValueError, match='endpoint projection'):
        project_bubble_gradient('custom')
    for aspect in (.5, 2., 4.):
        assert renderer._gradient_parameters(config, SimpleNamespace(aspect_ratio=aspect)) == (
            *project_linear_gradient(points, aspect), 0.)


@pytest.mark.parametrize('value', (None, [0., 0., 0., 0.], [1., 2.], [float('nan'), 0., 1., 1.]))
def test_bad_nodes_use_the_single_canonical_default(value):
    model = SpotifyVisualizerSettings.from_mapping({'bubble_gradient_endpoints': value}, apply_preset_overlay=False)
    assert model.bubble_gradient_endpoints == require_canonical_default('widgets.spotify_visualizer.bubble_gradient_endpoints')


@pytest.mark.qt
def test_node_gesture_selects_custom_and_undo_restores_recipe_nodes_and_disclosure(body):
    tab, manager, config = body
    points = [.2, .8, .8, .2]
    load_bubble_mode_settings(tab, {**config, 'bubble_gradient_direction': 'top_right',
                                   'bubble_gradient_semantics_version': 2,
                                   'bubble_gradient_endpoints': points})
    assert not hasattr(tab.bubble_gradient_direction, 'direction_mapper')
    editor = tab.bubble_gradient_endpoints
    owner = SettingsUndo(tab)
    assert not owner.can_undo
    editor.setFocus()
    QTest.keyClick(editor, Qt.Key.Key_Right)
    tab._flush_pending_visualizer_save()
    changed = editor.value()
    assert changed != tuple(points) and owner.can_undo
    assert tab.bubble_gradient_direction.currentData() == 'custom'
    saved = manager.get('widgets', {})['spotify_visualizer']
    assert saved['bubble_gradient_direction'] == 'custom'
    assert saved['bubble_gradient_endpoints'] == list(changed)
    # A programmatic recipe change is not a user gesture. It must not destroy
    # latent custom nodes or leave disclosure stale when the node edit is undone.
    tab.bubble_gradient_direction.setCurrentIndex(tab.bubble_gradient_direction.findData('center_out'))
    assert tab._bubble_rows['bubble_gradient_endpoints'].isHidden()
    assert editor.value() == changed
    assert owner.undo()
    tab._flush_pending_visualizer_save()
    assert editor.value() == tuple(points)
    assert tab.bubble_gradient_direction.currentData() == 'top_right'
    assert not tab._bubble_rows['bubble_gradient_endpoints'].isHidden()
    assert not owner.can_undo and owner.can_redo
    assert owner.redo()
    tab._flush_pending_visualizer_save()
    assert editor.value() == changed and tab.bubble_gradient_direction.currentData() == 'custom'
    assert owner.can_undo and not owner.can_redo


@pytest.mark.qt
def test_recipe_switch_and_hydration_preserve_latent_custom_nodes_without_undo(body):
    tab, _manager, config = body
    points = [.1, .7, .6, .2]
    owner = SettingsUndo(tab)
    for direction in ('custom', 'left', 'center_out_reverse', 'custom'):
        load_bubble_mode_settings(tab, {**config, 'bubble_gradient_direction': direction,
                                      'bubble_gradient_semantics_version': 2,
                                      'bubble_gradient_endpoints': points})
        values = collect_bubble_mode_settings(tab)
        assert values['bubble_gradient_endpoints'] == points
        assert values['bubble_gradient_direction'] == direction
        assert not owner.can_undo


@pytest.mark.qt
@pytest.mark.parametrize('size', ((320, 160), (120, 240)))
def test_custom_nodes_reach_native_gradient_pixels_with_span_and_placement(size, qt_app):
    import numpy as np
    from core.gradient_geometry import project_linear_gradient
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.labs.render_target import OffscreenRenderTarget
    from tests.test_bubble_aspect_pixels import _presentation, _snapshot

    width, height = size
    host, target = QuickVisualizerRenderHost(), OffscreenRenderTarget(width, height)
    presentation = _presentation(width, height)
    matrix = (2/width, 0, 0, 0, 0, -2/height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
    images = []
    try:
        for points in ((.1, .9, .9, .1), (.4, .6, .6, .4), (.05, .65, .45, .25)):
            snapshot = _snapshot(presentation, radius=.02, count=0, overrides={
                'bubble_gradient_direction': 'custom', 'bubble_gradient_endpoints': points,
                'bubble_gradient_dark': (0, 0, 0, 255), 'bubble_gradient_light': (255, 255, 255, 255)})
            target.bind()
            assert host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                               logical_size=(float(width), float(height)), matrix_values=matrix) == 'bubble'
            pixels = target.read_rgba()
            layout = host._implementations['bubble']._layout_cache
            x, y, w, h = layout.content_rect
            gx, gy, bias = project_linear_gradient(points, layout.aspect_ratio)
            yy, xx = np.mgrid[:height, :width]
            expected = np.clip((((xx+.5-x)/w-.5)*gx + ((yy+.5-y)/h-.5)*gy + .5+bias), 0., 1.)*255
            inside = (xx > x+2) & (xx < x+w-2) & (yy > y+2) & (yy < y+h-2)
            np.testing.assert_allclose(pixels[:, :, 0][inside], expected[inside], atol=1.)
            assert (pixels[:, :, 3][inside] == 255).all()
            images.append(pixels)
        assert not np.array_equal(images[0], images[1])
        assert not np.array_equal(images[0], images[2])
    finally:
        target.make_current()
        host.release_resources()
        target.close()
