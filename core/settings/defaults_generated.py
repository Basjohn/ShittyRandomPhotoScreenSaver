"""Legacy compatibility mirror for canonical defaults.

Historically this file carried a copied generated payload. It now re-exports
the public settings-defaults entrypoint so any legacy imports cannot drift
away from the settings system's canonical source.
"""
from __future__ import annotations

from core.settings.defaults import CANONICAL_DEFAULTS as DEFAULT_SETTINGS
