"""V7a contracts for the WidgetsTab-free Visualizer Settings owner seam."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from ui.tabs.visualizer_settings_context import VisualizerSettingsContextMixin


class _MemorySettings:
    def __init__(self, initial=None):
        self.data = dict(initial or {})

    def get(self, key, default=None):
        return deepcopy(self.data.get(key, default))

    def set(self, key, value):
        self.data[key] = deepcopy(value)


class _ContextHarness(VisualizerSettingsContextMixin):
    def __init__(self):
        self._settings = _MemorySettings()
        self._widget_defaults = {}
        self._widget_section_descriptors = ()
        self._scroll_area = None
        self._loading = False
        self._initialize_visualizer_settings_context_state()


def test_context_module_has_no_widgetstab_import_dependency():
    """The extracted owner seam must remain usable without importing WidgetsTab."""
    source = Path("ui/tabs/visualizer_settings_context.py").read_text(encoding="utf-8")
    assert "ui.tabs.widgets_tab" not in source
    assert "from ui.tabs.widgets_tab" not in source


def test_unhydrated_visualizer_merge_preserves_stored_mapping_exactly():
    owner = _ContextHarness()
    existing = {
        "media": {"enabled": True},
        "spotify_visualizer": {
            "mode": "spectrum",
            "preset_spectrum": 0,
            "spectrum_drop_speed": 1.85,
            "enabled_modes": ["spectrum", "bubble"],
        },
    }
    before = deepcopy(existing)

    saved, mode, preset = owner._merge_visualizer_section_save(
        existing,
        {"mode": "bubble", "bubble_count": 99},
        hydrated=False,
    )

    assert existing == before
    assert saved == before["spotify_visualizer"]
    assert mode == "spectrum"
    assert preset == 0


def test_hydrated_visualizer_merge_keeps_inactive_mode_state():
    owner = _ContextHarness()
    existing = {
        "media": {"enabled": True},
        "spotify_visualizer": {
            "mode": "spectrum",
            "preset_spectrum": 0,
            "preset_bubble": 0,
            "spectrum_drop_speed": 1.85,
            "enabled_modes": ["spectrum", "bubble"],
        },
    }

    saved, mode, preset = owner._merge_visualizer_section_save(
        existing,
        {"mode": "bubble", "preset_bubble": 0},
        hydrated=True,
    )

    assert existing["spotify_visualizer"] is saved
    assert saved["spectrum_drop_speed"] == 1.85
    assert saved["mode"] == "bubble"
    assert set(saved["enabled_modes"]) == {"spectrum", "bubble"}
    assert mode == "bubble"
    assert preset == 0
