"""
Assistmint Core - The brain that ALWAYS works.

This module provides:
- Resource management (GPU/CPU fallback)
- Audio I/O (STT, TTS, Wake word)
- NLP (Intent routing, corrections, filters)
- Module management (load/unload modules)
"""

from assistmint.core.logger import log, cmd, stt, tts, wake, session, error

__version__ = "2.0.0"
__all__ = ["log", "cmd", "stt", "tts", "wake", "session", "error"]
