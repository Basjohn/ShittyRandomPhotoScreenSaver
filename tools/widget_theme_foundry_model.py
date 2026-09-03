"""Qt-free model helpers for SRPSS Widget Theme Foundry.

The Foundry deliberately consumes the production Widget Theme schema instead of
maintaining a second list of legal theme keys.  This module owns only mutable
draft/editor conveniences so it can be tested without PySide6.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from ui.settings_theme_spec import Rgba
from ui.widget_theme_spec import (
    DEFAULT_DARK_WIDGET_THEME,
    WIDGET_THEME_CORE_COLOR_ROLES,
    WidgetThemeSpec,
)
from ui.widget_visual_roles import (
    WIDGET_THEME_OPTIONAL_COLOR_ROLES,
    WIDGET_VISUAL_ROLE_PARENTS,
)


ROLE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Shared Card", ("card.",)),
    ("Shared Widget", ("header.", "widget.")),
    ("Media", ("media.",)),
    ("Context Menu", ("context.",)),
    ("Mail / Reddit / Weather / Clock", ("gmail.", "reddit.", "reddit2.", "weather.", "clock.")),
    ("Steam", ("steam.", "achievement_pulse.", "abandonment_issues.")),
)


def all_widget_theme_roles() -> tuple[str, ...]:
    """Return every production-legal serialized colour role deterministically."""
    return tuple(sorted(set(WIDGET_THEME_CORE_COLOR_ROLES) | set(WIDGET_THEME_OPTIONAL_COLOR_ROLES)))


def role_group(role: str) -> str:
    role = str(role)
    for label, prefixes in ROLE_GROUPS:
        if role.startswith(prefixes):
            return label
    return "Other"


def friendly_role_label(role: str) -> str:
    parts = []
    for piece in str(role).split("."):
        words = piece.replace("_", " ").split()
        parts.append(" ".join(word.upper() if word.lower() in {"ui", "rgb", "rgba"} else word.capitalize() for word in words))
    return " · ".join(parts)


def rgba_summary(value: Rgba) -> str:
    return f"RGBA({value.r}, {value.g}, {value.b}, {value.a})  #{value.r:02X}{value.g:02X}{value.b:02X}{value.a:02X}"


def exact_color_matches(colors: dict[str, Rgba], value: Rgba) -> tuple[str, ...]:
    return tuple(role for role, candidate in colors.items() if candidate == value)


def replace_exact_color_matches(colors: dict[str, Rgba], value: Rgba, replacement: Rgba) -> tuple[str, ...]:
    matches = exact_color_matches(colors, value)
    for role in matches:
        colors[role] = replacement
    return matches


def most_used_colors(colors: dict[str, Rgba], *, limit: int = 6) -> tuple[tuple[Rgba, tuple[str, ...]], ...]:
    groups: dict[Rgba, list[str]] = {}
    order: dict[Rgba, int] = {}
    for index, (role, color) in enumerate(colors.items()):
        if color.a == 0:
            continue
        groups.setdefault(color, []).append(role)
        order.setdefault(color, index)
    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), order[item[0]]))
    return tuple((color, tuple(roles)) for color, roles in ranked[: max(0, limit)])


@dataclass(slots=True)
class RoleResolution:
    requested_role: str
    color: Rgba | None
    source_role: str | None
    kind: str  # explicit | inherited | local


@dataclass(slots=True)
class WidgetThemeDraft:
    theme_id: str
    name: str
    linked_settings_theme_id: str | None
    colors: dict[str, Rgba]

    @classmethod
    def from_spec(cls, spec: WidgetThemeSpec) -> "WidgetThemeDraft":
        return cls(
            theme_id=spec.theme_id,
            name=spec.name,
            linked_settings_theme_id=spec.linked_settings_theme_id,
            colors=dict(spec.colors),
        )

    def to_spec(self) -> WidgetThemeSpec:
        return WidgetThemeSpec(
            theme_id=self.theme_id,
            name=self.name,
            linked_settings_theme_id=self.linked_settings_theme_id,
            colors=dict(self.colors),
        )

    def is_core(self, role: str) -> bool:
        return role in WIDGET_THEME_CORE_COLOR_ROLES

    def has_override(self, role: str) -> bool:
        return role in self.colors

    def resolve_role(self, role: str) -> RoleResolution:
        """Resolve only theme-owned inheritance; local.* terminals remain unknown."""
        requested = str(role)
        current = requested
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            if current in self.colors:
                return RoleResolution(
                    requested_role=requested,
                    color=self.colors[current],
                    source_role=current,
                    kind="explicit" if current == requested else "inherited",
                )
            parent = WIDGET_VISUAL_ROLE_PARENTS.get(current, "")
            if parent.startswith("local."):
                return RoleResolution(requested, None, parent, "local")
            current = parent
        return RoleResolution(requested, None, None, "local")

    def set_role(self, role: str, color: Rgba) -> None:
        if role not in all_widget_theme_roles():
            raise ValueError(f"Unknown Widget Theme role: {role}")
        self.colors[role] = color

    def remove_optional_override(self, role: str) -> bool:
        if role in WIDGET_THEME_CORE_COLOR_ROLES:
            raise ValueError(f"Core Widget Theme role cannot be removed: {role}")
        return self.colors.pop(role, None) is not None


def safe_theme_filename(name: str) -> str:
    stem = re.sub(r'[<>:"/\\|?*]+', "", str(name)).strip().rstrip(".")
    return stem or "Widget Theme"


def theme_id_for_save_as(path: Path) -> str:
    """Make a path-independent unique-ish identity for a manually authored file."""
    return f"widget:file:{path.name}"


def default_seed_color(role: str, draft: WidgetThemeDraft) -> Rgba:
    """Pick a sensible editor seed when an optional role ends at local.*.

    This is UI convenience only; it is never silently serialized.  The user must
    explicitly choose/apply a colour before the optional role is written.
    """
    resolved = draft.resolve_role(role)
    if resolved.color is not None:
        return resolved.color
    if role.endswith(("border", "outline", "separator")):
        return draft.colors["card.border"]
    if role.endswith(("text", "icon", "arrow")) or "sender" in role or "age" in role or "timestamp" in role:
        return draft.colors["card.text"]
    if "accent" in role or role.endswith(("fill", "glow")):
        return draft.colors.get("widget.accent", draft.colors["card.border"])
    return draft.colors["card.background"]


__all__ = [
    "ROLE_GROUPS",
    "RoleResolution",
    "WidgetThemeDraft",
    "all_widget_theme_roles",
    "default_seed_color",
    "exact_color_matches",
    "friendly_role_label",
    "most_used_colors",
    "replace_exact_color_matches",
    "rgba_summary",
    "role_group",
    "safe_theme_filename",
    "theme_id_for_save_as",
]
