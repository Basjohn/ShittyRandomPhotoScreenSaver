"""Source-level guards for the one-owner Core Audio runtime migration."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_media_source_has_one_event_owner_and_no_legacy_poll_or_endpoint():
    owner = (ROOT / "widgets/system_mute_runtime.py").read_text(encoding="utf-8")
    source = (ROOT / "core/media/audio_shared_source.py").read_text(encoding="utf-8")
    assert "SharedCoreAudioBackend" in owner
    assert "backend.start(self._on_event_state)" in owner
    assert "backend.stop()" in owner
    assert "single_shot" not in owner
    assert "_POLL_INTERVAL_MS" not in owner
    assert "from core.media import system_mute" not in owner
    # A reversible Foundry cleanup may leave the retired module on disk until
    # the operator selects move_to_deleteme. Presence is not runtime admission.
    assert "SystemMuteController" not in owner
    assert "_SESSION_BY_THREAD" in source
    assert "source.subscribe(receive)" in source
    assert "source.unsubscribe(subscriber_id)" in source


def test_native_core_audio_registration_has_no_environment_variable_gate():
    native = (ROOT / "tests/test_core_audio_callback_native_probe.py").read_text(
        encoding="utf-8"
    )
    assert "@pytest.mark.skipif(sys.platform != \"win32\"" in native
    assert "SRPSS_CORE_AUDIO_NATIVE_GATE" not in native
    assert "os.environ" not in native


def test_callback_handover_guards_actions_and_no_duplicate_wake():
    session = (ROOT / "core/media/audio_event_session.py").read_text(encoding="utf-8")
    mailbox = (ROOT / "core/media/audio_event_mailbox.py").read_text(encoding="utf-8")
    assert "accepts_endpoint_actions" in session
    assert "not self._handover_pending" in mailbox
    assert "_last_delivered" in mailbox
    assert "scalar = round(scalar, 6)" in mailbox
