"""
Text-to-Speech (TTS) - Piper synthesis with GPU/CPU support.

Features:
- Bilingual support (EN/NL)
- Interruptable playback
- Auto language detection
"""

import os
import time
import re
import numpy as np
import sounddevice as sd

from typing import Optional

from assistmint.core.logger import tts as log_tts
from assistmint.core.resources.manager import get_resource_manager, ResourceType

# ONNX Runtime optimizations for Tensor Cores (RTX 3070)
os.environ.setdefault('ORT_TENSORRT_FP16_ENABLE', '1')
os.environ.setdefault('ORT_TENSORRT_ENGINE_CACHE_ENABLE', '1')
os.environ.setdefault('ORT_TENSORRT_ENGINE_CACHE_PATH', os.path.expanduser('~/.cache/onnx_tensorrt'))

# Import config values
try:
    from config import (
        INTERRUPT_DB, INTERRUPT_DURATION,
        TTS_SPEED_EN, TTS_PITCH_EN, TTS_VOLUME_EN,
        TTS_SPEED_NL, TTS_PITCH_NL, TTS_VOLUME_NL,
        TTS_GRACE_PERIOD, TTS_LANG_THRESHOLD, TTS_LOG_LENGTH,
        AUDIO_SAMPLE_RATE, AUDIO_BLOCKSIZE, USE_GPU, GPU_DEVICE_ID,
        FORCE_LANGUAGE
    )
except ImportError:
    # Defaults if config not available
    INTERRUPT_DB = -28
    INTERRUPT_DURATION = 0.3
    TTS_SPEED_EN = 0.90
    TTS_PITCH_EN = 0.950
    TTS_VOLUME_EN = 1.0
    TTS_SPEED_NL = 0.8
    TTS_PITCH_NL = 1.3
    TTS_VOLUME_NL = 0.90
    TTS_GRACE_PERIOD = 0.3
    TTS_LANG_THRESHOLD = 0.15
    TTS_LOG_LENGTH = 0
    AUDIO_SAMPLE_RATE = 16000
    AUDIO_BLOCKSIZE = 1600
    USE_GPU = True
    GPU_DEVICE_ID = 0
    FORCE_LANGUAGE = None


# Piper TTS - lazy load for fast startup
_piper_voice_nl = None
_piper_voice_en = None
VOICE_DIR = os.path.expanduser("~/.local/share/piper/voices")

# Runtime language override (None = auto, "en" = English, "nl" = Dutch)
_forced_language = FORCE_LANGUAGE


