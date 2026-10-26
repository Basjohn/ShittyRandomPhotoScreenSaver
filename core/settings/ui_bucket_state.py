"""Canonical Settings bucket persistence semantics.

Collapsible Settings buckets are schema-enumerated by canonical defaults, but
persisted user state is intentionally sparse. A dialog-wide projection retains
only the active tab/pill's editing path; local accordion scopes do not grant
separate inactive contexts permission to persist. Closed buckets are absent.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, MutableMapping
from typing import Hashable

BucketScopeResolver = Callable[[str], Hashable]


def normalize_single_open_bucket_states(
    canonical_keys: Iterable[str],
    raw: object,
    *,
    scope_for_key: BucketScopeResolver,
) -> dict[str, bool]:
    """Return canonical in-memory states with at most one open key per scope.

    Canonical keys remain fully enumerated in memory so missing schema is still
    fail-loud at getters.  Persisted mappings may be legacy full boolean maps or
    the current sparse true-only form.  When legacy data contains multiple open
    keys in one scope, the last true key in persisted mapping order wins.
    """

    keys = tuple(str(key) for key in canonical_keys)
    states = {key: False for key in keys}
    canonical = set(keys)
    if not isinstance(raw, Mapping):
        return states

    winners: dict[Hashable, str] = {}
    for raw_key, raw_value in raw.items():
        key = str(raw_key)
        if key not in canonical or not bool(raw_value):
            continue
        winners[scope_for_key(key)] = key

    for key in winners.values():
        states[key] = True
    return states


def normalize_widget_bucket_states(
    canonical_keys: Iterable[str],
    raw: object,
) -> dict[str, bool]:
    """Normalize persisted Widget bucket state using current identities only.

    Sparse persistence plus one-open-per-local-scope projection is current product
    behavior. Unknown/retired identities naturally drop because they are absent
    from the canonical key set; no historical identity rewrite remains.
    """

    keys = tuple(str(key) for key in canonical_keys)
    return normalize_single_open_bucket_states(
        keys,
        raw,
        scope_for_key=lambda key: widget_bucket_scope(key, keys),
    )


def set_single_open_bucket_state(
    states: MutableMapping[str, bool],
    key: str,
    expanded: bool,
    *,
    scope_for_key: BucketScopeResolver,
) -> None:
    """Mutate canonical states so ``key`` is the only open key in its scope."""

    canonical_key = str(key)
    if canonical_key not in states:
        raise KeyError(f"Unknown canonical Settings bucket: {canonical_key}")

    target_scope = scope_for_key(canonical_key)
    if expanded:
        for candidate in tuple(states):
            if scope_for_key(candidate) == target_scope:
                states[candidate] = False
        states[canonical_key] = True
    else:
        states[canonical_key] = False


def sparse_open_bucket_states(states: Mapping[str, bool]) -> dict[str, bool]:
    """Return the persisted true-only representation of canonical bucket state."""

    return {str(key): True for key, expanded in states.items() if bool(expanded)}


def flat_bucket_scope(_key: str) -> str:
    """One local accordion scope for an un-namespaced bucket family."""

    return "root"


def visualizer_bucket_scope(key: str) -> str:
    """Visualizer leaf buckets coordinate within their canonical mode page."""

    mode, separator, _bucket = str(key).partition(":")
    if not separator or not mode:
        raise ValueError(f"Malformed visualizer bucket key: {key!r}")
    return mode


def widget_bucket_scope(key: str, canonical_keys: Iterable[str]) -> str:
    """Resolve a stable Widget accordion scope from canonical bucket ancestry.

    Most Widget pages have one flat bucket level, so their section id is the
    scope.  Steam card buckets are nested (for example
    ``steam:achievement_pulse`` -> ``steam:achievement_pulse_layout``).  The
    canonical parent bucket name therefore defines a child scope without a
    hard-coded Steam table, and the same rule naturally supports future nested
    families that follow the existing naming contract.
    """

    full_key = str(key)
    section, separator, bucket = full_key.partition(":")
    if not separator or not section or not bucket:
        raise ValueError(f"Malformed widget bucket key: {key!r}")

    names = {
        str(candidate).partition(":")[2]
        for candidate in canonical_keys
        if str(candidate).partition(":")[0] == section
        and str(candidate).partition(":")[1]
    }
    parents = [
        candidate
        for candidate in names
        if candidate != bucket and bucket.startswith(f"{candidate}_")
    ]
    if not parents:
        return section
    parent = max(parents, key=len)
    return f"{section}:{parent}"


def widget_bucket_parent(key: str, canonical_keys: Iterable[str]) -> str | None:
    """Resolve canonical parent for legacy nested Widget bucket identities."""
    scope = widget_bucket_scope(key, canonical_keys)
    return scope if scope != str(key).partition(":")[0] else None


def set_active_widget_bucket_path(
    states: MutableMapping[str, bool], key: str, expanded: bool,
) -> None:
    """Remember a single Widget editing path, not independent pill accordions.

    A nested leaf preserves its ancestor; opening another root/leaf retires the
    entire previous path. Closing an ancestor also closes hidden descendants.
    """
    if key not in states:
        raise KeyError(f"Unknown canonical Settings bucket: {key}")
    parent = widget_bucket_parent(key, states)
    if expanded:
        keep = {key}
        while parent is not None:
            keep.add(parent)
            parent = widget_bucket_parent(parent, states)
        for candidate in states:
            states[candidate] = candidate in keep
    else:
        states[key] = False
        # A hidden descendant must never remain persisted open under a closed parent.
        for candidate in states:
            ancestor = widget_bucket_parent(candidate, states)
            while ancestor is not None:
                if ancestor == key:
                    states[candidate] = False
                    break
                ancestor = widget_bucket_parent(ancestor, states)


def normalize_active_widget_bucket_path(
    canonical_keys: Iterable[str], raw: object, active_section: str | None,
) -> dict[str, bool]:
    """Migrate full/sparse old maps to one path of the currently selected pill."""
    keys = tuple(str(key) for key in canonical_keys)
    state = dict.fromkeys(keys, False)
    if not isinstance(raw, Mapping) or not active_section:
        return state
    candidates = [str(key) for key, value in raw.items()
                  if str(key) in state and str(key).partition(":")[0] == active_section
                  and bool(value)]
    if candidates:
        # A nested child is more specific than its ancestor regardless of
        # legacy mapping order. For equally deep leaves, the last wins.
        winner = max(enumerate(candidates), key=lambda pair: (
            _widget_bucket_depth(pair[1], keys), pair[0]
        ))[1]
        set_active_widget_bucket_path(state, winner, True)
    return state


def _widget_bucket_depth(key: str, canonical: Iterable[str]) -> int:
    depth = 0
    parent = widget_bucket_parent(key, canonical)
    while parent is not None:
        depth += 1
        parent = widget_bucket_parent(parent, canonical)
    return depth


def normalize_active_visualizer_leaf_path(
    custom_keys: Iterable[str], technical_keys: Iterable[str],
    custom_raw: object, technical_raw: object, active_mode: str | None,
) -> tuple[dict[str, bool], dict[str, bool]]:
    """Only one active-mode Custom/Technical leaf survives legacy persistence."""
    custom = dict.fromkeys(tuple(str(k) for k in custom_keys), False)
    technical = dict.fromkeys(tuple(str(k) for k in technical_keys), False)
    if active_mode:
        winner = None
        for raw, state in ((custom_raw, custom), (technical_raw, technical)):
            if isinstance(raw, Mapping):
                for raw_key, value in raw.items():
                    key = str(raw_key)
                    if key in state and key.partition(":")[0] == active_mode and bool(value):
                        winner = key
        if winner is not None:
            (custom if winner in custom else technical)[winner] = True
    return custom, technical


# One active editing context is retained across the entire Settings dialog.
# Existing maps remain the canonical per-control schemas; this function only
# projects their saved *open* values to the selected tab/pill at navigation.
def visualizer_bucket_is_advanced(key: str) -> bool:
    """Read a Custom leaf's parent from its existing mode declaration."""
    from core.settings.visualizer_mode_settings import mode_settings
    mode, _, bucket = key.partition(":")
    spec = mode_settings(mode)
    return spec is not None and any(entry.key == bucket and entry.advanced for entry in spec.buckets)


