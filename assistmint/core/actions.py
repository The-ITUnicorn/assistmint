"""
System Actions - Direct xdotool keyboard/browser actions.

Handles voice2json intents that don't need LLM processing.
Configuration loaded from config_intents.py for easy customization.
"""

import subprocess
from typing import Optional
from assistmint.core.logger import cmd

# Import configuration from centralized config file
from assistmint.config_intents import (
    SYSTEM_ACTIONS,
    XDOTOOL_KEYS,
    ACTION_RESPONSES
)


def execute_action(action: str) -> Optional[str]:
    """
    Execute a system action and return response text (or None if not handled).

    Actions are configured in config_intents.py:
    - XDOTOOL_KEYS: Maps action → key sequence
    - ACTION_RESPONSES: Maps action → TTS response (None = silent)

    Returns:
        Response text to speak, or None if action not handled here.
    """
    # Check if this action has a key mapping
    if action in XDOTOOL_KEYS:
        key = XDOTOOL_KEYS[action]
        _xdotool_key(key)
        print(cmd(f"Action: {action} ({key})"))
        return ACTION_RESPONSES.get(action)

    # Volume control (via pactl - not a key press)
    if action == "volume_up":
        _run_cmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"])
        print(cmd("Action: volume_up (+5%)"))
        return ACTION_RESPONSES.get(action, "Volume up")

    if action == "volume_down":
        _run_cmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"])
        print(cmd("Action: volume_down (-5%)"))
        return ACTION_RESPONSES.get(action, "Volume down")

    if action == "volume_mute":
        _run_cmd(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
        print(cmd("Action: volume_mute (toggle)"))
        return ACTION_RESPONSES.get(action, "Mute toggled")

    # Time/Date (Python datetime - no external command)
    if action == "what_time":
        import datetime
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M")
        print(cmd(f"Action: what_time → {time_str}"))
        return f"It's {time_str}"

    if action == "what_date":
        import datetime
        now = datetime.datetime.now()
        date_str = now.strftime("%A, %B %d")
        print(cmd(f"Action: what_date → {date_str}"))
        return f"Today is {date_str}"

    # Open browser (xdg-open - not a key press)
    if action == "open_browser":
        _run_cmd(["xdg-open", "https://www.google.com"])
        print(cmd("Action: open_browser"))
        return ACTION_RESPONSES.get(action, "Opening browser")

    # Sleep mode - handled in main loop, just return response
    if action == "sleep":
        print(cmd("Action: sleep"))
        return ACTION_RESPONSES.get(action, "Going to sleep")

    # Not a system action
    return None


def _xdotool_key(key: str) -> bool:
    """Send key press via xdotool."""
    try:
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", key],
            check=True,
            timeout=2
        )
        return True
    except Exception as e:
        print(cmd(f"xdotool error: {e}"))
        return False


def _run_cmd(cmd_list: list) -> bool:
    """Run a shell command."""
    try:
        subprocess.run(cmd_list, check=True, timeout=5)
        return True
    except Exception as e:
        print(f"Command error: {e}")
        return False


def is_system_action(action: str) -> bool:
    """
    Check if action should be handled as a system action.

    System actions are defined in config_intents.py SYSTEM_ACTIONS set.
    """
    return action in SYSTEM_ACTIONS
