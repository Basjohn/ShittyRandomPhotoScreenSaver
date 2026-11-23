from __future__ import annotations


def test_main_dashboard_forces_interaction_mode_default(monkeypatch) -> None:
    import main_dashboard

    calls: list[tuple[str, object]] = []

    class DummySettingsManager:
        def set(self, key, value):
            calls.append((key, value))

    monkeypatch.setattr(main_dashboard, "SettingsManager", DummySettingsManager)
    monkeypatch.setattr(main_dashboard, "parse_screensaver_args", lambda: calls.append(("parse", True)))
    def _core_main(*, entrypoint):
        calls.append(("entrypoint", entrypoint))
        return 123

    monkeypatch.setattr(main_dashboard, "core_main", _core_main)

    result = main_dashboard.main()

    assert ("input.interaction_mode", True) in calls
    assert ("entrypoint", "main_dashboard") in calls
    assert result == 123


def test_dashboard_identity_is_resolved_without_constructing_settings(monkeypatch) -> None:
    import sys

    import core.settings.settings_manager as settings_manager
    from core.dashboard import is_dashboard_build

    def _no_manager(*_args, **_kwargs):
        raise AssertionError("is_dashboard_build must not construct a SettingsManager")

    monkeypatch.setattr(settings_manager.SettingsManager, "__init__", _no_manager)

    monkeypatch.setattr(sys, "argv", ["SRPSS.exe"])
    assert is_dashboard_build() is False

    monkeypatch.setattr(sys, "argv", ["SRPSS_Dashboard.exe"])
    assert is_dashboard_build() is True