class TTSEngine:
    """
    Text-to-Speech engine using Piper.

    Features:
    - GPU/CPU fallback via ResourceManager
    - Bilingual support (EN/NL)
    - Auto language detection
    - Interruptable playback
    """

    def __init__(self):
        self._voice_nl = None
        self._voice_en = None
        self._forced_language = FORCE_LANGUAGE
        self._resource_manager = get_resource_manager()

    def set_language(self, lang: Optional[str]):
        """Set forced language: 'en', 'nl', or None for auto-detect."""
        self._forced_language = lang
        global _forced_language
        _forced_language = lang
        if lang is None:
            log_tts("Language: auto-detect")
        else:
            log_tts(f"Language: forced to {lang}")

    def get_language(self) -> Optional[str]:
        """Get current forced language setting."""
        return self._forced_language

    def _check_cuda_available(self) -> bool:
        """Check if CUDA is available for Piper."""
        if not USE_GPU:
            return False
        try:
            import torch
            if torch.cuda.is_available():
                gpu_id = self._resource_manager.gpu_device_id
                torch.cuda.set_device(gpu_id)

                # Enable TensorRT if available
                try:
                    import onnxruntime as ort
                    providers = ort.get_available_providers()
                    if 'TensorrtExecutionProvider' in providers:
                        log_tts("TensorRT available - Tensor Cores enabled")
                    elif 'CUDAExecutionProvider' in providers:
                        log_tts("CUDA available - using GPU")
                except ImportError:
                    pass

                return True
            return False
        except ImportError:
            return False

    def _get_voice(self, lang: str = "nl"):
        """Lazy load Piper voice (GPU if available, CPU fallback)."""
        global _piper_voice_nl, _piper_voice_en

        use_cuda = self._check_cuda_available()

        if lang == "nl":
            if _piper_voice_nl is None:
                from piper import PiperVoice
                model_path = os.path.join(VOICE_DIR, "nl_BE-nathalie-medium.onnx")
                device_str = "GPU" if use_cuda else "CPU"
                log_tts(f"Loading Dutch voice ({device_str})...")
                _piper_voice_nl = PiperVoice.load(model_path, use_cuda=use_cuda)
                log_tts("Dutch voice ready")
            return _piper_voice_nl
        else:
            if _piper_voice_en is None:
                from piper import PiperVoice
                model_path = os.path.join(VOICE_DIR, "en_US-lessac-medium.onnx")
                device_str = "GPU" if use_cuda else "CPU"
                log_tts(f"Loading English voice ({device_str})...")
                _piper_voice_en = PiperVoice.load(model_path, use_cuda=use_cuda)
                log_tts("English voice ready")
            return _piper_voice_en

    def unload_voices(self, lang: str = None):
        """
        Unload Piper voice models to free VRAM.

        Args:
            lang: 'nl', 'en', or None to unload all voices

        Call this when TTS is not needed for a while.
        Voices will be reloaded automatically on next speak().
        """
        global _piper_voice_nl, _piper_voice_en

        unloaded = []

        if lang is None or lang == "nl":
            if _piper_voice_nl is not None:
                del _piper_voice_nl
                _piper_voice_nl = None
                unloaded.append("Dutch")

        if lang is None or lang == "en":
            if _piper_voice_en is not None:
                del _piper_voice_en
                _piper_voice_en = None
                unloaded.append("English")

        if unloaded:
            # Release GPU allocation
            self._resource_manager.release_gpu(ResourceType.TTS)

            # Force garbage collection and clear CUDA cache
            import gc
            gc.collect()

            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
            except:
                pass

            log_tts(f"TTS voices unloaded: {', '.join(unloaded)} - VRAM freed")

    def is_loaded(self, lang: str = None) -> bool:
        """Check if TTS voice(s) are currently loaded."""
        if lang == "nl":
            return _piper_voice_nl is not None
        elif lang == "en":
            return _piper_voice_en is not None
        else:
            return _piper_voice_nl is not None or _piper_voice_en is not None

    def _warm_audio_pipeline(self, sample_rate: int = 22050):
        """
        Play brief silence to wake up audio pipeline (PipeWire/PulseAudio).

        Prevents first syllable from being cut off when audio system
        is idle (e.g., Bluetooth headphones in sleep mode).
        """
        try:
            # 50ms of silence at low volume to wake audio system
            duration = 0.05
            silent = np.zeros(int(duration * sample_rate), dtype=np.float32)
            sd.play(silent, sample_rate)
            sd.wait()
        except Exception:
            pass  # Don't fail if warm-up fails

    def detect_language(self, text: str) -> str:
        """Simple language detection based on common words."""
        nl_words = [
            "de", "het", "een", "van", "en", "in", "is", "dat", "op", "te",
            "voor", "met", "zijn", "niet", "aan", "dit", "ook", "als", "maar", "om",
            "je", "ik", "we", "hij", "zij", "u", "kan", "zou", "wel", "nog"
        ]

        words = text.lower().split()
        if len(words) < 3:
            # For short phrases, check if any word is distinctly Dutch
            for w in words:
                if w in nl_words and w not in ["de", "is", "in", "en", "van"]:
                    return "nl"
            return "en"  # Default to English for short phrases

        nl_count = sum(1 for w in words if w in nl_words)
        ratio = nl_count / len(words)

        return "nl" if ratio > TTS_LANG_THRESHOLD else "en"

    def clean_text(self, text: str) -> str:
        """Replace unsupported characters with speakable alternatives."""
        # Remove markdown formatting
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        text = re.sub(r'```[^`]*```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

        # Replace special characters
        replacements = {
            '#': ' hashtag ', '@': ' at ', '&': ' and ', '%': ' percent ',
            '$': ' dollar ', '*': '', '+': ' plus ', '=': ' equals ',
            '<': ' less than ', '>': ' greater than ', '/': ' slash ',
            '\\': ' backslash ', '|': ' pipe ', '~': ' tilde ', '^': ' caret ',
            '_': ' ', '{': '', '}': '', '[': '', ']': '', '`': '',
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)

        # Remove emojis and non-ASCII
        text = re.sub(r'[^\x00-\x7F]+', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def speak(
        self,
        text: str,
        speed: float = None,
        pitch: float = None,
        volume: float = None,
        interruptable: bool = True,
        lang: str = None
    ) -> bool:
        """
        Speak text using Piper TTS.

        Args:
            text: Text to speak
            speed: Speech rate override (None = use per-language config)
            pitch: Pitch override (None = use per-language config)
            volume: Volume multiplier override (None = use per-language config)
            interruptable: If True, monitor mic for interrupt
            lang: Force language ('nl' or 'en'), or None for auto-detect

        Returns:
            True if interrupted, False otherwise
        """
        text = self.clean_text(text)

        if not text or text.isspace():
            return False

        # Use forced language if set, otherwise auto-detect
        if lang is None:
            if self._forced_language is not None:
                lang = self._forced_language
                log_tts(f"[DEBUG] Using forced lang: {lang}")
            else:
                lang = self.detect_language(text)
                log_tts(f"[DEBUG] Auto-detected lang: {lang} for: {text[:30]}...")

        # Apply per-language settings
        if lang == "nl":
            speed = speed if speed is not None else TTS_SPEED_NL
            pitch = pitch if pitch is not None else TTS_PITCH_NL
            volume = volume if volume is not None else TTS_VOLUME_NL
        else:
            speed = speed if speed is not None else TTS_SPEED_EN
            pitch = pitch if pitch is not None else TTS_PITCH_EN
            volume = volume if volume is not None else TTS_VOLUME_EN

        if TTS_LOG_LENGTH > 0 and len(text) > TTS_LOG_LENGTH:
            log_tts(f"Speaking ({lang}): {text[:TTS_LOG_LENGTH]}...")
        else:
            log_tts(f"Speaking ({lang}): {text}")

        try:
            voice = self._get_voice(lang)

            # Update last-used timestamp to prevent auto-unload
            self._resource_manager.touch(ResourceType.TTS)

            # Synthesize
            chunks = list(voice.synthesize(text))
            if not chunks:
                return False

            # Combine all audio chunks
            audio_arrays = [chunk.audio_float_array for chunk in chunks]
            audio_float = np.concatenate(audio_arrays) if len(audio_arrays) > 1 else audio_arrays[0]
            sample_rate = chunks[0].sample_rate

            # Apply pitch adjustment
            if pitch != 1.0:
                from scipy import signal
                new_length = int(len(audio_float) / pitch)
                audio_float = signal.resample(audio_float, new_length)
                sample_rate = int(sample_rate / pitch)

            # Apply speed adjustment
            if speed != 1.0:
                from scipy import signal
                new_length = int(len(audio_float) / speed)
                audio_float = signal.resample(audio_float, new_length)

            # Apply volume adjustment
            if volume != 1.0:
                audio_float = audio_float * volume
                audio_float = np.clip(audio_float, -1.0, 1.0)

            # Warm up audio pipeline to prevent first syllable cutoff
            self._warm_audio_pipeline(sample_rate)

            if not interruptable:
                sd.play(audio_float, sample_rate)
                sd.wait()
                return False

            # Interruptable playback with mic monitoring
            sd.play(audio_float, sample_rate)

            start_time = time.time()
            loud_start = None

            try:
                with sd.InputStream(samplerate=AUDIO_SAMPLE_RATE, channels=1, dtype='float32', blocksize=AUDIO_BLOCKSIZE) as stream:
                    while sd.get_stream().active:
                        audio, _ = stream.read(AUDIO_BLOCKSIZE)

                        # Grace period
                        if time.time() - start_time < TTS_GRACE_PERIOD:
                            continue

                        rms = np.sqrt(np.mean(audio ** 2))
                        db = 20 * np.log10(rms) if rms > 1e-10 else -60.0

                        if db > INTERRUPT_DB:
                            if loud_start is None:
                                loud_start = time.time()
                            elif time.time() - loud_start > INTERRUPT_DURATION:
                                print(f"\n{log_tts(f'Break detected! (sustained {db:.1f}dB)')}")
                                sd.stop()
                                # Unload Ollama model to free VRAM
                                try:
                                    from ollama import unload_ollama_model
                                    unload_ollama_model()
                                except Exception:
                                    pass
                                time.sleep(0.2)
                                return True
                        else:
                            loud_start = None
            except Exception:
                sd.wait()

            return False

        except Exception as e:
            log_tts(f"TTS error: {e}")
            return False


# Global TTS engine instance
_tts_engine: Optional[TTSEngine] = None


def get_tts_engine() -> TTSEngine:
    """Get the global TTS engine instance."""
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TTSEngine()
    return _tts_engine


# Backward compatibility functions
def set_language(lang: Optional[str]):
    """Set forced language (backward compatibility)."""
    get_tts_engine().set_language(lang)


def get_language() -> Optional[str]:
    """Get forced language (backward compatibility)."""
    return get_tts_engine().get_language()


def detect_language(text: str) -> str:
    """Detect language (backward compatibility)."""
    return get_tts_engine().detect_language(text)


def clean_text(text: str) -> str:
    """Clean text (backward compatibility)."""
    return get_tts_engine().clean_text(text)


def speak(
    text: str,
    speed: float = None,
    pitch: float = None,
    volume: float = None,
    interruptable: bool = True,
    lang: str = None
) -> bool:
    """Speak text (backward compatibility)."""
    return get_tts_engine().speak(text, speed, pitch, volume, interruptable, lang)
