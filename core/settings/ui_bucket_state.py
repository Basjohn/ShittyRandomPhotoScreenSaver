"""Canonical Settings bucket persistence semantics.

Collapsible Settings buckets are schema-enumerated by canonical defaults, but
persisted user state is intentionally sparse: at most one open bucket is stored
per local accordion scope.  Closed buckets are represented by absence rather
than one persisted boolean per bucket.
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
