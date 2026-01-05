"""Automated module reload system to prevent stale bytecode issues.

This module provides automatic pycache cleanup and module reloading
to prevent the catastrophic design flaw where stale bytecode gets loaded.
"""
import sys
import shutil
from pathlib import Path
from typing import Optional
import importlib


def force_clean_pycache(root_path: Path) -> int:
    """
    Aggressively clean all __pycache__ directories.
    
    Args:
        root_path: Root directory to clean
        
    Returns:
        Number of directories removed
    """
    removed = 0
    try:
        for pycache_dir in root_path.rglob("__pycache__"):
            try:
                shutil.rmtree(pycache_dir)
                removed += 1
            except Exception:
                pass
    except Exception:
        pass
    
    return removed


def force_reload_module(module_name: str, root_path: Optional[Path] = None) -> bool:
    """
    Force reload a module by cleaning its pycache and reimporting.
    
    Args:
        module_name: Full module name (e.g., 'widgets.spotify_visualizer.beat_engine')
        root_path: Project root for pycache cleanup (optional)
        
    Returns:
        True if reload successful
    """
    try:
        # Clean pycache if root provided
        if root_path:
            module_parts = module_name.split('.')
            for i in range(len(module_parts)):
                partial_path = root_path / Path(*module_parts[:i+1])
                pycache = partial_path / '__pycache__'
                if pycache.exists():
                    shutil.rmtree(pycache)
        
        # Remove from sys.modules to force reimport
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # Reimport
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def auto_reload_on_import(module_name: str) -> None:
    """
    Automatically clean pycache and reload module on import.
    
    Call this at the top of main.py before importing critical modules.
    
    Args:
        module_name: Module to auto-reload
    """
    project_root = Path(__file__).parent.parent.parent
    force_reload_module(module_name, project_root)
