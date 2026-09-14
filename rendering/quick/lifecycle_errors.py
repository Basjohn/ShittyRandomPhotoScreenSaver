"""Typed retained-Quick lifecycle failures.

Only failures that prove the current retained object graph cannot be reconciled
safely in-generation belong here.  Programming defects such as TypeError,
AttributeError, or malformed call contracts must remain ordinary exceptions so
callers cannot silently relabel them as legitimate teardown policy.
"""

from __future__ import annotations


class RetainedRuntimeIncoherenceError(RuntimeError):
    """The retained Quick owner graph is stale/dead/incoherent and must rebuild."""
