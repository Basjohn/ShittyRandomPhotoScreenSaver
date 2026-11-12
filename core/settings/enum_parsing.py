"""Strict enum parsing for settings values.

This module imports nothing from ``core.settings``: the settings models parse their canonical enum defaults at
class definition, and ``core.settings.normalization`` (which imports the models) builds its repairing
``SettingsNormalizer.to_enum`` on the same parser. Keeping the parser below both is what lets either be imported
first. ``core.settings.normalization`` re-exports ``parse_enum_strict`` for existing callers.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Type, TypeVar

T = TypeVar("T", bound=Enum)


def parse_enum_strict(value: Any, enum_type: Type[T]) -> T:
    """Parse one enum value without inventing a fallback.

    Canonical schema values use this path: if the authority itself contains an
    unsupported enum representation, fail loudly. Persisted/migration values
    should use ``SettingsNormalizer.to_enum`` with the already-parsed canonical
    enum as their repair value.
    """

    if isinstance(value, enum_type):
        return value
    if value is None:
        raise ValueError(f"Missing {enum_type.__name__} value")

    text = str(value)
    if "." in text:
        text = text.split(".")[-1]
    text = text.strip().lower().replace(" ", "_").replace("-", "_")
    if not text:
        raise ValueError(f"Empty {enum_type.__name__} value")

    try:
        return enum_type(text)
    except ValueError:
        for member in enum_type:
            if member.name.lower() == text:
                return member
    raise ValueError(f"Unsupported {enum_type.__name__} value: {value!r}")
