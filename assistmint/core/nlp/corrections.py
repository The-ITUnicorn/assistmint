"""
Corrections/Learning System - Auto-correction of transcribed text.

Allows users to teach the assistant new corrections.
"""

import json
import os
from typing import Dict, Optional

from assistmint.core.logger import learn

CORRECTIONS_FILE = os.path.expanduser("~/.assistmint_corrections.json")

# Built-in corrections for common Whisper mishearings (Dutch)
# These are applied automatically, user can add more via "learn that X is Y"
DEFAULT_CORRECTIONS = {
    # Dutch words Whisper often mishears
    "geveerjaardagsfeestje": "verjaardagsfeestje",
    "geverjaardagsfeestje": "verjaardagsfeestje",
    "verjaarsdagfeestje": "verjaardagsfeestje",
    "sint willenbrocht": "Sint Willebrord",
    "sint willenbrord": "Sint Willebrord",
    "sint willebrocht": "Sint Willebrord",
    # Common English->Dutch mishearings
    "ditch": "Dutch",
    "deutch": "Dutch",
    # Other common mishearings
    "tikkie": "Tikkie",
    "i deal": "iDEAL",
}


class CorrectionEngine:
    """
    Manages corrections for speech recognition errors.

    Features:
    - Persistent storage
    - Auto-correction on transcription
    - Add/remove corrections
    """

    def __init__(self, corrections_file: str = CORRECTIONS_FILE):
        self._corrections_file = corrections_file
        self._corrections: Dict[str, str] = {}
        self._all_corrections: Dict[str, str] = {}  # defaults + user
        self.load()

    def load(self) -> Dict[str, str]:
        """Load corrections dictionary from file."""
        if os.path.exists(self._corrections_file):
            try:
                with open(self._corrections_file, 'r') as f:
                    self._corrections = json.load(f)
            except json.JSONDecodeError:
                self._corrections = {}

        # Merge defaults with user corrections (user overrides defaults)
        self._all_corrections = {**DEFAULT_CORRECTIONS, **self._corrections}
        return self._corrections

    def save(self):
        """Save corrections dictionary to file."""
        with open(self._corrections_file, 'w') as f:
            json.dump(self._corrections, f, indent=2)

    def apply(self, text: str) -> str:
        """Apply stored corrections to transcribed text."""
        original = text.lower()

        # Use all corrections (defaults + user)
        for wrong, right in self._all_corrections.items():
            if wrong.lower() in original:
                text = text.lower().replace(wrong.lower(), right)
                learn(f"Auto-corrected: '{wrong}' -> '{right}'")

        return text

    def add(self, wrong: str, right: str):
        """Add a new correction to the dictionary."""
        self._corrections[wrong.lower()] = right
        self._all_corrections[wrong.lower()] = right  # Update merged dict
        self.save()
        learn(f"Saved: '{wrong}' -> '{right}'")

    def remove(self, wrong: str) -> bool:
        """Remove a correction from the dictionary."""
        if wrong.lower() in self._corrections:
            del self._corrections[wrong.lower()]
            # Refresh all_corrections (defaults remain, user correction removed)
            self._all_corrections = {**DEFAULT_CORRECTIONS, **self._corrections}
            self.save()
            learn(f"Removed correction for '{wrong}'")
            return True
        return False

    def list(self) -> Dict[str, str]:
        """List all stored corrections."""
        if self._corrections:
            print("\n=== Stored Corrections ===")
            for wrong, right in self._corrections.items():
                print(f"  '{wrong}' -> '{right}'")
            print()
        else:
            learn("No corrections stored yet.")
        return self._corrections

    def clear(self):
        """Clear all corrections."""
        self._corrections = {}
        self.save()


# Global correction engine instance
_correction_engine: Optional[CorrectionEngine] = None


def get_correction_engine() -> CorrectionEngine:
    """Get the global correction engine instance."""
    global _correction_engine
    if _correction_engine is None:
        _correction_engine = CorrectionEngine()
    return _correction_engine


# Backward compatibility functions
def load_corrections() -> Dict[str, str]:
    """Load corrections (backward compatibility)."""
    return get_correction_engine().load()


def save_corrections(corrections: Dict[str, str]):
    """Save corrections (backward compatibility)."""
    engine = get_correction_engine()
    engine._corrections = corrections
    engine.save()


def apply_corrections(text: str) -> str:
    """Apply corrections (backward compatibility)."""
    return get_correction_engine().apply(text)


def add_correction(wrong: str, right: str):
    """Add correction (backward compatibility)."""
    get_correction_engine().add(wrong, right)


def remove_correction(wrong: str) -> bool:
    """Remove correction (backward compatibility)."""
    return get_correction_engine().remove(wrong)


def list_corrections() -> Dict[str, str]:
    """List corrections (backward compatibility)."""
    return get_correction_engine().list()
