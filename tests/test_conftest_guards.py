"""The suite's own guards (tests/conftest.py): no real modal popup and no real display window reach the operator's
screen, including through modules imported lazily inside a test or inside production code.

7 Nov: a Studio that failed to open (no GL under the offscreen platform) reported through a real StyledPopup, whose
exec() blocked the test process for minutes. Unguarded, the same popup shows on the operator's screen.
"""
from __future__ import annotations

import sys

import pytest


def _conftest():
    return next(module for module in list(sys.modules.values())
                if getattr(module, "_POPUP_GUARD", None) is not None and hasattr(module, "_guard_on_import"))


def test_an_unpatched_popup_is_answered_as_dismissed_and_recorded_not_shown(qt_app):
    from ui.styled_popup import StyledPopup

    guard = _conftest()._POPUP_GUARD
    popup = StyledPopup(None, "Studio Unavailable", "The Studio could not open.", icon_type="error",
                        buttons=[("OK", "ok")])
    try:
        assert popup.exec() == 0                     # returns at once: no modal loop, nothing on screen
        assert not popup.isVisible()
        assert guard["shown"] == ["Studio Unavailable: The Studio could not open."]
    finally:
        guard["shown"].clear()                       # this test expects the popup; the teardown check must not fail
        popup.deleteLater()


def test_a_test_that_patches_exec_owns_the_popup(qt_app, monkeypatch):
    from ui.styled_popup import StyledPopup

    answers = []
    monkeypatch.setattr(StyledPopup, "exec", lambda self: answers.append(self._title) or 1)
    popup = StyledPopup(None, "Unsaved Preset Changes", "Keep them?", buttons=[("Keep", "keep")])
    try:
        assert popup.exec() == 1 and answers == ["Unsaved Preset Changes"]
        assert _conftest()._POPUP_GUARD["shown"] == []
    finally:
        popup.deleteLater()


def test_a_module_imported_during_a_test_is_guarded_before_its_first_use(tmp_path, monkeypatch):
    """The guard installs on import itself, so a lazy ``from ui.styled_popup import ...`` inside production code is
    guarded too (negative control: a module that is never registered is left alone)."""
    conftest = _conftest()
    (tmp_path / "srpss_guard_probe_registered.py").write_text("class Target:\n    value = 'real'\n")
    (tmp_path / "srpss_guard_probe_unregistered.py").write_text("class Target:\n    value = 'real'\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    def install(module):
        module.Target.value = "guarded"

    monkeypatch.setitem(conftest._POST_IMPORT_GUARDS, "srpss_guard_probe_registered", install)
    try:
        import srpss_guard_probe_registered as registered
        import srpss_guard_probe_unregistered as unregistered
        assert registered.Target.value == "guarded"
        assert unregistered.Target.value == "real"
    finally:
        sys.modules.pop("srpss_guard_probe_registered", None)
        sys.modules.pop("srpss_guard_probe_unregistered", None)


def test_both_production_guards_are_registered():
    conftest = _conftest()
    assert {"rendering.quick.window", "ui.styled_popup"} <= set(conftest._POST_IMPORT_GUARDS)
    if "ui.styled_popup" in sys.modules:
        assert getattr(sys.modules["ui.styled_popup"].StyledPopup.exec, "_srpss_guard", False)
    if "rendering.quick.window" in sys.modules:
        assert getattr(sys.modules["rendering.quick.window"].QuickDisplayWindow.show_on_screen, "_srpss_guard", False)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
