"""Stable application-owned Windows audio-session event context.

The Core Audio callback only compares the value; it never imports COM, queries
an endpoint or writes sound state. The GUID is a program identity, not a user
or session identifier.
"""
from __future__ import annotations

SESSION_VOLUME_EVENT_CONTEXT = "{D71A8B39-7F5D-46A9-9AF0-675F89EBEF62}"


def is_owned_session_volume_event(context: object) -> bool:
    if context is None:
        return False
    try:
        value = getattr(context, "contents", context)
        # comtypes GUID.__str__ produces a braced canonical value. Accept
        # only exact equality rather than a substring or untrusted pointer.
        return str(value).strip().casefold() == SESSION_VOLUME_EVENT_CONTEXT.casefold()
    except (AttributeError, ValueError, TypeError):
        return False
