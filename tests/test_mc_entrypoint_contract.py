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
