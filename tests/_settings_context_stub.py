"""Shared test double for the canonical Widget-defaults API surface.

The settings migration made the Settings-side helpers
(``_widget_default``/``_default_int``/``_default_float``/``_default_bool``/
``_default_str`` and ``_config_bool``/``_config_int``/``_config_float``/
``_config_str``) read strictly from the canonical Widget defaults authority --
they no longer accept a caller-supplied default. Every one of them derives from
``self._widget_defaults`` (the ``widgets`` sub-tree of the canonical defaults),
so a stub that populates that mapping from the real authority mirrors production
exactly, without pulling in the QWidget/scroll-area/persistence dependencies of
the concrete Settings tabs.

Tests that only need the canonical-default API mix this in; tests that also need
UI widgets add their own control attributes alongside it.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from core.settings.defaults import get_default_settings
from ui.tabs.visualizer_settings_context import VisualizerSettingsContextMixin

_WIDGET_DEFAULTS_CACHE: Dict[str, Dict[str, Any]] | None = None


def canonical_widget_defaults() -> Dict[str, Dict[str, Any]]:
    """Return a deep copy of the canonical ``widgets`` defaults sub-tree."""
    global _WIDGET_DEFAULTS_CACHE
    if _WIDGET_DEFAULTS_CACHE is None:
        widgets = get_default_settings()["widgets"]
        if not isinstance(widgets, dict):
            raise TypeError("canonical defaults are missing the widgets mapping")
        _WIDGET_DEFAULTS_CACHE = widgets
    return deepcopy(_WIDGET_DEFAULTS_CACHE)


class CanonicalWidgetDefaultsStub(VisualizerSettingsContextMixin):
    """Reuse the production canonical-default helpers backed by real defaults.

    Only ``self._widget_defaults`` is required by those helpers, so populating it
    yields the exact production behaviour (fail-loud ``KeyError`` on a missing
    key included) for ``_widget_default`` / ``_default_*`` / ``_config_*``.
    """

    def __init__(self) -> None:
        self._widget_defaults = canonical_widget_defaults()
