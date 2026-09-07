"""Pre-migration vs current settings-defaults completeness/diff harness.

Strategy-B oracle. Compares the known-good *pre-settings-migration* canonical
defaults (a reference tree, default ``deleteme/PreSettings``) against the current
canonical authority, and verifies every runtime-resolvable key still has a
canonical default. Non-interactive, side-effect-free, safe to re-run; also backs a
regression test.

Usage:
    python tools/settings_migration_audit.py [--ref deleteme/PreSettings] [--json]

Report sections:
  1. DROPPED   canonical keys present pre-migration, absent now (candidate
     recover-from-git unless explicitly retired).
  2. ADDED     keys new since pre-migration (informational).
  3. CHANGED   values that differ (informational; review for silent drift).
  4. RESOLVE   runtime-resolvable keys (descriptors + per-mode x key) with no
     canonical default and not derivable-by-design.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Keys intentionally retired by the sanitation (dropping them is correct, not a
# regression). Extend as retirements are confirmed against Current_Plan.
KNOWN_RETIRED_SUFFIXES: Tuple[str, ...] = (
    "_growth",
)
KNOWN_RETIRED_KEYS: frozenset[str] = frozenset(
    {
        # Verified unreferenced in current source (dead legacy visualizer keys the
        # sanitation correctly removed; confirmed via repo-wide grep 2026-09-07).
        "widgets.spotify_visualizer.osc_glow_size",
        "widgets.spotify_visualizer.sine_glow_size",
        "widgets.spotify_visualizer.sine_line1_color",
    }
)

# Runtime/session state that pre-migration wrongly stored inside DEFAULT_SETTINGS.
# Product defaults must not carry user backups, saved presets, or session UI
# state, so the migration removing these is CORRECT -- they are not lost defaults.
RUNTIME_STATE_PREFIXES: Tuple[str, ...] = (
    "custom_preset_backup.",
    "visualizer_custom_presets.",
    "widgets.custom_layout_restore.",
    "ui.tab_state.",
    "ui.last_tab_scroll.",
    "ui.last_tab_index",
    "ui.dialog_geometry.",
    "ui.visualizer_scroll_positions.",
    "transitions.last_random_choice",
    "transitions.random_choice",
    "transitions.wipe.last_direction",
    "preset",
)


def _is_runtime_state(key: str) -> bool:
    return any(key == p or key.startswith(p) for p in RUNTIME_STATE_PREFIXES)


def _load_reference_default_settings(ref_root: Path) -> Dict[str, Any]:
    """Exec the reference tree's default_settings.py in isolation and return
    its DEFAULT_SETTINGS literal (no package import, so it cannot collide with
    the live modules)."""
    path = ref_root / "core" / "settings" / "default_settings.py"
    if not path.is_file():
        raise FileNotFoundError(f"reference default_settings.py not found: {path}")
    namespace: Dict[str, Any] = {"__name__": "_ref_default_settings", "__file__": str(path)}
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    exec(code, namespace)  # noqa: S102 - trusted local reference tree
    defaults = namespace.get("DEFAULT_SETTINGS")
    if not isinstance(defaults, dict):
        raise TypeError("reference DEFAULT_SETTINGS is not a dict")
    return defaults


def _flatten(mapping: Any, prefix: str = "") -> Dict[str, Any]:
    """Flatten nested mappings to dotted leaf paths (scalars/lists are leaves)."""
    out: Dict[str, Any] = {}
    if isinstance(mapping, dict):
        for key, value in mapping.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                out.update(_flatten(value, dotted))
            else:
                out[dotted] = value
    return out


def _is_retired(key: str) -> bool:
    leaf = key.rsplit(".", 1)[-1]
    if key in KNOWN_RETIRED_KEYS:
        return True
    return any(leaf.endswith(suffix) for suffix in KNOWN_RETIRED_SUFFIXES)


def diff_canonical_defaults(ref_root: Path) -> Dict[str, Any]:
    from core.settings.default_contract import get_raw_default_settings

    ref = _flatten(_load_reference_default_settings(ref_root))
    cur = _flatten(get_raw_default_settings())

    ref_keys, cur_keys = set(ref), set(cur)
    dropped = sorted(ref_keys - cur_keys)
    added = sorted(cur_keys - ref_keys)
    changed = sorted(
        k for k in (ref_keys & cur_keys) if repr(ref[k]) != repr(cur[k])
    )
    return {
        "dropped": dropped,
        "dropped_retired": [k for k in dropped if _is_retired(k)],
        "dropped_runtime_state": [k for k in dropped if _is_runtime_state(k)],
        "dropped_candidate": [
            k for k in dropped if not _is_retired(k) and not _is_runtime_state(k)
        ],
        "added": added,
        "changed": [(k, ref[k], cur[k]) for k in changed],
        "ref_values": {k: ref[k] for k in dropped},
    }


def resolvable_key_gaps() -> List[Tuple[str, str, str]]:
    """Return (section, key, source) for runtime-resolvable keys with no
    canonical default and no by-design derivation."""
    from core.settings.default_contract import require_canonical_default
    from rendering.widget_descriptors import get_widget_default_init_descriptors
    from core.settings.models._spotify_visualizer import (
        _PER_MODE_TECHNICAL_SERIALIZERS,
        _PER_MODE_RESOLVERS,
    )
    from core.settings.models._visualizer_helpers import PER_MODE_TECHNICAL_MODES

    canon: Dict[str, Any] = {}

    def has(section: str, key: str) -> bool:
        if section not in canon:
            try:
                canon[section] = require_canonical_default(f"widgets.{section}")
            except Exception:
                canon[section] = None
        c = canon[section]
        return bool(c is not None and key in c)

    gaps: List[Tuple[str, str, str]] = []

    # Descriptor-driven default attrs.
    for d in get_widget_default_init_descriptors():
        if not has(d.section, d.key):
            gaps.append((d.section, d.key, f"descriptor:{d.attr_name}"))

    # Per-mode x per-key: only modes with a technical profile are required to
    # define these; other modes derive from the reference mode (by design).
    per_mode_keys = sorted(set(_PER_MODE_TECHNICAL_SERIALIZERS) | set(_PER_MODE_RESOLVERS))
    for mode in PER_MODE_TECHNICAL_MODES:
        for key in per_mode_keys:
            if not has("spotify_visualizer", f"{mode}_{key}"):
                gaps.append(("spotify_visualizer", f"{mode}_{key}", "per-mode-technical"))

    return gaps


def run_audit(ref_root: Path) -> Dict[str, Any]:
    return {
        "defaults": diff_canonical_defaults(ref_root),
        "resolve_gaps": resolvable_key_gaps(),
    }


def _print_report(result: Dict[str, Any]) -> int:
    d = result["defaults"]
    gaps = result["resolve_gaps"]
    print("=" * 72)
    print("SETTINGS MIGRATION AUDIT (pre-migration oracle vs current)")
    print("=" * 72)
    cand = d["dropped_candidate"]
    print(f"\n[1] DROPPED canonical keys (candidates to recover): {len(cand)}")
    for k in cand:
        print(f"    - {k}   was={d['ref_values'][k]!r}")
    print(f"\n    (retired-by-design, ignored: {len(d['dropped_retired'])}: "
          f"{', '.join(d['dropped_retired']) or 'none'})")
    print(f"    (runtime/session state correctly purged from defaults, ignored: "
          f"{len(d['dropped_runtime_state'])})")
    print(f"\n[2] ADDED keys since pre-migration: {len(d['added'])}")
    print(f"\n[3] CHANGED values: {len(d['changed'])}")
    for k, was, now in d["changed"]:
        print(f"    - {k}   {was!r} -> {now!r}")
    print(f"\n[4] RUNTIME-RESOLVABLE keys with NO canonical default: {len(gaps)}")
    for section, key, source in gaps:
        print(f"    - widgets.{section}.{key}   <- {source}")
    blocking = len(cand) + len(gaps)
    print("\n" + "-" * 72)
    print(f"RESULT: {blocking} blocking gap(s) "
          f"({len(cand)} dropped candidates, {len(gaps)} unresolved runtime keys); "
          f"{len(d['changed'])} value changes to review.")
    return blocking


def main() -> int:
    parser = argparse.ArgumentParser(description="Settings migration defaults audit")
    parser.add_argument("--ref", default="deleteme/PreSettings",
                        help="pre-migration reference tree (default deleteme/PreSettings)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a report")
    args = parser.parse_args()
    ref_root = (REPO_ROOT / args.ref) if not Path(args.ref).is_absolute() else Path(args.ref)
    result = run_audit(ref_root)
    if args.json:
        print(json.dumps(
            {
                "dropped_candidate": result["defaults"]["dropped_candidate"],
                "dropped_retired": result["defaults"]["dropped_retired"],
                "added": result["defaults"]["added"],
                "changed": [[k, repr(a), repr(b)] for k, a, b in result["defaults"]["changed"]],
                "resolve_gaps": result["resolve_gaps"],
            },
            indent=2,
        ))
        return 0
    return _print_report(result)


if __name__ == "__main__":
    raise SystemExit(main())
