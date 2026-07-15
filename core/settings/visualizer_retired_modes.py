"""Forward-only cleanup for retired visualizer modes."""
from __future__ import annotations

from typing import Any, Dict, Mapping


RETIRED_VISUALIZER_MODE_IDS = frozenset({"blob"})
_RETIRED_VISUALIZER_KEYS = frozenset({"preset_blob"})
_RETIRED_VISUALIZER_PREFIXES = ("blob_",)


def strip_retired_visualizer_settings(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, Any]:
    """Migrate retired selections and remove their owned settings.

    Both section-local and dotted mappings pass through this helper during
    settings, import, preset, and generated-default normalization.
    """
    if not isinstance(data, Mapping):
        return {}

    cleaned: Dict[str, Any] = {}
    dotted_prefix = f"{prefix}."
    for key, value in data.items():
        key_text = str(key)
        leaf = key_text[len(dotted_prefix):] if key_text.startswith(dotted_prefix) else key_text
        if leaf in _RETIRED_VISUALIZER_KEYS or leaf.startswith(_RETIRED_VISUALIZER_PREFIXES):
            continue
        if leaf == "mode" and str(value or "").strip().lower() in RETIRED_VISUALIZER_MODE_IDS:
            from core.settings.visualizer_mode_registry import get_default_visualizer_mode_id

            cleaned[key] = get_default_visualizer_mode_id()
            continue
        cleaned[key] = value
    return cleaned
