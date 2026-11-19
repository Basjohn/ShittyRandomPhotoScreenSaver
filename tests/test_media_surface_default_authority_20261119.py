"""Media transport surface must never introduce a second product-default authority.

This catches the runtime and lazy-save fallback regression detected by the
repository-wide defaults-authority audit. The selected theme material remains
owned by widgets.global, while the legacy Media key is preserved for old profiles.
"""
from __future__ import annotations

from pathlib import Path

from core.settings.default_contract import require_canonical_default
from core.settings.defaults_authority_audit import audit_defaults_authority


ROOT = Path(__file__).resolve().parents[1]


def test_media_transport_material_has_canonical_default() -> None:
    value = require_canonical_default("widgets.media.controls_surface_material")
    assert isinstance(value, str)
    assert value.strip()


def test_media_transport_projection_and_lazy_saver_use_canonical_defaults() -> None:
    # The source check is intentionally global: a later settings refactor must
    # not relocate a second fallback into another presentation or save module.
    issues = audit_defaults_authority(ROOT)
    assert not issues, "\n".join(issue.render() for issue in issues)


def test_legacy_media_value_remains_preserved_through_lazy_save() -> None:
    saver = (ROOT / "ui/tabs/widgets_tab_media.py").read_text(encoding="utf-8")
    projection = (ROOT / "rendering/quick/widgets/media.py").read_text(encoding="utf-8")
    assert "tab._default_str('media', 'controls_surface_material')" in saver
    assert 'merged["controls_surface_material"]' in projection
    assert "get('controls_surface_material', 'inherit')" not in saver
    assert 'get("controls_surface_material", "inherit")' not in projection
