"""R41 focused policy gates. Native QML smoke is still required on Windows."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / 'rendering/quick/qml'


def read(path):
    return path.read_text(encoding='utf-8')


def test_glyph_tooltips_wait_at_least_a_second_without_timers_or_polling():
    s = read(QML/'WidgetHoverEditGlyphs.qml')
    assert 'duration: 1800' in s
    assert '(chrome.delayedTipProgress - 0.56) / 0.44' in s
    assert 1800 * .56 >= 1000
    assert 'tipReveal.restart()' in s
    assert 'onExited:' in s and 'tipReveal.stop()' in s
    assert 'Timer {' not in s and 'onFrameSwapped' not in s
    for tip in ('TOGGLE CHILD LOCK', 'RESTORE WIDGET SIZE',
                'ROTATE WIDGET CONTENT', 'CLOSE & DISABLE WIDGET'):
        assert tip in s
    assert 'enabled: false\n        visible: opacity' in s


def test_glyphs_follow_actual_media_card_not_accessory_host_and_close_is_vector():
    outer = read(QML/'OverlayWidget.qml')
    shared = read(QML/'WidgetHoverEditGlyphs.qml')
    assert 'objectName: "ordinaryHoverGlyphLoader"\n' in outer
    assert 'anchors.fill: card' in outer
    assert 'visible: actionKind === "close"' in shared
    # The authored inset/scale can change; preserve centred vector geometry.
    import re
    start = re.search(r'ctx.moveTo\(([\d.]+), \1\)', shared)
    end = re.search(r'ctx.lineTo\(([\d.]+), \1\)', shared)
    assert start and end
    low, high = float(start[1]), float(end[1])
    assert 0 < low < 10 < high < 20 and low+high == 20
    scale = re.search(r'ctx.scale\(([\d.]+), \1\)', shared)
    assert scale and 0 < float(scale[1]) < 1
    assert 'font.pixelSize: actionKind === "restore" ? 17 : 15' in shared
    assert 'width: visible ? 24 : 0' in shared
    assert 'height: 24' in shared


def test_camera_reset_tooltip_has_the_same_delayed_qml_clock():
    s = read(QML/'VisualizerPresentation.qml')
    assert 'cameraResetTipReveal.restart()' in s
    assert '(visualizerPresentationRoot.cameraResetTipProgress - 0.56) / 0.44' in s
    assert 'cameraActionTip = "RESET CAMERA"' in s
    assert 'text: visualizerPresentationRoot.cameraActionTip' in s
    assert 'Timer {' not in s


def test_eb_settings_tooltips_are_escaped_wrapped_not_one_line_or_new_owner():
    s = read(ROOT/'ui/tabs/media/spec_mode_builder.py')
    assert 'textwrap.wrap(control.tooltip, width=59' in s
    assert 'html.escape(line)' in s
    assert '<br/>' in s
    assert 'widget.setToolTip(_control_tooltip(control))' in s
    assert 'row.setToolTip(_control_tooltip(control))' in s


def test_surface_and_deep_light_authority_distinction_remains_explicit():
    source = read(ROOT/'rendering/gl_programs/extruded_bubble_scene.py')
    render = read(ROOT/'rendering/quick/visualizer/implementations/extruded_bubble.py')
    assert 'knobs["ray_source"] = knobs["light_source"]' in source
    assert 'ray_source=world_point(ray_path[:3])' in source
    assert 'light_on_screen(knobs["sun_below"]' in render
    assert '"uRaySource": _floats(knobs["ray_source"])' in render
    assert '"uRayEnd": _floats(knobs["ray_end"])' in render
