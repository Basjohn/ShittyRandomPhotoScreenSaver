"""Import-free guard against OSD polling, duplicate audio ownership and silent omission."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_osd_is_one_independently_dormant_retained_quick_family():
    catalog = _source("core/settings/widget_family_catalog.py")
    defaults = _source("core/settings/default_settings.py")
    binder = _source("rendering/quick/widgets/family_binder.py")
    registry = _source("rendering/quick/widgets/registry.py")
    assert 'family_id="system_audio_osd"' in catalog
    assert "'system_audio_osd': {'enabled': False" in defaults
    assert 'return _enabled_from_candidates(widgets_config, ("system_audio_osd",))' in binder
    assert 'qml_filename="SystemAudioOSDPresentation.qml"' in registry
    assert '"system_audio_osd": _SYSTEM_MUTE_SERVICE_SPEC' in _source(
        "rendering/widget_runtime_services.py"
    )


def test_osd_uses_only_shared_audio_lease_and_one_event_owned_deadline():
    model = _source("rendering/quick/widgets/system_audio_osd.py")
    qml = _source("rendering/quick/qml/SystemAudioOSDPresentation.qml")
    assert model.count("QTimer(self)") == 1
    assert "self._deadline.setSingleShot(True)" in model
    assert "self._deadline.start(self.config.inactivity_ms)" in model
    assert "service.attach_consumer(self)" in model
    assert "service.detach_consumer(self)" in model
    assert "service.stop()" in model
    assert "SystemAudioOSDPolicy" in model
    for forbidden in ("GetSpeakers", "AudioUtilities", "IAudioEndpointVolumeCallback",
                      "QThread(", "threading.Timer", "time.sleep(", "setInterval(",
                      "processEvents(", "requestUpdate("):
        assert forbidden not in model + qml, forbidden
    assert 'objectName: "systemAudioOSDVolumeTrack"' in qml
    assert 'objectName: "systemAudioOSDVolumeFill"' in qml
    assert "import QtQuick.Effects" not in qml


def test_settings_are_canonical_and_custom_editor_is_descriptor_routed():
    section = _source("ui/tabs/widgets_tab_system_audio_osd.py")
    descriptors = _source("rendering/widget_descriptors.py")
    assert 'section_id="system_audio_osd"' in descriptors
    assert 'widget_id="system_audio_osd"' in descriptors
    assert 'WidgetCustomPositionOptionDescriptor("system_audio_osd",' in descriptors
    assert 'section_id="system_audio_osd",\n        settings_section_id="system_audio_osd"' in descriptors
    assert '"text_position": _selected_text_position(' in section
    assert '"inactivity_ms": int(' in section
    assert '"preferred_width": int(' in section
    assert '"preferred_height": int(' in section
    for forbidden in ('os.environ', 'setenv(', 'getenv(', 'QTimer(', 'GetSpeakers('):
        assert forbidden not in section


def test_osd_has_one_foreground_lane_without_relayering_visualizers():
    scene = _source("rendering/quick/qml/DisplayScene.qml")
    host = _source("rendering/quick/widgets/host.py")
    controller = _source("rendering/quick/scene_controller.py")
    osd = _source("rendering/quick/qml/SystemAudioOSDPresentation.qml")
    assert 'objectName: "systemAudioOSDShadowHost"' in scene
    assert 'objectName: "systemAudioOSDForegroundHost"' in scene
    assert scene.index('id: visualizerPresentationLoader') < scene.index('id: systemAudioOSDShadowHost')
    assert scene.index('id: systemAudioOSDForegroundHost') < scene.index('id: retainedContextMenu')
    assert 'z: 29' in scene and 'z: 30' in scene
    assert '_paint_host_for_identity' in host
    assert '_shadow_host_for_identity' in host
    assert 'foreground_host_item=osd_foreground_host_item' in controller
    assert 'foreground_shadow_host_item=osd_shadow_host_item' in controller
    assert 'duration: (osdModel.revealed || osdRoot.customLayoutInputBlocked) ? 170 : 1150' in osd
    assert 'onCustomLayoutInputBlockedChanged:' not in osd
    assert 'QTimer {' not in osd
    assert 'property bool paintMuted: osdModel.muted' in osd
    assert 'function onStateChanged() { speakerGlyph.requestPaint() }' not in osd
    assert 'Timer {' not in osd


def test_osd_semantic_palette_uses_shared_widget_theme_resolver():
    model = _source("rendering/quick/widgets/system_audio_osd.py")
    roles = _source("ui/widget_visual_roles.py")
    assert 'resolve_card_surface_colors(' in model
    assert 'resolve_primary_text_color(' in model
    assert 'resolve_rgba_role(' in model
    assert 'configured_rgba_override(' in model
    assert '"system_audio_osd.accent": "widget.accent"' in roles
    assert '"system_audio_osd.track": "widget.panel"' in roles
    assert 'from ui.widget_theme_active import get_active_widget_theme' in model
