"""
Resource Manager - GPU/CPU coordination for Assistmint.

Handles:
- GPU allocation with CPU fallback
- Resource release between operations
- Memory management for low-memory systems
- Auto-unload of inactive models to free VRAM

Design:
- GPU is released between operations (STT -> release -> TTS)
- Fallback chain: GPU available -> queue/fallback to CPU -> CPU-only mode
- Thread-safe resource acquisition
- Auto-unload models after configurable inactivity period
"""

import threading
import time
from enum import Enum
from typing import Optional, Dict, Callable
from dataclasses import dataclass, field
from assistmint.core.logger import resource


class ResourceType(Enum):
    """Types of GPU resources that can be allocated."""
    STT = "stt"        # Speech-to-text (Whisper)
    TTS = "tts"        # Text-to-speech (Piper)
    LLM = "llm"        # Language model (Ollama - external)


@dataclass
class ResourceAllocation:
    """Tracks an active resource allocation."""
    resource_type: ResourceType
    owner: str
    device: str  # "cuda" or "cpu"
    timestamp: float
    last_used: float = field(default_factory=time.time)


# Default auto-unload timeout (seconds)
DEFAULT_UNLOAD_TIMEOUT = 60.0  # 1 minute of inactivity


class ResourceManager:
    """
    Centralized GPU/CPU resource management.

    Usage:
        rm = ResourceManager()

        # Request GPU for STT
        if rm.request_gpu(ResourceType.STT, "whisper"):
            # Use GPU
            rm.release_gpu(ResourceType.STT)
        else:
            # Fallback to CPU
            pass
    """

    _instance: Optional["ResourceManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern - only one ResourceManager exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._gpu_available = False
        self._gpu_device_id = 0
        self._gpu_name = "Unknown"
        self._gpu_memory_gb = 0
        self._force_cpu = False

        self._allocations: Dict[ResourceType, ResourceAllocation] = {}
        self._allocation_lock = threading.Lock()

        # Auto-unload configuration
        self._unload_timeout = DEFAULT_UNLOAD_TIMEOUT
        self._unload_callbacks: Dict[ResourceType, Callable] = {}
        self._auto_unload_enabled = False
        self._unload_timer: Optional[threading.Timer] = None

        self._detect_gpu()
        self._initialized = True

    def _detect_gpu(self):
        """Detect available GPU and its capabilities."""
        try:
            import torch
            if torch.cuda.is_available():
                # Get best GPU (most VRAM)
                num_gpus = torch.cuda.device_count()
                best_gpu = 0
                best_vram = 0

                for i in range(num_gpus):
                    vram = torch.cuda.get_device_properties(i).total_memory
                    if vram > best_vram:
                        best_vram = vram
                        best_gpu = i

                self._gpu_available = True
                self._gpu_device_id = best_gpu
                self._gpu_name = torch.cuda.get_device_name(best_gpu)
                self._gpu_memory_gb = best_vram // (1024**3)

                resource(f"GPU detected: {self._gpu_name} ({self._gpu_memory_gb}GB)")
            else:
                resource("No CUDA GPU available - CPU mode")
                self._gpu_available = False
        except ImportError:
            resource("PyTorch not installed - CPU mode")
            self._gpu_available = False
        except Exception as e:
            resource(f"GPU detection failed: {e} - CPU mode")
            self._gpu_available = False

    @property
    def gpu_available(self) -> bool:
        """Check if GPU is available (and not forced to CPU)."""
        return self._gpu_available and not self._force_cpu

    @property
    def gpu_device_id(self) -> int:
        """Get the selected GPU device ID."""
        return self._gpu_device_id

    @property
    def gpu_name(self) -> str:
        """Get GPU name."""
        return self._gpu_name

    @property
    def gpu_memory_gb(self) -> int:
        """Get GPU memory in GB."""
        return self._gpu_memory_gb

    def force_cpu_mode(self, enabled: bool = True):
        """Force CPU mode (for low-memory systems or testing)."""
        self._force_cpu = enabled
        if enabled:
            resource("Forced CPU mode enabled")
        else:
            resource("Forced CPU mode disabled")

    def request_gpu(self, resource_type: ResourceType, owner: str) -> bool:
        """
        Request GPU for a specific resource type.

        Args:
            resource_type: Type of resource (STT, TTS, LLM)
            owner: Name of the requesting component

        Returns:
            True if GPU was allocated, False if should use CPU
        """
        if not self.gpu_available:
            resource(f"{owner} using CPU (no GPU)")
            return False

        with self._allocation_lock:
            # Check if resource is already allocated
            if resource_type in self._allocations:
                existing = self._allocations[resource_type]
                if existing.owner != owner:
                    resource(f"{owner} waiting for GPU (held by {existing.owner})")
                    # Could implement queue here, for now just return False
                    return False

            # Allocate GPU
            import time
            self._allocations[resource_type] = ResourceAllocation(
                resource_type=resource_type,
                owner=owner,
                device="cuda",
                timestamp=time.time()
            )
            resource(f"GPU allocated: {resource_type.value} -> {owner}")
            return True

    def release_gpu(self, resource_type: ResourceType):
        """
        Release GPU allocation for a resource type.

        Args:
            resource_type: Type of resource to release
        """
        with self._allocation_lock:
            if resource_type in self._allocations:
                alloc = self._allocations.pop(resource_type)
                resource(f"GPU released: {resource_type.value} <- {alloc.owner}")

                # Try to free GPU memory
                self._clear_gpu_cache()

    def _clear_gpu_cache(self):
        """Clear GPU memory cache."""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except:
            pass

    def get_device(self, resource_type: ResourceType) -> str:
        """
        Get device string for a resource type.

        Returns:
            "cuda" if GPU is allocated, "cpu" otherwise
        """
        with self._allocation_lock:
            if resource_type in self._allocations:
                return self._allocations[resource_type].device
        return "cpu"

    def get_compute_type(self, resource_type: ResourceType) -> str:
        """
        Get compute type for a resource type.

        Returns:
            "float16" for GPU, "int8" for CPU
        """
        device = self.get_device(resource_type)
        return "float16" if device == "cuda" else "int8"

    def get_status(self) -> Dict:
        """Get current resource allocation status."""
        with self._allocation_lock:
            return {
                "gpu_available": self.gpu_available,
                "gpu_name": self._gpu_name,
                "gpu_memory_gb": self._gpu_memory_gb,
                "force_cpu": self._force_cpu,
                "allocations": {
                    rt.value: {
                        "owner": alloc.owner,
                        "device": alloc.device
                    }
                    for rt, alloc in self._allocations.items()
                }
            }

    def release_all(self):
        """Release all GPU allocations (cleanup)."""
        with self._allocation_lock:
            for rt in list(self._allocations.keys()):
                alloc = self._allocations.pop(rt)
                resource(f"GPU released (cleanup): {rt.value} <- {alloc.owner}")
            self._clear_gpu_cache()

    # ===== AUTO-UNLOAD FUNCTIONALITY =====

    def register_unload_callback(self, resource_type: ResourceType, callback: Callable):
        """
        Register a callback to unload a resource type.

        Args:
            resource_type: Type of resource (STT, TTS)
            callback: Function to call to unload the model (no arguments)
        """
        self._unload_callbacks[resource_type] = callback
        resource(f"Registered unload callback for {resource_type.value}")

    def set_unload_timeout(self, seconds: float):
        """Set the auto-unload timeout in seconds."""
        self._unload_timeout = seconds
        resource(f"Auto-unload timeout set to {seconds}s")

    def enable_auto_unload(self, enabled: bool = True):
        """
        Enable or disable auto-unload of inactive models.

        When enabled, models will be automatically unloaded after
        the configured timeout of inactivity.
        """
        self._auto_unload_enabled = enabled
        if enabled:
            resource(f"Auto-unload enabled (timeout: {self._unload_timeout}s)")
            self._schedule_unload_check()
        else:
            resource("Auto-unload disabled")
            if self._unload_timer:
                self._unload_timer.cancel()
                self._unload_timer = None

    def touch(self, resource_type: ResourceType):
        """
        Update last-used timestamp for a resource.

        Call this when using a resource to prevent auto-unload.
        """
        with self._allocation_lock:
            if resource_type in self._allocations:
                self._allocations[resource_type].last_used = time.time()

    def _schedule_unload_check(self):
        """Schedule the next auto-unload check."""
        if not self._auto_unload_enabled:
            return

        # Cancel existing timer
        if self._unload_timer:
            self._unload_timer.cancel()

        # Schedule new check (check every 10 seconds)
        self._unload_timer = threading.Timer(10.0, self._check_and_unload)
        self._unload_timer.daemon = True
        self._unload_timer.start()

    def _check_and_unload(self):
        """Check for inactive resources and unload them."""
        if not self._auto_unload_enabled:
            return

        now = time.time()
        to_unload = []

        with self._allocation_lock:
            for rt, alloc in self._allocations.items():
                idle_time = now - alloc.last_used
                if idle_time > self._unload_timeout:
                    to_unload.append(rt)
                    resource(f"Auto-unload: {rt.value} idle for {idle_time:.1f}s")

        # Unload outside the lock to avoid deadlock
        for rt in to_unload:
            if rt in self._unload_callbacks:
                try:
                    self._unload_callbacks[rt]()
                except Exception as e:
                    resource(f"Auto-unload error for {rt.value}: {e}")

        # Schedule next check
        self._schedule_unload_check()

    def get_vram_usage(self) -> Dict:
        """
        Get current VRAM usage information.

        Returns dict with:
            - total_mb: Total VRAM in MB
            - used_mb: Used VRAM in MB
            - free_mb: Free VRAM in MB
            - percent: Usage percentage
        """
        try:
            import torch
            if torch.cuda.is_available():
                device = self._gpu_device_id
                total = torch.cuda.get_device_properties(device).total_memory
                reserved = torch.cuda.memory_reserved(device)
                allocated = torch.cuda.memory_allocated(device)

                return {
                    "total_mb": total // (1024**2),
                    "reserved_mb": reserved // (1024**2),
                    "allocated_mb": allocated // (1024**2),
                    "free_mb": (total - reserved) // (1024**2),
                    "percent": (reserved / total) * 100 if total > 0 else 0
                }
        except:
            pass

        return {"total_mb": 0, "reserved_mb": 0, "allocated_mb": 0, "free_mb": 0, "percent": 0}


# Global instance
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get the global ResourceManager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


# Test
if __name__ == "__main__":
    rm = get_resource_manager()
    print(f"GPU available: {rm.gpu_available}")
    print(f"GPU name: {rm.gpu_name}")
    print(f"GPU memory: {rm.gpu_memory_gb}GB")

    # Test allocation
    if rm.request_gpu(ResourceType.STT, "whisper"):
        print("STT got GPU")
        print(f"Device: {rm.get_device(ResourceType.STT)}")
        rm.release_gpu(ResourceType.STT)

    print(f"Status: {rm.get_status()}")
