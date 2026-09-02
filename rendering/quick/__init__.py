"""Qt Quick production presentation package.

Retained Qt Quick is the production presentation path after the explicit
cutover phase.  Modules in this package own the replacement Quick presentation
architecture as it lands slice by slice.
"""

from .bootstrap import (
    QuickBootstrapState,
    configure_quick_environment,
    configure_quick_graphics,
    quick_qml_root,
)

__all__ = [
    "QuickBootstrapState",
    "configure_quick_environment",
    "configure_quick_graphics",
    "quick_qml_root",
]
