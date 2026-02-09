"""
Speech-to-Text (STT) - Whisper transcription with GPU/CPU support.

Uses faster-whisper for efficient transcription.
Integrates with ResourceManager for GPU coordination.
"""

import queue
import time
import re
import subprocess
import numpy as np
import sounddevice as sd
import noisereduce as nr

from typing import Optional, Dict, Any

# VRAM monitoring cache
_vram_cache = {"pct": 0, "last_check": 0.0}


def _get_vram_pct() -> int:
    """Get VRAM usage percentage (cached, updates every 2 seconds)."""
    global _vram_cache
    now = time.time()
    if now - _vram_cache["last_check"] < 2.0:
        return _vram_cache["pct"]
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=1
        )
        if result.returncode == 0:
            used, total = map(int, result.stdout.strip().split(','))
            _vram_cache["pct"] = int(used * 100 / total)
            _vram_cache["last_check"] = now
    except Exception:
        pass
    return _vram_cache["pct"]

from assistmint.core.logger import stt as log_stt
from assistmint.core.resources.manager import get_resource_manager, ResourceType

# Import config values
try:
    from config import (
        SILENCE_SKIP_DB, SPEECH_START_DB, SILENCE_DROP_DB, SILENCE_DURATION,
        SILENCE_DURATION_EXT, WHISPER_MODEL, WHISPER_BEAM_SIZE,
        WHISPER_SAMPLE_RATE, STT_BLOCKSIZE, USE_GPU, GPU_DEVICE_ID,
        WHISPER_COMPUTE_TYPE, NOISE_REDUCE
    )
    # Per-language models (optional)
    try:
        from config import WHISPER_MODEL_EN, WHISPER_MODEL_NL
    except ImportError:
        WHISPER_MODEL_EN = None
        WHISPER_MODEL_NL = None
    # New config values (with defaults for backwards compatibility)
    try:
        from config import (
            STT_QUEUE_TIMEOUT, NOISE_REDUCE_STRENGTH,
            WHISPER_NO_SPEECH_THRESHOLD, WHISPER_LOG_PROB_THRESHOLD,
            WHISPER_HALLUCINATION_SILENCE
        )
    except ImportError:
        STT_QUEUE_TIMEOUT = 0.3
        NOISE_REDUCE_STRENGTH = 0.8
        WHISPER_NO_SPEECH_THRESHOLD = 0.6
        WHISPER_LOG_PROB_THRESHOLD = -1.0
        WHISPER_HALLUCINATION_SILENCE = 0.5
except ImportError:
    # Defaults if config not available
    SILENCE_SKIP_DB = -45
    SPEECH_START_DB = -40
    SILENCE_DROP_DB = 19
    SILENCE_DURATION = 1.2
    SILENCE_DURATION_EXT = 2.0
    WHISPER_MODEL = "small"
    WHISPER_MODEL_EN = None
    WHISPER_MODEL_NL = None
    WHISPER_BEAM_SIZE = 4
    WHISPER_SAMPLE_RATE = 16000
    STT_BLOCKSIZE = 4096
    USE_GPU = True
    GPU_DEVICE_ID = 0
    WHISPER_COMPUTE_TYPE = "float16"
    NOISE_REDUCE = True
    STT_QUEUE_TIMEOUT = 0.3
    NOISE_REDUCE_STRENGTH = 0.8
    WHISPER_NO_SPEECH_THRESHOLD = 0.6
    WHISPER_LOG_PROB_THRESHOLD = -1.0
    WHISPER_HALLUCINATION_SILENCE = 0.5


# Lazy load - deferred to avoid startup delay
_whisper_model = None
_whisper_model_name = None  # Track which model is loaded
_WhisperModel = None


