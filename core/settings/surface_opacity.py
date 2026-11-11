"""Shared admission and semantic surface-density mapping; never whole-item opacity.

Zero preserves the authored/calibrated recipe. Negative adjustment removes that
fraction of density; positive adjustment fills that fraction of transparency.
The cached Settings adjustment is a process rendering projection, not persistence.
"""
from __future__ import annotations

from collections.abc import Mapping
from math import isfinite

_settings_adjustment = 0.0


def admit_opacity_adjust(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return max(-1.0, min(1.0, number)) if isfinite(number) else 0.0


def adjusted_surface_density(density: float, adjustment: object) -> float:
    density = max(0.0, min(1.0, float(density)))
    amount = admit_opacity_adjust(adjustment)
    return density * (1.0 + amount) if amount < 0.0 else density + (1.0 - density) * amount


def resolve_opacity_adjust(widgets: Mapping | None, target: str) -> float:
    if target not in ("settings", "widget"):
        raise ValueError(f"Unknown surface-opacity target: {target}")
    values = widgets.get("global", {}) if isinstance(widgets, Mapping) else {}
    return admit_opacity_adjust(values.get(f"{target}_opacity_adjust")) if isinstance(values, Mapping) else 0.0


def settings_opacity_adjust() -> float:
    return _settings_adjustment


def project_settings_opacity_adjust(value: object) -> bool:
    """Cache one admitted persisted value at an existing Settings application edge."""
    global _settings_adjustment
    admitted = admit_opacity_adjust(value)
    if admitted == _settings_adjustment:
        return False
    _settings_adjustment = admitted
    return True


# Per-material calibration of combined surface density (Smoked applies to dark surfaces only).
# Runtime cards bound their dark-ink legibility panel with the same calibration
# (rendering/quick/qml/SurfaceContrast.js keeps an equal table; tests check the two).
SETTINGS_DENSITY_BASELINE: dict[str, float] = {"acrylic": -.10, "frosted": -.20, "mica": -.20,
                                               "glass": .10, "smoked": -.10}


def settings_surface_density(mode: str, density: float, *, dark_surface: bool = True,
                             adjustment: float | None = None) -> float:
    """Calibrate combined density; callers decide the actual composition boundary."""
    baseline = 0.0 if mode == "smoked" and not dark_surface else SETTINGS_DENSITY_BASELINE.get(mode, 0.0)
    calibrated = adjusted_surface_density(density, baseline)
    return adjusted_surface_density(calibrated, _settings_adjustment if adjustment is None else adjustment)


def settings_surface_alpha(mode: str, alpha: int, *, dark_surface: bool = True) -> int:
    """Map one independent fill; alpha-zero structural surfaces remain absent."""
    return 0 if alpha == 0 else round(255.0 * settings_surface_density(mode, alpha / 255.0,
                                                                    dark_surface=dark_surface))


def is_surface_role(token: str) -> bool:
    """Semantic fills only; typography, edges, shadows and slider ink are independent."""
    return (token == "window.dialog_glass" or token.endswith(".surface")
            or token.endswith("_surface")) and not token.startswith(("text.", "slider."))
