"""Stored settings values: strict equality and structural sharing between a stored value and its replacement.

A value the settings store holds is never changed in place (``JsonSettingsStore.peek``). A write therefore need not
copy the whole value it is handed: the parts equal to the stored value can be the stored value's own objects, and
only the containers on a changed path are new. That keeps a write that changes one route of a 300 KB widgets root
as cheap as the change (Current_Plan 1C.2: a whole-root ``deepcopy`` on the GUI thread, inflated by every GIL
hand-off to the render threads, stalled a display move's fade).

The scans below find the values that are not the same objects with C iterators (``map``/``compress`` over
``operator.is_not``), so the Python-level work is proportional to what changed, not to the size of the value.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import chain, compress, repeat
from operator import is_, is_not
from typing import Any

__all__ = ["changed_keys", "same_stored_value", "share_unchanged"]

_MISSING: Any = object()
_EMPTY: dict = {}
_SCALARS = (str, int, float, bool, type(None), bytes)


def changed_keys(new: dict, old: dict) -> list:
    """Keys of ``new`` whose values are not the very objects ``old`` holds under them (missing keys included)."""
    return list(compress(new, map(is_not, new.values(), map(old.get, new, repeat(_MISSING)))))


def _changed_indices(new: list | tuple, old: list | tuple) -> list:
    return list(compress(range(len(new)), map(is_not, new, chain(old, repeat(_MISSING)))))


def same_stored_value(a: Any, b: Any) -> bool:
    """Equal and of the same types throughout (``1 == 1.0`` but they are stored differently).

    Objects shared by both sides are skipped without a look inside, so comparing a value with one derived from it
    costs what differs between them.
    """
    if a is b:
        return True
    cls = type(a)
    if cls is not type(b):
        return False
    if cls is dict:
        if a.keys() != b.keys():
            return False
        return all(same_stored_value(a[key], b[key]) for key in changed_keys(a, b))
    if cls is list or cls is tuple:
        if len(a) != len(b):
            return False
        return all(same_stored_value(a[i], b[i]) for i in _changed_indices(a, b))
    return a == b


def share_unchanged(old: Any, new: Any) -> Any:
    """A value strictly equal to ``new`` (``same_stored_value``) that holds none of ``new``'s containers.

    Every part of ``new`` strictly equal to the matching part of ``old`` is ``old``'s own object (``old`` itself when
    the whole is unchanged); only the containers on a changed path are new, and everything under a new key is a
    fresh copy. Pass ``old`` only when nothing changes it in place (a stored value). Types other than plain JSON
    containers and scalars are deep-copied, as a store write always did.
    """
    if new is old:
        return old
    cls = type(new)
    if cls in _SCALARS:
        return old if type(old) is cls and old == new else new
    if cls is dict:
        base = old if type(old) is dict else _EMPTY
        result = dict(new)
        for key in changed_keys(new, base):
            result[key] = share_unchanged(base.get(key, _MISSING), new[key])
        if (base is old and result.keys() == old.keys()
                and all(map(is_, result.values(), map(old.get, result)))):
            return old
        return result
    if cls is list or cls is tuple:
        base_seq = old if type(old) is cls else ()
        items = list(new)
        for index in _changed_indices(new, base_seq):
            items[index] = share_unchanged(base_seq[index] if index < len(base_seq) else _MISSING, new[index])
        if base_seq is old and len(items) == len(old) and all(map(is_, items, old)):
            return old
        return items if cls is list else tuple(items)
    return deepcopy(new)
