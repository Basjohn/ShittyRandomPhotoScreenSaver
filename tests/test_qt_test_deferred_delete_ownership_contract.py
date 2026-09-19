"""Qt test cleanup must not flush unrelated tests' deferred QObject deletions.

A native whole-tree abort occurred at a global DeferredDelete flush in a
DisplayTab listener test after other tests had created QQuick scenes. Keep the
owned-object deletion assertions while preventing that cross-test side effect.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_lifetime_assertions_drain_only_the_qobject_they_retired() -> None:
    expected = {
        "test_widget_glow_settings.py": ("tab", "tab.deleteLater()"),
        "test_qtquick_retained_model_lifetime.py": ("item", "widget.retire()"),
        "test_gmail_runtime.py": ("timer", "leases[1].retire()"),
    }
    for name, (owner, retirement) in expected.items():
        source = (ROOT / "tests" / name).read_text(encoding="utf-8")
        assert retirement in source, name
        assert "sendPostedEvents(None, QEvent.Type.DeferredDelete)" not in source, name
        assert (
            f"QCoreApplication.sendPostedEvents({owner}, QEvent.Type.DeferredDelete)"
            in source
        ), name


def test_glow_subscription_baseline_does_not_retire_foreign_qobjects() -> None:
    source = (ROOT / "tests/test_widget_glow_settings.py").read_text(encoding="utf-8")
    method = source.split(
        "def test_display_tab_widget_theme_subscription_unsubscribes_on_destroy(", 1
    )[1]
    baseline = method.split("before = len(widget_theme_active._listeners)", 1)[0]
    assert "sendPostedEvents" not in baseline
    assert "tab.destroyed" not in method  # real production destroyed->unsubscribe hook
    assert "assert len(widget_theme_active._listeners) == before" in method
