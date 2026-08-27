"""Gmail integration package.

Concrete backend, OAuth, IMAP, client and deeplink modules are imported only by
their explicit runtime callers.  Keeping the package initializer dormant stops
presentation-only imports from activating the backend implementation tree.
"""

__all__: list[str] = []