class STTEngine:
    """
    Speech-to-Text engine using Whisper.

    Features:
    - GPU/CPU fallback via ResourceManager
    - Noise reduction
    - Hallucination filtering
    - Extended listening mode for longer questions
    """

    def __init__(self):
        self._model = None
        self._resource_manager = get_resource_manager()

    def _init_model(self, model_size: str = None, for_language: str = None) -> Any:
        """
        Initialize Whisper model lazily.

        Args:
            model_size: Model name or path (overrides config)
            for_language: Language hint ('en', 'nl') to select per-language model

        Returns:
            Loaded WhisperModel instance
        """
        global _whisper_model, _whisper_model_name, _WhisperModel

        # Determine which model to use
        if model_size is None:
            # Check for per-language models
            if for_language == "en" and WHISPER_MODEL_EN:
                model_size = WHISPER_MODEL_EN
            elif for_language == "nl" and WHISPER_MODEL_NL:
                model_size = WHISPER_MODEL_NL
            else:
                model_size = WHISPER_MODEL

        # Check if we need to switch models
        if _whisper_model is not None and _whisper_model_name == model_size:
            return _whisper_model

        # If different model requested, unload current one first
        if _whisper_model is not None and _whisper_model_name != model_size:
            log_stt(f"Switching model from '{_whisper_model_name}' to '{model_size}'...")
            self.unload_model()

        # Lazy import
        if _WhisperModel is None:
            log_stt("Loading faster-whisper library...")
            from faster_whisper import WhisperModel
            _WhisperModel = WhisperModel

        # Request GPU from resource manager
        use_gpu = self._resource_manager.request_gpu(ResourceType.STT, "whisper")

        device = "cuda" if use_gpu else "cpu"
        device_index = self._resource_manager.gpu_device_id if use_gpu else 0
        compute_type = "float16" if use_gpu else "int8"

        log_stt(f"Loading Whisper model '{model_size}' on {device} (GPU {device_index})...")
        _whisper_model = _WhisperModel(
            model_size,
            device=device,
            device_index=device_index,
            compute_type=compute_type
        )
        _whisper_model_name = model_size
        log_stt("Whisper ready!")

        return _whisper_model

    def unload_model(self):
        """
        Unload Whisper model from GPU to free VRAM.

        Call this when STT is not needed for a while.
        Model will be reloaded automatically on next transcribe().
        """
        global _whisper_model, _whisper_model_name

        if _whisper_model is None:
            return

        log_stt("Unloading Whisper model to free VRAM...")

        # Release GPU allocation
        self._resource_manager.release_gpu(ResourceType.STT)

        # Delete model reference
        del _whisper_model
        _whisper_model = None
        _whisper_model_name = None

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

        log_stt("Whisper model unloaded - VRAM freed")

    def is_loaded(self) -> bool:
        """Check if Whisper model is currently loaded."""
        return _whisper_model is not None

    def transcribe(
        self,
        selected_device: Dict,
        samplerate: int,
        extended_listen: bool = False
    ) -> str:
        """
        Record audio and transcribe with Whisper.

        Args:
            selected_device: Microphone device dict
            samplerate: Audio sample rate
            extended_listen: If True, waits longer for silence before stopping

        Returns:
            Transcribed text
        """
        # Get language hint from TTS setting (if user forced a language)
        forced_lang = None
        try:
            from core.audio.tts import get_language
            forced_lang = get_language()
        except ImportError:
            pass

        # Load model (may switch to language-specific model if configured)
        model = self._init_model(for_language=forced_lang)

        # Update last-used timestamp to prevent auto-unload
        self._resource_manager.touch(ResourceType.STT)

        q = queue.Queue()
        audio_buffer = []

        def callback(indata, frames, time_info, status):
            if status:
                print(status)
            q.put(indata.copy())

        try:
            with sd.InputStream(
                samplerate=int(samplerate),
                blocksize=STT_BLOCKSIZE,
                device=selected_device['index'],
                dtype='float32',
                channels=1,
                callback=callback
            ):
                if extended_listen:
                    print("# Speak your question... (pause to finish)")
                else:
                    print("# Say something!")

                peak_db = -60.0
                drop_start = None
                speech_started = False
                silence_threshold = SILENCE_DURATION_EXT if extended_listen else SILENCE_DURATION

                while True:
                    try:
                        data = q.get(timeout=STT_QUEUE_TIMEOUT)
                    except queue.Empty:
                        continue

                    audio_buffer.append(data)

                    # Calculate dB
                    rms = np.sqrt(np.mean(data ** 2)) if len(data) > 0 else 0
                    current_db = 20 * np.log10(rms) if rms > 1e-10 else -60.0

                    # Track peak (ignore clipped)
                    if current_db > peak_db and current_db < -5:
                        peak_db = current_db
                        drop_start = None
                        if current_db > SPEECH_START_DB:
                            speech_started = True

                    # Show dB meter with VRAM
                    bar_len = int((current_db + 60) / 60 * 20)
                    bar = '█' * max(0, min(20, bar_len)) + '░' * (20 - max(0, min(20, bar_len)))
                    vram = _get_vram_pct()
                    vram_warn = "⚠" if vram > 85 else " "
                    print(f"\r[{bar}] {current_db:5.1f}dB |{vram_warn}VRAM:{vram:2d}% ", end='', flush=True)

                    # Check for silence after speech
                    if speech_started and current_db < (peak_db - SILENCE_DROP_DB):
                        if drop_start is None:
                            drop_start = time.time()
                        elif (time.time() - drop_start) > silence_threshold:
                            print()  # Newline after meter
                            break
                    else:
                        drop_start = None

            # Convert buffer to numpy array
            if not audio_buffer:
                return ""

            audio_data = np.concatenate(audio_buffer, axis=0).flatten()

            # Check if there was actual audio (not just silence)
            rms = np.sqrt(np.mean(audio_data ** 2))
            avg_db = 20 * np.log10(rms) if rms > 1e-10 else -60.0
            if avg_db < SILENCE_SKIP_DB:
                log_stt(f"Skipping - too quiet ({avg_db:.1f}dB)")
                return ""

            # Resample to 16kHz if needed
            if int(samplerate) != WHISPER_SAMPLE_RATE:
                from scipy import signal
                num_samples = int(len(audio_data) * WHISPER_SAMPLE_RATE / samplerate)
                audio_16k = signal.resample(audio_data, num_samples).astype(np.float32)
            else:
                audio_16k = audio_data.astype(np.float32)

            # Apply noise reduction if enabled
            if NOISE_REDUCE:
                log_stt("Reducing noise...")
                audio_16k = nr.reduce_noise(y=audio_16k, sr=WHISPER_SAMPLE_RATE, prop_decrease=NOISE_REDUCE_STRENGTH)

            # Use the language hint from earlier (forced_lang already set at start of method)
            whisper_lang = forced_lang  # None = auto-detect, "nl" = Dutch, "en" = English

            log_stt(f"Transcribing... (lang={whisper_lang or 'auto'})")
            segments, info = model.transcribe(
                audio_16k,
                beam_size=WHISPER_BEAM_SIZE,
                language=whisper_lang,  # None = auto-detect, "nl" = Dutch, "en" = English
                # Anti-hallucination settings (from config.py)
                no_speech_threshold=WHISPER_NO_SPEECH_THRESHOLD,
                log_prob_threshold=WHISPER_LOG_PROB_THRESHOLD,
                hallucination_silence_threshold=WHISPER_HALLUCINATION_SILENCE,
                condition_on_previous_text=False,
            )
            text = " ".join([seg.text for seg in segments]).strip()

            # Filter non-Latin hallucinations
            text = self._filter_hallucinations(text)

            log_stt(f"Result: {text}")
            return text

        except Exception as e:
            print(f"\nAn error occurred during audio processing: {e}")
            # Try to free GPU memory on OOM errors
            if "out of memory" in str(e).lower():
                self._handle_oom()
        return ""

    def _filter_hallucinations(self, text: str) -> str:
        """Filter non-Latin script hallucinations from Whisper output."""
        # Remove leading non-ASCII characters and clean up
        text = re.sub(r'^[^\x00-\x7F]+\s*', '', text)
        # Remove any remaining non-Latin script blocks
        text = re.sub(r'[\u0900-\u097F]+', '', text)  # Devanagari (Hindi)
        text = re.sub(r'[\u4E00-\u9FFF]+', '', text)  # Chinese
        text = re.sub(r'[\u0600-\u06FF]+', '', text)  # Arabic
        text = re.sub(r'[\u0400-\u04FF]+', '', text)  # Cyrillic
        text = re.sub(r'[\u3040-\u30FF]+', '', text)  # Japanese
        text = re.sub(r'[\uAC00-\uD7AF]+', '', text)  # Korean
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _handle_oom(self):
        """Handle out-of-memory error."""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                log_stt("Cleared GPU cache after OOM")
        except:
            pass

    def release(self):
        """Release GPU resources."""
        self._resource_manager.release_gpu(ResourceType.STT)


# Global STT engine instance
_stt_engine: Optional[STTEngine] = None


def get_stt_engine() -> STTEngine:
    """Get the global STT engine instance."""
    global _stt_engine
    if _stt_engine is None:
        _stt_engine = STTEngine()
    return _stt_engine


# Backward compatibility functions
def init_whisper(model_size: str = None):
    """Initialize Whisper model (backward compatibility)."""
    return get_stt_engine()._init_model(model_size)


def whisper_speech_to_text(selected_device: Dict, samplerate: int, extended_listen: bool = False) -> str:
    """Transcribe speech to text (backward compatibility)."""
    return get_stt_engine().transcribe(selected_device, samplerate, extended_listen)


def get_device():
    """Get device info (backward compatibility)."""
    rm = get_resource_manager()
    if rm.gpu_available:
        return "cuda", rm.gpu_device_id, "float16"
    return "cpu", 0, "int8"
