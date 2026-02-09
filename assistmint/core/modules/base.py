"""
BaseModule - Abstract base class for all Assistmint modules.

All skill modules (chat, calendar, dictation, terminal) inherit from this class.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Dict, Any, Optional, List


class ModuleCapability(Flag):
    """Capabilities that modules can have."""
    NONE = 0
    TEXT_INPUT = auto()      # Accepts text input
    TEXT_OUTPUT = auto()     # Returns text output
    CONTINUOUS = auto()      # Can run in continuous mode (skip wake word)
    MULTI_TURN = auto()      # Supports multi-turn dialogs
    EXTERNAL_API = auto()    # Uses external API (Ollama, etc.)
    SYSTEM_ACCESS = auto()   # Accesses system (terminal, files)
    CALENDAR = auto()        # Calendar operations
    LEARNING = auto()        # Learning/correction capability


@dataclass
class ModuleResult:
    """Result returned by module execution."""
    text: str                           # Text for TTS to speak
    success: bool = True                # Did the operation succeed?
    continue_listening: bool = False    # Skip wake word for next input?
    requires_confirmation: bool = False # Waiting for user confirmation?
    data: Dict[str, Any] = field(default_factory=dict)  # Optional structured data


@dataclass
class ModuleContext:
    """Context passed to module execution."""
    text: str                           # Original transcribed text
    text_lower: str                     # Lowercase version
    language: Optional[str] = None      # Detected language ("en", "nl", None)
    selected_device: Any = None         # Microphone device
    samplerate: int = 16000             # Audio sample rate
    session_data: Dict[str, Any] = field(default_factory=dict)  # Session state
    intent: Optional[str] = None        # voice2json intent (add_calendar, check_calendar, etc.)


class BaseModule(ABC):
    """
    Abstract base class for Assistmint modules.

    All modules must implement:
    - name: Module identifier
    - capabilities: What the module can do
    - can_handle(text, intent): Confidence score for handling input
    - execute(text, context): Process input and return result

    Optional overrides:
    - on_load(): Called when module is loaded
    - on_unload(): Called when module is unloaded
    - get_help(): Return help text for this module
    """

    def __init__(self):
        self._loaded = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique module identifier (e.g., 'chat', 'calendar')."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> ModuleCapability:
        """Module capabilities flags."""
        pass

    @property
    def description(self) -> str:
        """Human-readable module description."""
        return f"{self.name} module"

    @property
    def triggers(self) -> List[str]:
        """List of keywords/phrases that trigger this module."""
        return []

    @property
    def priority(self) -> int:
        """Module priority (higher = checked first). Default: 50."""
        return 50

    @abstractmethod
    def can_handle(self, text: str, intent: Optional[str] = None) -> float:
        """
        Determine if this module can handle the input.

        Args:
            text: The transcribed text
            intent: Optional intent from voice2json

        Returns:
            Confidence score 0.0-1.0 (0 = cannot handle, 1 = perfect match)
        """
        pass

    @abstractmethod
    def execute(self, context: ModuleContext) -> ModuleResult:
        """
        Execute the module's functionality.

        Args:
            context: ModuleContext with text, device, etc.

        Returns:
            ModuleResult with text for TTS and status flags
        """
        pass

    def on_load(self) -> None:
        """Called when module is loaded. Override for initialization."""
        self._loaded = True

    def on_unload(self) -> None:
        """Called when module is unloaded. Override for cleanup."""
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Check if module is currently loaded."""
        return self._loaded

    def get_help(self) -> str:
        """Return help text for this module."""
        return f"{self.name}: {self.description}"

    def get_triggers_text(self) -> str:
        """Return formatted trigger text for help."""
        if self.triggers:
            return f"Triggers: {', '.join(self.triggers)}"
        return ""


class FallbackModule(BaseModule):
    """
    Special module that handles unmatched input.

    This module always has lowest priority and accepts any input.
    Typically routes to LLM (Ollama) for general Q&A.
    """

    @property
    def name(self) -> str:
        return "fallback"

    @property
    def capabilities(self) -> ModuleCapability:
        return ModuleCapability.TEXT_INPUT | ModuleCapability.TEXT_OUTPUT | ModuleCapability.EXTERNAL_API

    @property
    def description(self) -> str:
        return "General Q&A (routes to LLM)"

    @property
    def priority(self) -> int:
        return 0  # Lowest priority - only handles if nothing else matches

    def can_handle(self, text: str, intent: Optional[str] = None) -> float:
        """Always returns low confidence - only used as fallback."""
        return 0.1

    def execute(self, context: ModuleContext) -> ModuleResult:
        """Override in subclass to implement LLM routing."""
        return ModuleResult(
            text="I don't know how to handle that.",
            success=False
        )
