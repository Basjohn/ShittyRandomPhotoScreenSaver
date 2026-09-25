from __future__ import annotations


def test_main_mc_forces_interaction_mode_default(monkeypatch) -> None:
    import main_mc

    calls: list[tuple[str, object]] = []

    class DummySettingsManager:
        def set(self, key, value):
            calls.append((key, value))

    monkeypatch.setattr(main_mc, "SettingsManager", DummySettingsManager)
    monkeypatch.setattr(main_mc, "parse_screensaver_args", lambda: calls.append(("parse", True)))
    def _core_main(*, entrypoint):
        calls.append(("entrypoint", entrypoint))
        return 123

    monkeypatch.setattr(main_mc, "core_main", _core_main)

    result = main_mc.main()

    assert ("input.interaction_mode", True) in calls
    assert ("entrypoint", "main_mc") in calls
    assert result == 123


def test_mc_identity_is_resolved_without_constructing_settings(monkeypatch) -> None:
    import sys

    import core.settings.settings_manager as settings_manager
    from core.mc import is_mc_build

    def _no_manager(*_args, **_kwargs):
        raise AssertionError("is_mc_build must not construct a SettingsManager")

    monkeypatch.setattr(settings_manager.SettingsManager, "__init__", _no_manager)

    monkeypatch.setattr(sys, "argv", ["SRPSS.exe"])
    assert is_mc_build() is False

    monkeypatch.setattr(sys, "argv", ["SRPSS_MC.exe"])
    assert is_mc_build() is True
