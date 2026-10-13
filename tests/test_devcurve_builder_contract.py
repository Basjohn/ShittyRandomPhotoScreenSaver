from __future__ import annotations

from pathlib import Path


def test_devcurve_builder_uses_widgets_tab_color_default_helper():
    builder_path = Path(__file__).resolve().parents[1] / "ui" / "tabs" / "media" / "devcurve_builder.py"
    src = builder_path.read_text(encoding="utf-8")
    assert "_default_color(" not in src
    assert "_color_from_default(" in src


def test_devcurve_builder_keeps_mode_scaffold_and_bucket_contracts():
    from core.settings.visualizer_mode_settings import Custom, require_mode_settings

    builder_path = Path(__file__).resolve().parents[1] / "ui" / "tabs" / "media" / "devcurve_builder.py"
    src = builder_path.read_text(encoding="utf-8")

    assert 'build_spec_mode_ui(tab, parent_layout, "devcurve")' in src
    spec = require_mode_settings("devcurve")
    assert [(bucket.key, bucket.advanced) for bucket in spec.buckets] == [
        ("shaper", False), ("core", False), ("foreground_fx", False), ("ghost", True),
    ]
    custom = next(entry for entry in spec.entries if isinstance(entry, Custom))
    assert custom.build == "ui.tabs.media.devcurve_builder:build_devcurve_layers"
    assert all(control.logical for control in spec.controls)