def normalize_visualizer_disclosure_path(
    custom: Mapping[str, bool], technical: Mapping[str, bool],
    advanced: Mapping[str, bool], tech_roots: Mapping[str, bool],
) -> tuple[dict[str, bool], dict[str, bool]]:
    """Preserve required ancestors: Technical is a child of Advanced."""
    advanced = dict(advanced)
    tech_roots = dict(tech_roots)
    for mode in advanced:
        custom_leaf = next((key for key, opened in custom.items()
                            if opened and key.partition(":")[0] == mode), None)
        technical_leaf = any(opened and key.partition(":")[0] == mode
                             for key, opened in technical.items())
        if technical_leaf:
            tech_roots[mode] = True
            advanced[mode] = True
        elif custom_leaf is not None:
            tech_roots[mode] = False
            advanced[mode] = visualizer_bucket_is_advanced(custom_leaf)
        elif tech_roots.get(mode):
            advanced[mode] = True
    return advanced, tech_roots


def project_settings_bucket_context(settings, tab: str, pill: str | None = None) -> None:
    from core.settings.defaults import get_default_settings

    canonical = get_default_settings(settings.get_application_name())["ui"]
    tab = str(tab or "")
    pill = str(pill or "")
    widget = normalize_active_widget_bucket_path(
        canonical["widget_bucket_states"],
        settings.get("ui.widget_bucket_states"),
        pill if tab == "widgets" else None,
    )
    custom, technical = normalize_active_visualizer_leaf_path(
        canonical["visualizer_bucket_states"],
        canonical["visualizer_tech_bucket_states"],
        settings.get("ui.visualizer_bucket_states"),
        settings.get("ui.visualizer_tech_bucket_states"),
        pill if tab == "visualizers" else None,
    )
    requested = {
        "ui.widget_bucket_states": sparse_open_bucket_states(widget),
        "ui.gmail_bucket_states": sparse_open_bucket_states(
            normalize_single_open_bucket_states(
                canonical["gmail_bucket_states"],
                settings.get("ui.gmail_bucket_states") if tab == "widgets" and pill == "gmail" else {},
                scope_for_key=flat_bucket_scope,
            )
        ),
        "ui.visualizer_bucket_states": sparse_open_bucket_states(custom),
        "ui.visualizer_tech_bucket_states": sparse_open_bucket_states(technical),
    }
    for leaf in ("visualizer_adv_states", "visualizer_tech_states"):
        raw = settings.get("ui." + leaf)
        requested["ui." + leaf] = {
            str(key): True for key, expanded in (raw.items() if isinstance(raw, Mapping) else ())
            if tab == "visualizers" and str(key) == pill and bool(expanded)
            and key in canonical[leaf]
        }
    advanced, tech_roots = normalize_visualizer_disclosure_path(
        custom, technical,
        {key: bool(requested["ui.visualizer_adv_states"].get(key)) for key in canonical["visualizer_adv_states"]},
        {key: bool(requested["ui.visualizer_tech_states"].get(key)) for key in canonical["visualizer_tech_states"]},
    )
    requested["ui.visualizer_adv_states"] = sparse_open_bucket_states(advanced)
    requested["ui.visualizer_tech_states"] = sparse_open_bucket_states(tech_roots)
    raw_simple = settings.get("ui.basic_bucket_path")
    if tab == "sources" and raw_simple in ("sources:folders", "sources:feeds"):
        basic = raw_simple
    elif tab == "transitions" and pill and raw_simple == "transitions:" + pill:
        # For Transitions the caller passes the pill's bucket section (``transition_bucket_section``):
        # a pill's display name ("3D Block Spins") is not its section ("blockspin").
        basic = raw_simple
    else:
        basic = ""
    requested["ui.basic_bucket_path"] = basic
    for name, value in requested.items():
        raw = settings.get(name)
        # Avoid startup writes when an all-false canonical legacy map already
        # represents the same all-closed state. Only changed open keys matter.
        if isinstance(value, dict):
            previous = sparse_open_bucket_states(raw) if isinstance(raw, Mapping) else {}
            if previous == value:
                continue
        elif raw == value:
            continue
        settings.set(name, value, emit_change=False)


def retire_settings_bucket_context(settings) -> None:
    """On successful leave, no earlier pill/tab retains an expanded bucket."""
    project_settings_bucket_context(settings, "", "")
