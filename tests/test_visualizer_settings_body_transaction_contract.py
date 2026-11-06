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
        if path.name == "spec_mode_builder.py":
            continue          # builds the buckets the mode specs declare (below)
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

    from core.settings.visualizer_mode_settings import iter_mode_settings

    discovered |= {f"{spec.mode_id}:{bucket.key}" for spec in iter_mode_settings() for bucket in spec.buckets}
    missing = discovered - expected
    assert not missing, f"Visualizer builder bucket(s) missing canonical UI defaults: {sorted(missing)}"


def test_dynamic_accessory_bootstrap_does_not_consult_incompatible_active_mode() -> None:
    """Parked shared accessories acquire persisted state only after compatible placement."""
    source = (ROOT / "ui/tabs/media/builder_scaffold.py").read_text(encoding="utf-8")
    start = source.index("def build_dynamic_collapsible_bucket(")
    end = source.index("\ndef build_mode_scaffold(", start)
    dynamic = source[start:end]
    assert "initial_expanded=False" in dynamic


def test_3d_builder_bucket_identities_are_declared_by_their_current_owners() -> None:
    """Builder/spec bucket identities must resolve to the canonical UI schema.

    The inventory is an extensible code-owned schema, not an immutable list of
    yesterday's bucket names or the operator's currently expanded state.
    """
    import ast

    from core.settings.default_settings import DEFAULT_SETTINGS
    from core.settings.visualizer_mode_settings import require_mode_settings

    canonical = set(DEFAULT_SETTINGS["ui"]["visualizer_bucket_states"])
    for mode in ("extruded_spectrum", "shockwave_grid", "sphere"):
        spec_keys = {f"{mode}:{bucket.key}" for bucket in require_mode_settings(mode).buckets}
        builder = ROOT / "ui" / "tabs" / "media" / f"{mode}_builder.py"
        builder_keys = set()
        if builder.exists():
            tree = ast.parse(builder.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                    continue
                if node.func.id != "build_collapsible_bucket":
                    continue
                args = {kw.arg: kw.value for kw in node.keywords if kw.arg}
                bucket = args.get("bucket_key")
                owner = args.get("mode_key")
                if (isinstance(bucket, ast.Constant) and isinstance(owner, ast.Constant)
                        and owner.value == mode and isinstance(bucket.value, str)):
                    builder_keys.add(f"{mode}:{bucket.value}")
        declared = spec_keys | builder_keys
        assert declared, f"No real UI buckets registered for {mode}"
        assert declared <= canonical, f"Unregistered {mode} bucket identities: {sorted(declared-canonical)}"


