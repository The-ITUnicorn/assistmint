"""
Core Audio - Speech I/O for Assistmint.

Provides:
- STT (Speech-to-Text) via Whisper
- TTS (Text-to-Speech) via Piper
- Wake word detection via OpenWakeWord
- Audio device management
"""

from assistmint.core.audio.device import (
    list_microphones,
    get_default_microphone,
    select_microphone_and_samplerate,
    get_microphone_by_index
)
from assistmint.core.audio.stt import (
    STTEngine,
    get_stt_engine,
    whisper_speech_to_text,
    init_whisper,
    get_device
)
from assistmint.core.audio.tts import (
    TTSEngine,
    get_tts_engine,
    speak,
    set_language,
    get_language,
    detect_language,
    clean_text
)
from assistmint.core.audio.wake import (
    WakeWordEngine,
    get_wake_engine,
    init_wake_word,
    listen_for_wake_word,
    list_available_wakewords
)

__all__ = [
    # Device
    "list_microphones",
    "get_default_microphone",
    "select_microphone_and_samplerate",
    "get_microphone_by_index",
    # STT
    "STTEngine",
    "get_stt_engine",
    "whisper_speech_to_text",
    "init_whisper",
    "get_device",
    # TTS
    "TTSEngine",
    "get_tts_engine",
    "speak",
    "set_language",
    "get_language",
    "detect_language",
    "clean_text",
    # Wake
    "WakeWordEngine",
    "get_wake_engine",
    "init_wake_word",
    "listen_for_wake_word",
    "list_available_wakewords",
]
