"""Replay teardown must retire its own engine, not globally drain Qt scenes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_offline_replay_cleanup_is_receiver_scoped_and_never_global() -> None:
    replay = (ROOT / "tests/test_visualizer_replay.py").read_text(encoding="utf-8")
    driver = (ROOT / "tools/visualizer_replay/driver.py").read_text(encoding="utf-8")
    assert "def drain_retired_qobjects" not in replay
    assert 'pytestmark = pytest.mark.usefixtures("qt_app")' in replay
    assert "sendPostedEvents(None" not in replay + driver
    assert "engine.deleteLater()" in driver
    assert "QCoreApplication.sendPostedEvents(engine, QEvent.Type.DeferredDelete)" in driver
    assert "engine.thread() == QThread.currentThread()" in driver
