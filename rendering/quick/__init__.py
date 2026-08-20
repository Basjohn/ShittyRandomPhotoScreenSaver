"""Qt Quick production presentation package.

The legacy QWidget presenter remains the production path until the explicit
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
