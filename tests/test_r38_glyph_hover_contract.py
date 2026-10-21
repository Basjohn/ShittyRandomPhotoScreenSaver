"""Qt-free ingress/Settings/glyph policy coverage; native Qt is a separate gate."""
from pathlib import Path
from core.settings.default_settings import DEFAULT_SETTINGS

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT/path).read_text(encoding='utf-8')


def test_default_on_glyph_option_is_independent_from_glow():
    assert DEFAULT_SETTINGS['input']['always_show_glyphs'] is True
    settings = read('core/settings/models/_core.py')
    controller = read('rendering/quick/input_controller.py')
    projection = read('rendering/quick/scene_controller.py')
    assert 'input.always_show_glyphs' in settings
    assert 'always_show_glyphs=bool(always_show_glyphs)' in controller
    assert '"alwaysShowGlyphs": bool(input_state.always_show_glyphs)' in projection


def test_eligible_hover_and_fade_do_not_require_glow_enabled():
    ordinary = read('rendering/quick/qml/OverlayWidget.qml')
    visualizer = read('rendering/quick/qml/VisualizerPresentation.qml')
    assert 'overlayWidget.alwaysShowGlyphs\n' in ordinary
    assert '&& overlayWidget.widgetGlowAdmitted' in ordinary
    assert '&& overlayWidget.visible' in ordinary
    assert 'visualizerPresentationRoot.alwaysShowGlyphs' in visualizer
    assert 'cameraResetHover.hovered ? 700 : 1200' in visualizer
    assert 'duration: 200' not in visualizer[visualizer.index('id: cameraResetGlyph'):visualizer.index('id: visualizerPerfHud')]
    assert 'cameraResetHover.hovered && opacity > 0.05' in visualizer


def test_hide_controls_remains_edit_only_and_not_duplicated():
    ordinary = read('rendering/quick/qml/OverlayWidget.qml')
    visualizer = read('rendering/quick/qml/VisualizerPresentation.qml')
    assert 'parentGlyphControlsHidden' not in ordinary + visualizer
    edit = read('rendering/quick/qml/CustomLayoutOverlay.qml')
    assert 'parentGlyphControlsHidden' in edit
