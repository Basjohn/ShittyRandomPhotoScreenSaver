from __future__ import annotations

from pathlib import Path


def test_devcurve_builder_uses_widgets_tab_color_default_helper():
    builder_path = Path(__file__).resolve().parents[1] / "ui" / "tabs" / "media" / "devcurve_builder.py"
    src = builder_path.read_text(encoding="utf-8")
    assert "_default_color(" not in src
    assert "_color_from_default(" in src
