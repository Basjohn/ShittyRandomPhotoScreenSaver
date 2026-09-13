"""Steam widget family support package.

Achievement Pulse, Abandonment Issues, and Friend Pulse are available normally;
only the unfinished Steam Journey scaffold remains gated by ``--devsteam``.
Importing this package must stay side-effect free: no provider
calls, credential reads, or cache scans.
"""
