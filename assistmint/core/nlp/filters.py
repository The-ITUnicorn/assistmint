"""
Hallucination Filters - Filter out Whisper hallucinations and noise.
"""

import re
from typing import List

from assistmint.core.constants import WHISPER_HALLUCINATIONS, MAIN_HALLUCINATIONS


def is_hallucination(text: str, strict: bool = False) -> bool:
    """
    Check if text is likely a Whisper hallucination.

    Args:
        text: Text to check
        strict: If True, use stricter filtering (includes yes/no)

    Returns:
        True if text appears to be a hallucination
    """
    t_lower = text.lower().strip().rstrip('.,!?')

    # Choose hallucination list based on strictness
    hallucinations = MAIN_HALLUCINATIONS if strict else WHISPER_HALLUCINATIONS

    # Check known hallucinations
    if t_lower in hallucinations:
        return True

    # Check for repeated single word (e.g., "You You You")
    words = t_lower.split()
    if len(words) >= 2 and len(set(words)) == 1:
        return True

    # Check for repeated phrases (e.g., "I'm sorry. I'm sorry. I'm sorry.")
    phrases = [p.strip() for p in re.split(r'[.!?]+', t_lower) if p.strip()]
    if len(phrases) >= 2 and len(set(phrases)) == 1:
        return True

    # Check for very short meaningless output
    if len(t_lower) <= 2 and t_lower not in ["ok", "hi", "no", "ja"]:
        return True

    return False


def filter_non_latin(text: str) -> str:
    """
    Remove non-Latin script from text.

    Whisper sometimes hallucinates in other languages.
    """
    # Remove leading non-ASCII characters
    text = re.sub(r'^[^\x00-\x7F]+\s*', '', text)
    # Remove non-Latin script blocks
    text = re.sub(r'[\u0900-\u097F]+', '', text)  # Devanagari (Hindi)
    text = re.sub(r'[\u4E00-\u9FFF]+', '', text)  # Chinese
    text = re.sub(r'[\u0600-\u06FF]+', '', text)  # Arabic
    text = re.sub(r'[\u0400-\u04FF]+', '', text)  # Cyrillic
    text = re.sub(r'[\u3040-\u30FF]+', '', text)  # Japanese
    text = re.sub(r'[\uAC00-\uD7AF]+', '', text)  # Korean
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_transcription(text: str, strict: bool = False) -> str:
    """
    Clean transcription text.

    Args:
        text: Raw transcription
        strict: If True, use stricter filtering

    Returns:
        Cleaned text, or empty string if hallucination
    """
    if not text:
        return ""

    # Filter non-Latin first
    text = filter_non_latin(text)

    # Check for hallucination
    if is_hallucination(text, strict):
        return ""

    return text.strip()
