"""SC3: the unread Spectrum fill/border link state is forward-stripped everywhere.

Fill and Border remain independent controls; no input path may reinstate the
retired link leaf.
"""
from __future__ import annotations

import gc
import uuid

from core.settings.visualizer_retired_modes import (
    _RETIRED_VISUALIZER_KEYS,
    strip_retired_visualizer_settings,
)

_KEY = "spectrum_link_fill_border"
_PREFIX = "widgets.spotify_visualizer"


def test_link_state_is_retired_and_absent_from_canonical_defaults() -> None:
    from core.settings.default_contract import require_canonical_default

    assert _KEY in _RETIRED_VISUALIZER_KEYS
    assert _KEY not in require_canonical_default(_PREFIX)


def test_section_and_dotted_input_drop_the_link_leaf() -> None:
    cleaned = strip_retired_visualizer_settings(
        {_KEY: True, f"{_PREFIX}.{_KEY}": True, "spectrum_mirrored": False}
    )
    assert cleaned == {"spectrum_mirrored": False}


def test_typed_model_neither_reads_nor_serializes_the_link_leaf() -> None:
    from core.settings.models import SpotifyVisualizerSettings

    model = SpotifyVisualizerSettings.from_mapping({_KEY: True, "mode": "spectrum"})
    assert not hasattr(model, _KEY)
    serialized = model.to_dict()
    assert not any(key.endswith(_KEY) for key in serialized)


def test_persisted_profile_with_the_link_leaf_is_repaired_and_cannot_resave_it(tmp_path) -> None:
    from core.settings import SettingsManager

    app = f"SpectrumLinkRetired_{uuid.uuid4().hex}"
    first = SettingsManager(application=app, storage_base_dir=tmp_path)
    widgets = dict(first.get("widgets"))
    section = dict(widgets["spotify_visualizer"])
    section[_KEY] = True
    widgets["spotify_visualizer"] = section
    # Write below the manager's normalizing API, as an older build would have.
    first._settings.setValue("widgets", widgets)
    first._settings.sync()
    assert first._settings.value("widgets")["spotify_visualizer"][_KEY] is True
    del first
    gc.collect()

    reopened = SettingsManager(application=app, storage_base_dir=tmp_path)
    assert _KEY not in reopened.get("widgets")["spotify_visualizer"]
    reopened.set("widgets.spotify_visualizer.spectrum_mirrored", True)
    reopened._settings.sync()
    del reopened
    gc.collect()

    final = SettingsManager(application=app, storage_base_dir=tmp_path)
    assert _KEY not in final._settings.value("widgets")["spotify_visualizer"]
