"""Import-free audio listener cost boundaries and explicit risk checks."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_session_listener_has_no_poll_or_callback_com_enumeration():
    listener = (ROOT / "core/media/session_volume_listener.py").read_text(encoding="utf-8")
    bridge = (ROOT / "core/media/audio_qt_wake.py").read_text(encoding="utf-8")
    mailbox = (ROOT / "core/media/audio_event_mailbox.py").read_text(encoding="utf-8")
    owner = (ROOT / "widgets/media_volume_runtime.py").read_text(encoding="utf-8")
    for source in (listener, bridge, mailbox):
        assert "QTimer(" not in source
        assert "single_shot(" not in source
        assert "time.sleep(" not in source
    tree = ast.parse(listener)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in (
                "on_simple_volume_changed", "on_session_disconnected", "_consume"):
            continue
        code = ast.get_source_segment(listener, node) or ""
        assert "GetAllSessions" not in code
        assert "register_notification" not in code
        assert "SetMasterVolume" not in code
    assert "self._start_session_listener()" in owner
    assert "self._pending_volume is not None" in owner
    assert "if abs(bounded - self._level) <= 0.000001:" in owner
    assert "self._read_request_id += 1" in owner
    # Explicit open cost risk: startup/source admission does enumerate on the
    # GUI COM apartment. Never mislabel this source-only gate as measured latency.
    assert "sessions = sessions_factory()" in listener
