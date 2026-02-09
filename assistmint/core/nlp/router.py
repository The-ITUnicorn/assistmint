"""
Intent Router - Route transcribed text to appropriate modules.

Uses voice2json for intent recognition with fallback to keyword matching.
Configuration is loaded from config_intents.py for easy customization.
"""

import subprocess
import json
import os
from typing import Dict, Any, Optional, List

from assistmint.core.logger import v2j, router, error

# Import configuration from centralized config file
from assistmint.config_intents import (
    INTENT_ACTIONS,
    KEYWORD_FALLBACK,
    VOICE2JSON_PROFILES as PROFILES
)

# Debug flag
DEBUG = os.environ.get("VOICE2JSON_DEBUG", "0") == "1"


class IntentRouter:
    """
    Intent recognition and routing.

    Uses voice2json Docker container for accurate intent recognition,
    with fallback to keyword matching.
    """

    def __init__(self):
        self._voice2json_available = self._check_voice2json()

    def _check_voice2json(self) -> bool:
        """Check if voice2json Docker image is available."""
        try:
            result = subprocess.run(
                ["docker", "images", "-q", "synesthesiam/voice2json"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return bool(result.stdout.strip())
        except:
            return False

    def _run_voice2json(
        self,
        profile: str,
        command: str,
        args: List[str] = None,
        input_text: str = None
    ) -> Optional[str]:
        """Run voice2json command via Docker."""
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{os.environ['HOME']}:{os.environ['HOME']}",
            "-w", os.getcwd(),
            "-e", f"HOME={os.environ['HOME']}",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "synesthesiam/voice2json",
            "--profile", profile,
            command
        ]
        if args:
            cmd.extend(args)

        try:
            if input_text:
                result = subprocess.run(cmd, input=input_text, capture_output=True, text=True, timeout=10)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if DEBUG:
                v2j(f"Command: {' '.join(cmd)}")
                if result.stderr:
                    v2j(f"Stderr: {result.stderr[:200]}")

            return result.stdout.strip() if result.stdout else None
        except subprocess.TimeoutExpired:
            error("Docker command timed out")
            return None
        except Exception as e:
            error(f"{e}")
            return None

    def recognize_intent(self, text: str, language: str = "auto") -> Dict[str, Any]:
        """
        Recognize intent from text using voice2json.

        Args:
            text: The transcribed text to analyze
            language: "en", "nl", or "auto" (tries both)

        Returns:
            Dict with 'intent', 'confidence', 'action', 'language', 'entities'
        """
        result = {
            "intent": None,
            "confidence": 0.0,
            "action": "ollama",  # Default: send to LLM
            "language": None,
            "entities": [],
            "text": text
        }

        if not self._voice2json_available:
            router("voice2json not available, using keyword fallback")
            return self._keyword_fallback(text)

        profiles_to_try = []
        if language == "auto":
            profiles_to_try = [("en", PROFILES["en"]), ("nl", PROFILES["nl"])]
        elif language in PROFILES:
            profiles_to_try = [(language, PROFILES[language])]
        else:
            v2j(f"Unknown language: {language}")
            return result

        best_match = None
        best_confidence = 0.0

        for lang, profile in profiles_to_try:
            output = self._run_voice2json(profile, "recognize-intent", ["--text-input", text])

            if output:
                try:
                    data = json.loads(output)
                    intent_name = data.get("intent", {}).get("name")
                    confidence = data.get("intent", {}).get("confidence", 0.0)

                    if DEBUG:
                        v2j(f"{lang}: intent={intent_name}, confidence={confidence}")

                    if intent_name and confidence > best_confidence:
                        best_confidence = confidence
                        best_match = {
                            "intent": intent_name,
                            "confidence": confidence,
                            "action": INTENT_ACTIONS.get(intent_name, "ollama"),
                            "language": lang,
                            "entities": data.get("entities", []),
                            "slots": data.get("slots", {}),
                            "text": text
                        }
                except json.JSONDecodeError as e:
                    if DEBUG:
                        v2j(f"JSON parse error: {e}")

        if best_match and best_confidence > 0.5:
            return best_match

        # voice2json didn't match - try keyword fallback
        router("voice2json no match, trying keyword fallback")
        keyword_result = self._keyword_fallback(text)
        if keyword_result["intent"]:
            return keyword_result

        return result

    def _keyword_fallback(self, text: str) -> Dict[str, Any]:
        """
        Fallback keyword-based intent recognition.

        Used when voice2json is not available.
        Patterns loaded from config_intents.py KEYWORD_FALLBACK.
        """
        text_lower = text.lower().strip()

        result = {
            "intent": None,
            "confidence": 0.0,
            "action": "ollama",
            "language": None,
            "entities": [],
            "text": text
        }

        # Use patterns from config_intents.py
        for intent_name, (keywords, action) in KEYWORD_FALLBACK.items():
            for keyword in keywords:
                if keyword in text_lower:
                    result["intent"] = intent_name
                    result["confidence"] = 0.8
                    result["action"] = action
                    return result

        return result

    def get_available_intents(self) -> List[str]:
        """Get list of available intents."""
        return list(INTENT_ACTIONS.keys())


# Global router instance
_intent_router: Optional[IntentRouter] = None


def get_intent_router() -> IntentRouter:
    """Get the global intent router instance."""
    global _intent_router
    if _intent_router is None:
        _intent_router = IntentRouter()
    return _intent_router


# Backward compatibility
def recognize_intent(text: str, language: str = "auto") -> Dict[str, Any]:
    """Recognize intent (backward compatibility)."""
    return get_intent_router().recognize_intent(text, language)


def get_available_intents(language: str = "en") -> List[str]:
    """Get available intents (backward compatibility)."""
    return get_intent_router().get_available_intents()
