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
