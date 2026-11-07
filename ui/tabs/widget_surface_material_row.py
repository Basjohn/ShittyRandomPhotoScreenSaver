"""The per-widget Surface Material row (Docs/Architecture/Card_Surface_Materials.md, section 4).

One shared control for every card family page: **Inherit** (the baseline set in
Widgets -> General -> Style Overrides, by default the active Widget Theme's material) or an
explicit material that beats it. The value is the
canonical ``widgets.<section>.surface_material`` key, so a page save keeps it even when the row
is not built; the row joins the WidgetsTab's existing descriptor load and save paths through
``sync_surface_material_rows`` and ``apply_surface_material_rows``. No timer, no Settings read
outside those edges.
"""
from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QHBoxLayout

from rendering.quick.widgets.surface_material import (
    INHERIT,
    SURFACE_MATERIALS,
    SURFACE_MATERIAL_LABELS,
    normalize_surface_material,
)
from ui.widgets import StyledComboBox


def add_surface_material_row(tab: Any, row: QHBoxLayout, section: str) -> StyledComboBox:
    """Fill ``row`` with the Surface Material combo for widget section ``section``."""

    combo = StyledComboBox()
    combo.setFixedWidth(192)
    combo.addItem("Inherit", INHERIT)
    for material in SURFACE_MATERIALS:
        combo.addItem(SURFACE_MATERIAL_LABELS[material], material)
    combo.setToolTip(
        "This card's surface. Inherit follows Widgets > General > Style Overrides > Surface "
        "Material (by default the Widget Theme's own material); any other choice wins for "
        "this card only."
    )
    combo.setObjectName(f"surfaceMaterialCombo_{section}")
    _select(combo, INHERIT)
    combo.currentIndexChanged.connect(lambda _index, owner=tab: owner._save_settings())
    row.addWidget(combo)
    row.addStretch()
    rows = getattr(tab, "_surface_material_rows", None)
    if rows is None:
        rows = {}
        tab._surface_material_rows = rows
    rows[str(section)] = combo
    return combo


def _select(combo: StyledComboBox, value: object) -> None:
    index = combo.findData(normalize_surface_material(value, allow_inherit=True) or INHERIT)
    blocker = QSignalBlocker(combo)
    combo.setCurrentIndex(max(0, index))
    del blocker


def sync_surface_material_rows(tab: Any, widgets_config: Mapping[str, Any]) -> None:
    """Descriptor load edge: show each built row's stored value (``inherit`` when absent)."""

    rows = getattr(tab, "_surface_material_rows", None) or {}
    loaded = getattr(tab, "_surface_material_loaded", None)
    if loaded is None:
        loaded = set()
        tab._surface_material_loaded = loaded
    for section, combo in rows.items():
        values = widgets_config.get(section, {}) if isinstance(widgets_config, Mapping) else {}
        value = values.get("surface_material", INHERIT) if isinstance(values, Mapping) else INHERIT
        _select(combo, value)
        loaded.add(section)


def apply_surface_material_rows(tab: Any, section_results: MutableMapping[str, Any]) -> None:
    """Save edge: write each loaded row into its section's save result (only built + loaded rows)."""

    rows = getattr(tab, "_surface_material_rows", None) or {}
    loaded = getattr(tab, "_surface_material_loaded", None) or set()
    for section, combo in rows.items():
        result = section_results.get(section)
        if section not in loaded or not isinstance(result, MutableMapping):
            continue
        result["surface_material"] = normalize_surface_material(
            combo.currentData(), allow_inherit=True) or INHERIT


__all__ = ["add_surface_material_row", "apply_surface_material_rows", "sync_surface_material_rows"]
