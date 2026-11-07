"""The Studio shows the same mode names as Settings and Guided Setup.

The mode registry's ``display_name`` is the one user-facing name source: the Studio's switcher entry,
header (schema title) and window title (adapter title) all derive from it, never from a second hand-typed
copy (Docs/Audits/Semantic_Naming_Audit_2026-11-07.md section 2.3). Names are compared with the registry,
never with literal wording, so the operator can rename a mode in the registry alone.
"""
from __future__ import annotations

import pytest

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from ui.studio.registry import create_adapter, studio_modes

STUDIO_MODES = tuple(entry.mode_id for entry in studio_modes())


@pytest.mark.parametrize("mode_id", STUDIO_MODES)
def test_every_studio_name_is_the_registry_display_name(qt_app, mode_id):
    name = get_visualizer_mode_descriptor(mode_id).display_name
    entry = next(entry for entry in studio_modes() if entry.mode_id == mode_id)
    adapter = create_adapter(mode_id)
    assert entry.title == name                                   # the switcher
    assert adapter.title == f"{name} Studio"                     # the window title
    assert adapter.schema().title == f"{name} Studio"            # the header
