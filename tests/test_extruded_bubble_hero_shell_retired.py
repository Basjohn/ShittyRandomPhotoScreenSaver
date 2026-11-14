"""Hero Shell (and its Hero Across / Hero Height placement) was removed from Extruded Bubble on 14 Nov 2026 at the
operator's request: a saved profile, preset or export that still carries its keys loads without them."""
from __future__ import annotations

import gc
import uuid

from core.settings.visualizer_retired_modes import (
    _RETIRED_VISUALIZER_KEYS,
    strip_retired_visualizer_settings,
)

_KEYS = ("extruded_bubble_hero_shell", "extruded_bubble_hero_across", "extruded_bubble_hero_height")
_PREFIX = "widgets.spotify_visualizer"


def test_hero_keys_are_retired_and_absent_from_canonical_defaults() -> None:
    from core.settings.default_contract import require_canonical_default

    defaults = require_canonical_default(_PREFIX)
    for key in _KEYS:
        assert key in _RETIRED_VISUALIZER_KEYS
        assert key not in defaults


def test_section_and_dotted_input_drop_the_hero_keys() -> None:
    data = {key: 0.5 for key in _KEYS}
    data.update({f"{_PREFIX}.{key}": 0.5 for key in _KEYS})
    data["extruded_bubble_haze"] = 0.25
    assert strip_retired_visualizer_settings(data) == {"extruded_bubble_haze": 0.25}


def test_persisted_profile_with_the_hero_keys_is_repaired_and_cannot_resave_them(tmp_path) -> None:
    from core.settings import SettingsManager

    app = f"HeroShellRetired_{uuid.uuid4().hex}"
    first = SettingsManager(application=app, storage_base_dir=tmp_path)
    widgets = dict(first.get("widgets"))
    section = dict(widgets["spotify_visualizer"])
    for key in _KEYS:
        section[key] = 0.5
    widgets["spotify_visualizer"] = section
    # Write below the manager's normalizing API, as an older build would have.
    first._settings.setValue("widgets", widgets)
    first._settings.sync()
    assert all(first._settings.value("widgets")["spotify_visualizer"][key] == 0.5 for key in _KEYS)
    del first
    gc.collect()

    reopened = SettingsManager(application=app, storage_base_dir=tmp_path)
    assert not set(_KEYS) & set(reopened.get("widgets")["spotify_visualizer"])
    reopened.set("widgets.spotify_visualizer.spectrum_mirrored", True)
    reopened._settings.sync()
    del reopened
    gc.collect()

    final = SettingsManager(application=app, storage_base_dir=tmp_path)
    assert not set(_KEYS) & set(final._settings.value("widgets")["spotify_visualizer"])
