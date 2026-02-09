"""
Resource management for Assistmint.

Handles GPU/CPU allocation and coordination between modules.
"""

from assistmint.core.resources.manager import ResourceManager, ResourceType, get_resource_manager

__all__ = ["ResourceManager", "ResourceType", "get_resource_manager"]
