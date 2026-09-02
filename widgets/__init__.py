"""Overlay widget package.

Runtime implementations are resolved through their explicit submodules only.
Keeping package import inert prevents lightweight runtime helpers from
activating unrelated widget families.
"""
