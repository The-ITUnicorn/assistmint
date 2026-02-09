"""
Module Loader - Dynamic loading and management of Assistmint modules.

Handles:
- Loading modules from modules/ directory
- Module lifecycle (load/unload)
- Module discovery and registration
- Intent routing to appropriate modules
"""

import importlib
import importlib.util
import os
from typing import Dict, List, Optional, Type
from pathlib import Path

from assistmint.core.modules.base import BaseModule, ModuleContext, ModuleResult, ModuleCapability
from assistmint.core.logger import module as log_module, router


class ModuleLoader:
    """
    Dynamic module loader and router.

    Usage:
        loader = ModuleLoader()
        loader.discover_modules()  # Find all modules in modules/

        # Route text to best module
        result = loader.route("add meeting tomorrow at 3pm", context)
    """

    _instance: Optional["ModuleLoader"] = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._modules: Dict[str, BaseModule] = {}
        self._module_classes: Dict[str, Type[BaseModule]] = {}
        self._initialized = True

    def register_module(self, module_class: Type[BaseModule]) -> bool:
        """
        Register a module class.

        Args:
            module_class: Class inheriting from BaseModule

        Returns:
            True if registration succeeded
        """
        try:
            # Instantiate to get name
            instance = module_class()
            name = instance.name

            if name in self._module_classes:
                log_module(f"Module already registered: {name}")
                return False

            self._module_classes[name] = module_class
            log_module(f"Registered: {name}")
            return True
        except Exception as e:
            log_module(f"Failed to register module: {e}")
            return False

    def load_module(self, name: str) -> Optional[BaseModule]:
        """
        Load and initialize a registered module.

        Args:
            name: Module name

        Returns:
            Loaded module instance or None
        """
        if name in self._modules:
            return self._modules[name]

        if name not in self._module_classes:
            log_module(f"Unknown module: {name}")
            return None

        try:
            module = self._module_classes[name]()
            module.on_load()
            self._modules[name] = module
            log_module(f"Loaded: {name}")
            return module
        except Exception as e:
            log_module(f"Failed to load {name}: {e}")
            return None

    def unload_module(self, name: str) -> bool:
        """
        Unload a module and release its resources.

        Args:
            name: Module name

        Returns:
            True if unload succeeded
        """
        if name not in self._modules:
            return False

        try:
            module = self._modules[name]
            module.on_unload()
            del self._modules[name]
            log_module(f"Unloaded: {name}")
            return True
        except Exception as e:
            log_module(f"Failed to unload {name}: {e}")
            return False

    def get_module(self, name: str) -> Optional[BaseModule]:
        """Get a loaded module by name."""
        return self._modules.get(name)

    def get_loaded_modules(self) -> List[BaseModule]:
        """Get all loaded modules."""
        return list(self._modules.values())

    def get_registered_modules(self) -> List[str]:
        """Get names of all registered modules."""
        return list(self._module_classes.keys())

    def discover_modules(self, modules_dir: str = None) -> int:
        """
        Discover and register modules from directory.

        Args:
            modules_dir: Path to modules directory (default: ./modules/)

        Returns:
            Number of modules discovered
        """
        if modules_dir is None:
            # Default to modules/ relative to this file's grandparent
            base_path = Path(__file__).parent.parent.parent
            modules_dir = base_path / "modules"

        modules_path = Path(modules_dir)
        if not modules_path.exists():
            log_module(f"Modules directory not found: {modules_path}")
            return 0

        discovered = 0

        # Look for module.py in each subdirectory
        for subdir in modules_path.iterdir():
            if not subdir.is_dir():
                continue

            module_file = subdir / "module.py"
            if not module_file.exists():
                continue

            try:
                # Import the module
                module_name = f"modules.{subdir.name}.module"
                spec = importlib.util.spec_from_file_location(module_name, module_file)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    # Look for classes inheriting from BaseModule
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if (isinstance(attr, type) and
                            issubclass(attr, BaseModule) and
                            attr is not BaseModule and
                            not attr_name.startswith('_')):
                            if self.register_module(attr):
                                discovered += 1

            except Exception as e:
                log_module(f"Failed to discover {subdir.name}: {e}")

        log_module(f"Discovered {discovered} modules")
        return discovered

    def load_all_modules(self) -> int:
        """
        Load all registered modules.

        Returns:
            Number of modules loaded
        """
        loaded = 0
        for name in self._module_classes:
            if self.load_module(name):
                loaded += 1
        return loaded

    def route(self, text: str, context: ModuleContext, intent: Optional[str] = None) -> Optional[ModuleResult]:
        """
        Route input to the best matching module.

        Args:
            text: Transcribed text
            context: ModuleContext with device, session, etc.
            intent: Optional intent from voice2json

        Returns:
            ModuleResult from the best matching module, or None
        """
        text_lower = text.lower().strip()

        # Get all loaded modules sorted by priority (highest first)
        modules = sorted(
            self._modules.values(),
            key=lambda m: m.priority,
            reverse=True
        )

        best_module = None
        best_confidence = 0.0

        # Find best matching module
        for module in modules:
            try:
                confidence = module.can_handle(text_lower, intent)
                router(f"{module.name}: confidence={confidence:.2f}")

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_module = module
            except Exception as e:
                router(f"{module.name} error: {e}")

        # Threshold for accepting a match
        if best_module and best_confidence >= 0.5:
            router(f"Routing to: {best_module.name} (confidence={best_confidence:.2f})")
            try:
                # Pass intent to context so modules can use it for routing
                context.intent = intent
                return best_module.execute(context)
            except Exception as e:
                router(f"Execution error in {best_module.name}: {e}")
                return ModuleResult(
                    text=f"Sorry, there was an error: {e}",
                    success=False
                )

        router(f"No module matched (best: {best_module.name if best_module else 'none'}, conf={best_confidence:.2f})")
        return None

    def get_help_text(self) -> str:
        """Get combined help text from all loaded modules."""
        lines = ["Available commands:"]
        for module in sorted(self._modules.values(), key=lambda m: m.name):
            help_text = module.get_help()
            triggers = module.get_triggers_text()
            lines.append(f"\n{help_text}")
            if triggers:
                lines.append(f"  {triggers}")
        return "\n".join(lines)


# Global instance
_module_loader: Optional[ModuleLoader] = None


def get_module_loader() -> ModuleLoader:
    """Get the global ModuleLoader instance."""
    global _module_loader
    if _module_loader is None:
        _module_loader = ModuleLoader()
    return _module_loader


# Test
if __name__ == "__main__":
    loader = get_module_loader()
    print(f"Registered: {loader.get_registered_modules()}")

    # Discover modules
    discovered = loader.discover_modules()
    print(f"Discovered: {discovered}")

    # Load all
    loaded = loader.load_all_modules()
    print(f"Loaded: {loaded}")

    print(f"Modules: {[m.name for m in loader.get_loaded_modules()]}")
