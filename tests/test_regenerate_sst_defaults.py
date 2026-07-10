from __future__ import annotations

from pathlib import Path

from tools import regenerate_sst_defaults as module


def test_sst_regeneration_routes_every_settings_write_to_isolated_storage(
    tmp_path,
    monkeypatch,
) -> None:
    storage_root = tmp_path / "isolated-settings"
    docs_root = tmp_path / "docs"
    created: list[tuple[str, Path]] = []

    class _FakeSettingsManager:
        def __init__(self, *, organization, application, storage_base_dir) -> None:
            assert organization == "UnitTest"
            assert storage_base_dir == storage_root
            self.application = application
            created.append((application, storage_base_dir))

        def reset_to_defaults(self) -> None:
            return None

        def set(self, _key, _value) -> None:
            return None

        def save(self) -> None:
            return None

        def export_to_sst(self, path: str) -> bool:
            Path(path).write_text(self.application, encoding="utf-8")
            return True

    monkeypatch.setattr(module, "SettingsManager", _FakeSettingsManager)

    outputs = module.regenerate_sst_defaults(
        docs_root,
        organization="UnitTest",
        storage_base_dir=storage_root,
    )

    assert [application for application, _root in created] == [
        "Screensaver",
        "Screensaver_MC",
    ]
    assert all(root == storage_root for _application, root in created)
    assert all(path.parent == docs_root and path.exists() for path in outputs)
