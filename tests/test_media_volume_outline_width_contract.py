"""Import-free contract for Media's user-adjustable application-volume outline.

Runtime Qt paint/Settings round-trips remain mandatory on Windows. These checks
cover canonical defaults, config projection and every active QML outline path.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_volume_width_default_is_existing_two_point_five_px() -> None:
    tree = ast.parse(source("core/settings/default_settings.py"))
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "DEFAULT_SETTINGS" for target in node.targets)
    )
    defaults = ast.literal_eval(assignment.value)
    assert defaults["widgets"]["media"]["spotify_volume_border_width_px"] == 2.5


def test_typed_and_retained_configurations_round_trip_volume_outline_width() -> None:
    typed = source("core/settings/models/_widget_settings.py")
    model = source("rendering/quick/widgets/media.py")
    assert 'spotify_volume_border_width_px: float = float(_default(' in typed
    assert 'spotify_volume_border_width_px=float(get_value("spotify_volume_border_width_px"))' in typed
    assert 'f"{prefix}.spotify_volume_border_width_px": self.spotify_volume_border_width_px' in typed
    assert 'app_volume_border_width_px: float' in model
    assert 'merged["spotify_volume_border_width_px"]' in model
    assert 'float(defaults["spotify_volume_border_width_px"]), 0.0, 8.0' in model
    assert 'def appVolumeBorderWidth(self) -> float:' in model
    assert 'return float(self.config.app_volume_border_width_px)' in model


def test_media_settings_volume_width_control_and_save_reload() -> None:
    ui = source("ui/tabs/widgets_tab_media.py")
    assert 'tab.media_volume_outline_width = QDoubleSpinBox()' in ui
    assert 'tab.media_volume_outline_width.setRange(0.0, 8.0)' in ui
    assert 'tab.media_volume_outline_width.setSingleStep(0.5)' in ui
    assert 'tab.media_volume_outline_width.valueChanged.connect(tab._save_settings)' in ui
    assert "tab._config_float('media', media_config, 'spotify_volume_border_width_px')" in ui
    assert "'spotify_volume_border_width_px': tab.media_volume_outline_width.value()" in ui


def test_qml_all_four_outline_strokes_obey_one_width_with_zero_disabled() -> None:
    qml = source("rendering/quick/qml/MediaPresentation.qml")
    track = qml.split('id: appVolumeTrack\n', 1)[1].split('objectName: "mediaAppVolumeInputArea"', 1)[0]
    width_expr = 'mediaRoot.scaleAwareStrokeWidth(mediaRoot.mediaModel.appVolumeBorderWidth)'
    assert track.count(width_expr) == 4
    assert 'mediaRoot.scaleAwareStrokeWidth(2.5)' not in track
    assert 'height > 0.0' in track
    overlay = source("rendering/quick/qml/OverlayWidget.qml")
    assert 'if (baseWidth <= 0.0)\n            return 0.0' in overlay
    # Material outline softening is separate from width; no unguarded overlap.
    assert 'cardBorderMaterialActive ? 0.8 : 1.0' in qml
    assert 'active: mediaRoot.cardBorderMaterialActive' in track


def test_m4_theme_semantic_migration_is_planned_not_premature() -> None:
    plan = source("Current_Plan.md")
    m4 = plan.split('**M4 Unified Appearance Theme', 1)[1].split('### 1B.9', 1)[0]
    assert 'media.volume.outline.width' in m4
    assert 'default value must inherit the theme' in m4
    assert 'Preserve non-default user-authored widths' in m4
