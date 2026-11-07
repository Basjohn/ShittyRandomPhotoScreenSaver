"""The Settings tab registry: one descriptor per top-level Settings tab, in sidebar order.

``SettingsDialog`` derives everything tab-shaped from this tuple: the tab keys (and so the content-stack positions),
the lazy builders, the background-warm list, the sidebar labels, the editing-path pill both bucket projections use
(construction and reload), and the tabs a Settings reload refreshes. A tab that exists only in some product profile
declares it with ``available(profile)``; an unavailable tab is absent from the sidebar, the content stack and the
persisted-tab mapping. The persisted tab is a key (``ui.last_tab_key``), never a position, so hiding a tab cannot
shift a remembered one.

The profile is answered by the one product-identity predicate (``core/mc.py``); never add a second resolver here.
A new tab adds one descriptor; it builds lazily, owns its own pill vocabulary through ``pill_of`` and must not keep
hidden value-owner widgets (Studio-owned values live in a value cache, see ``ui/tabs/media/spec_mode_builder.py``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional

from ui.tabs.accessibility_tab import AccessibilityTab
from ui.tabs.display_tab import DisplayTab
from ui.tabs.scene3d_tab import Scene3DTab
from ui.tabs.sources_tab import SourcesTab
from ui.tabs.themes_tab import ThemesTab
from ui.tabs.transitions_tab import TransitionsTab, transition_bucket_section
from ui.tabs.visualizers_tab import VisualizersTab
from ui.tabs.widgets_tab import WidgetsTab

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class SettingsProfile:
    """The product identity Settings is opened in. ``mc``: the Manual Controller build."""

    mc: bool = False

    @classmethod
    def current(cls) -> "SettingsProfile":
        from core import mc
        return cls(mc=bool(mc.is_mc_build()))


def _no_pill(_view_state: Mapping[str, Any]) -> str:
    return ""


def _always(_profile: SettingsProfile) -> bool:
    return True


@dataclass(frozen=True)
class SettingsTabDescriptor:
    """One top-level Settings tab.

    ``build(dialog)`` constructs the tab parented to the dialog's content stack. ``pill_of(view_state)`` returns the
    editing-path pill of the tab's persisted view state ('' for a tab without pills), as
    ``project_settings_bucket_context`` takes it. ``warm_in_background``: built after first paint, staggered and
    cancellable; every other tab builds only when visited. ``reloads_with_settings``: refreshed in place after a
    preset change, reset or import. ``pinned_bottom``: the button sits under the sidebar's stretch.
    """

    key: str
    label: str
    build: Callable[[Any], "QWidget"]
    pill_of: Callable[[Mapping[str, Any]], str] = _no_pill
    available: Callable[[SettingsProfile], bool] = _always
    warm_in_background: bool = False
    reloads_with_settings: bool = False
    pinned_bottom: bool = False


def _widgets_pill(view_state: Mapping[str, Any]) -> str:
    return str(view_state.get("subtab_id") or "setup")


def _visualizers_pill(view_state: Mapping[str, Any]) -> str:
    return str(view_state.get("mode_id") or "") if view_state.get("page") == "mode" else ""


def _transitions_pill(view_state: Mapping[str, Any]) -> str:
    # The bucket projection takes a pill's bucket section, not its display name ("3D Block Spins" -> "blockspin").
    return transition_bucket_section(str(view_state.get("pill") or ""))


SETTINGS_TAB_DESCRIPTORS: tuple[SettingsTabDescriptor, ...] = (
    SettingsTabDescriptor(
        "sources", "Sources",
        lambda d: SourcesTab(d._settings, parent=d.content_stack),
        reloads_with_settings=True,
    ),
    SettingsTabDescriptor(
        "display", "Display",
        lambda d: DisplayTab(d._settings, parent=d.content_stack),
        warm_in_background=True, reloads_with_settings=True,
    ),
    SettingsTabDescriptor(
        "transitions", "Transitions",
        lambda d: TransitionsTab(d._settings, parent=d.content_stack),
        pill_of=_transitions_pill, warm_in_background=True, reloads_with_settings=True,
    ),
    SettingsTabDescriptor(
        "widgets", "Widgets",
        lambda d: WidgetsTab(
            d._settings,
            parent=d.content_stack,
            lazy_sections=True,
            initial_view_state=d._initial_view_state_for_tab("widgets"),
        ),
        pill_of=_widgets_pill, reloads_with_settings=True,
    ),
    SettingsTabDescriptor("layout", "Layout", lambda d: d._create_layout_tab()),
    SettingsTabDescriptor(
        "visualizers", "Visualizers",
        lambda d: VisualizersTab(d._settings, parent=d.content_stack),
        pill_of=_visualizers_pill, reloads_with_settings=True,
    ),
    SettingsTabDescriptor(
        "scene3d", "3D Quality",
        lambda d: Scene3DTab(d._settings, parent=d.content_stack),
        reloads_with_settings=True,
    ),
    SettingsTabDescriptor(
        "accessibility", "Accessibility",
        lambda d: AccessibilityTab(d._settings, parent=d.content_stack),
        reloads_with_settings=True,
    ),
    SettingsTabDescriptor("themes", "Themes", lambda d: ThemesTab(d._settings, parent=d.content_stack)),
    SettingsTabDescriptor("about", "About", lambda d: d._create_about_tab()),
    # Title Case like its siblings; all-caps did not fit the 200 px sidebar.
    SettingsTabDescriptor("quick_start", "Quick Start", lambda d: d._create_quick_start_tab(), pinned_bottom=True),
)


def settings_tab_descriptors(profile: SettingsProfile) -> tuple[SettingsTabDescriptor, ...]:
    """The tabs available in ``profile``, in sidebar order."""
    return tuple(descriptor for descriptor in SETTINGS_TAB_DESCRIPTORS if descriptor.available(profile))


def settings_tab_descriptor(key: str) -> Optional[SettingsTabDescriptor]:
    """The descriptor of ``key`` whatever the profile, or None for an unknown key."""
    return next((descriptor for descriptor in SETTINGS_TAB_DESCRIPTORS if descriptor.key == key), None)


def settings_tab_pill(key: str, view_state: object) -> str:
    """The editing-path pill of tab ``key`` for ``view_state`` ('' for unknown tabs and non-mapping states)."""
    descriptor = settings_tab_descriptor(key)
    if descriptor is None:
        return ""
    return descriptor.pill_of(view_state if isinstance(view_state, Mapping) else {})


__all__ = [
    "SETTINGS_TAB_DESCRIPTORS",
    "SettingsProfile",
    "SettingsTabDescriptor",
    "settings_tab_descriptor",
    "settings_tab_descriptors",
    "settings_tab_pill",
]
