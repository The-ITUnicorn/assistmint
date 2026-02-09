"""
Unified logging for Assistmint.

Provides colored terminal output with optional emojis.
Replaces colors.py with a more flexible logging system.
"""

import sys
from typing import Optional
from enum import Enum


class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


# ANSI escape codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Foreground colors
BLACK = "\033[30m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

# Tag colors mapping
TAG_COLORS = {
    "CMD": YELLOW,
    "STT": CYAN,
    "TTS": MAGENTA,
    "WAKE": GREEN,
    "V2J": BLUE,
    "LEARN": GREEN,
    "SESSION": YELLOW,
    "DICTATE": CYAN,
    "DATE": DIM,
    "ERROR": RED,
    "ROUTER": BLUE,
    "MODULE": GREEN,
    "RESOURCE": CYAN,
    "CORE": WHITE,
}

# Tag emojis
TAG_EMOJIS = {
    "CMD": "⚡",
    "STT": "🎤",
    "TTS": "🔊",
    "WAKE": "👂",
    "V2J": "🧠",
    "LEARN": "📚",
    "SESSION": "💬",
    "DICTATE": "✍️",
    "DATE": "📅",
    "ERROR": "❌",
    "ROUTER": "🔀",
    "MODULE": "📦",
    "RESOURCE": "🖥️",
    "CORE": "🧠",
}

# Global settings (can be modified at runtime)
_use_emojis = False
_log_level = LogLevel.INFO


def set_use_emojis(enabled: bool):
    """Enable or disable emoji output."""
    global _use_emojis
    _use_emojis = enabled


def set_log_level(level: LogLevel):
    """Set minimum log level."""
    global _log_level
    _log_level = level


def tag(name: str, message: str = "") -> str:
    """Format a colored tag with optional message.

    Usage:
        print(tag("CMD", "Processing command"))
        print(tag("STT") + " Transcribing...")
    """
    color = TAG_COLORS.get(name, WHITE)
    emoji = TAG_EMOJIS.get(name, "") if _use_emojis else ""
    prefix = f"{emoji} " if emoji else ""
    if message:
        return f"{prefix}{color}[{name}]{RESET} {message}"
    return f"{prefix}{color}[{name}]{RESET}"


def log(category: str, message: str, level: LogLevel = LogLevel.INFO):
    """Log a message with category tag."""
    if level.value >= _log_level.value:
        print(tag(category.upper(), message))


# Convenience functions for common categories
def cmd(msg: str) -> str:
    """Command processing log."""
    return tag("CMD", msg)


def stt(msg: str) -> str:
    """Speech-to-text log."""
    return tag("STT", msg)


def tts(msg: str) -> str:
    """Text-to-speech log."""
    return tag("TTS", msg)


def wake(msg: str) -> str:
    """Wake word detection log."""
    return tag("WAKE", msg)


def v2j(msg: str) -> str:
    """Voice2json intent log."""
    return tag("V2J", msg)


def learn(msg: str) -> str:
    """Learning/correction log."""
    return tag("LEARN", msg)


def session(msg: str) -> str:
    """Session management log."""
    return tag("SESSION", msg)


def dictate(msg: str) -> str:
    """Dictation mode log."""
    return tag("DICTATE", msg)


def router(msg: str) -> str:
    """Router/intent log."""
    return tag("ROUTER", msg)


def module(msg: str) -> str:
    """Module lifecycle log."""
    return tag("MODULE", msg)


def resource(msg: str) -> str:
    """Resource management log."""
    return tag("RESOURCE", msg)


def error(msg: str) -> str:
    """Error log."""
    return tag("ERROR", msg)


def debug(category: str, msg: str):
    """Debug-level log."""
    log(category, msg, LogLevel.DEBUG)


def info(category: str, msg: str):
    """Info-level log."""
    log(category, msg, LogLevel.INFO)


def warning(category: str, msg: str):
    """Warning-level log."""
    log(category, msg, LogLevel.WARNING)


# Test
if __name__ == "__main__":
    print(cmd("Processing: help me"))
    print(stt("Transcribing..."))
    print(tts("Speaking: Hello world"))
    print(wake("Listening... (say 'Hey Jarvis')"))
    print(v2j("Intent: Help (en) conf=1.00"))
    print(learn("Saved: 'calander' → 'calendar'"))
    print(session("Loaded 5 messages"))
    print(dictate("Typing: hello world"))
    print(router("Routing to: chat"))
    print(module("Loaded: calendar"))
    print(resource("GPU allocated to: STT"))
    print(error("Something went wrong"))
