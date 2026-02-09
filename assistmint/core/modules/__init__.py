"""
Module management for Assistmint.

Provides:
- BaseModule abstract class
- ModuleLoader for dynamic loading/unloading
- ModuleResult for module return values
"""

from assistmint.core.modules.base import BaseModule, ModuleResult, ModuleCapability, ModuleContext
from assistmint.core.modules.loader import ModuleLoader, get_module_loader

__all__ = ["BaseModule", "ModuleResult", "ModuleCapability", "ModuleContext", "ModuleLoader", "get_module_loader"]
