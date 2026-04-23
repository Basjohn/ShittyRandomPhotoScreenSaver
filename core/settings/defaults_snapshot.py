"""Derived defaults snapshot artifact.

This module intentionally stays tiny so the canonical defaults entrypoint in
`core.settings.defaults` remains authoritative. Snapshot consumers should treat
`DEFAULTS` as a sanitized derivative for docs/export parity, not a second
editable settings baseline.
"""
from __future__ import annotations

from core.settings.defaults_snapshot_builder import build_defaults_snapshot

DEFAULTS = build_defaults_snapshot()
