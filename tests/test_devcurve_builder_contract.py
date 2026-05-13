from __future__ import annotations

from pathlib import Path


def test_devcurve_builder_uses_widgets_tab_color_default_helper():
    builder_path = Path(__file__).resolve().parents[1] / "ui" / "tabs" / "media" / "devcurve_builder.py"
    src = builder_path.read_text(encoding="utf-8")
    assert "_default_color(" not in src
    assert "_color_from_default(" in src


def test_devcurve_builder_keeps_mode_scaffold_and_bucket_contracts():
    builder_path = Path(__file__).resolve().parents[1] / "ui" / "tabs" / "media" / "devcurve_builder.py"
    src = builder_path.read_text(encoding="utf-8")

    assert 'build_mode_scaffold(' in src
    assert 'mode_key="devcurve"' in src
    assert 'build_collapsible_bucket(' in src
    assert 'bucket_key="shaper"' in src
    assert 'bucket_key="core"' in src
    assert 'bucket_key="foreground_fx"' in src
    assert 'bucket_key="ghost"' in src
