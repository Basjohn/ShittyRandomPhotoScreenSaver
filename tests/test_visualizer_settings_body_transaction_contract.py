from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_lazy_visualizer_body_factory_cleans_failed_qt_body_before_reraise() -> None:
    source = (ROOT / "ui/tabs/widgets_tab_media.py").read_text(encoding="utf-8")
    factory = source[source.index("    def _factory(mode_id):"):source.index("    widgets_value =", source.index("    def _factory(mode_id):"))]
    assert "except Exception:" in factory
    assert "retire_body(mode_id, failed)" in factory
    assert "controls_layout.removeWidget(failed)" in factory
    assert "raise\n" in factory


def test_mode_scaffold_marks_bodies_and_does_not_flash_custom_controls_for_preset_one() -> None:
    source = (ROOT / "ui/tabs/media/builder_scaffold.py").read_text(encoding="utf-8")
    assert 'body_object_name = f"visualizer_mode_body_{mode_key}"' in source
    assert "candidate.objectName() == body_object_name" in source
    assert "parent_layout.removeWidget(stale)" in source
    assert "preset_slider.preset_index() == preset_slider.custom_index()" in source
    assert "_handle_preset_visibility(True)" not in source


def test_collapsible_builder_bucket_keys_are_registered_in_canonical_ui_defaults() -> None:
    """Every persisted bucket used by a lazy builder must exist canonically.

    This stays Qt-free on purpose so a Settings bucket rename/addition cannot
    escape CI merely because PySide6 is unavailable in the test environment.
    """
    import ast

    from core.settings.default_settings import DEFAULT_SETTINGS

    expected = set(DEFAULT_SETTINGS["ui"]["visualizer_bucket_states"])
    discovered: set[str] = set()
    builders_root = ROOT / "ui" / "tabs" / "media"
    for path in builders_root.glob("*_builder.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "build_collapsible_bucket":
                continue
            keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            mode_node = keywords.get("mode_key")
            bucket_node = keywords.get("bucket_key")
            assert isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str), path
            assert isinstance(bucket_node, ast.Constant) and isinstance(bucket_node.value, str), path
            discovered.add(f"{mode_node.value}:{bucket_node.value}")

    missing = discovered - expected
    assert not missing, f"Visualizer builder bucket(s) missing canonical UI defaults: {sorted(missing)}"


def test_sphere_bucket_defaults_match_current_isolated_builder_contract() -> None:
    from core.settings.default_settings import DEFAULT_SETTINGS

    sphere_keys = {
        key
        for key in DEFAULT_SETTINGS["ui"]["visualizer_bucket_states"]
        if key.startswith("sphere:")
    }
    assert sphere_keys == {
        "sphere:appearance",
        "sphere:particle_flow",
        "sphere:reaction",
        "sphere:rotation",
        "sphere:effects",
    }


def test_sphere_builder_default_lookups_exist_in_canonical_visualizer_defaults() -> None:
    """Keep the isolated Sphere builder's canonical-default lookups schema-complete."""
    import ast

    from core.settings.default_settings import DEFAULT_SETTINGS

    path = ROOT / "ui" / "tabs" / "media" / "sphere_builder.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    looked_up: set[str] = set()
    default_methods = {"_default_bool", "_default_float", "_default_str", "_color_from_default"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in default_methods or len(node.args) < 2:
            continue
        section, key = node.args[0], node.args[1]
        if not (
            isinstance(section, ast.Constant)
            and section.value == "spotify_visualizer"
            and isinstance(key, ast.Constant)
            and isinstance(key.value, str)
        ):
            continue
        looked_up.add(key.value)

    canonical = DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]
    missing = looked_up - set(canonical)
    assert not missing, f"Sphere builder canonical default lookup(s) missing: {sorted(missing)}"
    assert looked_up, "Sphere builder default lookup contract unexpectedly discovered nothing"
