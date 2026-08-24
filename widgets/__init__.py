"""Overlay widget package.

Runtime implementations are resolved through their explicit submodules only.
Keeping package import inert prevents a lightweight helper such as
``widgets.shadow_utils`` from activating unrelated widget families.
"""
