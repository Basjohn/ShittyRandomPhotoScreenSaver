"""Shared test doubles for ``DisplayManager`` and what it reads, built from the real classes.

Hand-built stubs went stale every time ``DisplayManager`` started reading one more member: ``owner.is_started``
(dfceed38) and ``scene_controller.set_visualizer_studio_rotate_glyphs`` broke five files at once, and the Expanded
Visualizer glyph neighbours (32279216) reached ``self.displays`` on a manager built with ``__new__``. These doubles
follow the real surfaces instead of a copied list:

* ``bare_display_manager``: ``DisplayManager.__new__`` (no Qt, resource or display construction) carrying every
  plain default ``DisplayManager.__init__`` assigns (``None``, constants, empty containers), read from its source.
* ``scene_controller_double`` / ``input_controller_double``: a no-op for every public ``set_*`` method of the real
  ``QuickSceneController`` / ``QuickInputController``; a name the real class lacks raises, so a double never
  invents a member.
* ``visualizer_owner_double``: the read surface of ``QuickDisplayVisualizerOwner`` (started, retired, controller),
  each name checked against the real class.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

_EMPTY_CALLS = {"list": list, "dict": dict, "set": set, "tuple": tuple}


def _plain_default(node: ast.expr) -> tuple[bool, Any]:
    """Whether ``node`` is a plain default (constant or empty container) and, if so, a builder of its value."""
    if isinstance(node, ast.Constant):
        return True, lambda value=node.value: value
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)) and not node.elts:
        kind = {ast.List: list, ast.Set: set, ast.Tuple: tuple}[type(node)]
        return True, kind
    if isinstance(node, ast.Dict) and not node.keys:
        return True, dict
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _EMPTY_CALLS
            and not node.args and not node.keywords):
        return True, _EMPTY_CALLS[node.func.id]
    return False, None


@lru_cache(maxsize=1)
def _display_manager_plain_defaults() -> tuple[tuple[str, Any], ...]:
    """``(name, builder)`` for each ``self.<name> = <plain default>`` at the top level of ``DisplayManager.__init__``."""
    from engine.display_manager import DisplayManager

    tree = ast.parse(textwrap.dedent(inspect.getsource(DisplayManager.__init__)))
    body = tree.body[0].body
    defaults: dict[str, Any] = {}
    for statement in body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            target, value = statement.target, statement.value
        else:
            continue
        if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                and target.value.id == "self"):
            continue
        plain, builder = _plain_default(value)
        if plain:
            defaults[target.attr] = builder
    return tuple(defaults.items())


def bare_display_manager(**attributes: Any):
    """A ``DisplayManager`` built with ``__new__`` plus every plain ``__init__`` default; ``attributes`` override."""
    from engine.display_manager import DisplayManager

    manager = DisplayManager.__new__(DisplayManager)
    for name, builder in _display_manager_plain_defaults():
        setattr(manager, name, builder())
    for name, value in attributes.items():
        setattr(manager, name, value)
    return manager


def _setter_double(cls: type, overrides: dict[str, Any]) -> SimpleNamespace:
    setters = {name for name in dir(cls) if name.startswith("set_") and callable(getattr(cls, name, None))}
    unknown = sorted(name for name in overrides if not hasattr(cls, name))
    if unknown:
        raise AttributeError(f"{cls.__name__} has no {', '.join(unknown)}: the double would invent members")
    members = {name: (lambda *_args, **_kwargs: None) for name in setters}
    members.update(overrides)
    return SimpleNamespace(**members)


def scene_controller_double(**overrides: Any) -> SimpleNamespace:
    """A no-op for every public ``set_*`` of the real ``QuickSceneController``; ``overrides`` must be real members."""
    from rendering.quick.scene_controller import QuickSceneController

    return _setter_double(QuickSceneController, overrides)


def input_controller_double(**overrides: Any) -> SimpleNamespace:
    """A no-op for every public ``set_*`` of the real ``QuickInputController``; ``overrides`` must be real members."""
    from rendering.quick.input_controller import QuickInputController

    return _setter_double(QuickInputController, overrides)


def visualizer_owner_double(controller: Any, *, started: bool = True, retired: bool = False,
                            **members: Any) -> SimpleNamespace:
    """The read surface of a live ``QuickDisplayVisualizerOwner``; every name must exist on the real class."""
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    surface = {"controller": controller, "is_started": bool(started), "is_retired": bool(retired), **members}
    unknown = sorted(name for name in surface if not hasattr(QuickDisplayVisualizerOwner, name))
    if unknown:
        raise AttributeError(f"QuickDisplayVisualizerOwner has no {', '.join(unknown)}")
    return SimpleNamespace(**surface)


__all__ = [
    "bare_display_manager",
    "input_controller_double",
    "scene_controller_double",
    "visualizer_owner_double",
]
