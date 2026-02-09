"""
Core NLP - Natural Language Processing for Assistmint.

Provides:
- Intent routing
- Corrections/learning system
- Hallucination filters
"""

from assistmint.core.nlp.corrections import (
    CorrectionEngine,
    get_correction_engine,
    apply_corrections,
    add_correction,
    remove_correction,
    list_corrections,
    load_corrections,
    save_corrections
)
from assistmint.core.nlp.filters import (
    is_hallucination,
    filter_non_latin,
    clean_transcription
)
from assistmint.core.nlp.router import (
    IntentRouter,
    get_intent_router,
    recognize_intent,
    get_available_intents,
    INTENT_ACTIONS
)

__all__ = [
    # Corrections
    "CorrectionEngine",
    "get_correction_engine",
    "apply_corrections",
    "add_correction",
    "remove_correction",
    "list_corrections",
    "load_corrections",
    "save_corrections",
    # Filters
    "is_hallucination",
    "filter_non_latin",
    "clean_transcription",
    # Router
    "IntentRouter",
    "get_intent_router",
    "recognize_intent",
    "get_available_intents",
    "INTENT_ACTIONS",
]
