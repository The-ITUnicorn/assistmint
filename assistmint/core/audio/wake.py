"""
Wake Word Detection - OpenWakeWord integration.

Low-power wake word listening using OpenWakeWord models.
"""

import time
import numpy as np
import sounddevice as sd
from scipy import signal
from typing import Optional, Dict, List

from assistmint.core.logger import wake as log_wake

# Import config values
try:
    from config import WAKE_WORD, WAKE_THRESHOLD, AUDIO_SAMPLE_RATE
except ImportError:
    WAKE_WORD = "hey_jarvis"
    WAKE_THRESHOLD = 0.5
    AUDIO_SAMPLE_RATE = 16000


# Global wake word model
_oww_model = None


class WakeWordEngine:
    """
    Wake word detection using OpenWakeWord.

    Features:
    - Low CPU usage while waiting
    - Configurable wake words
    - Adjustable sensitivity
    """

    def __init__(self):
        self._model = None
        self._wake_word = WAKE_WORD
        self._threshold = WAKE_THRESHOLD

    def init_model(self):
        """Initialize OpenWakeWord model."""
        global _oww_model

        if _oww_model is not None:
            self._model = _oww_model
            return self._model

        log_wake("Loading wake word model...")
        from openwakeword.model import Model
        _oww_model = Model()
        self._model = _oww_model
        log_wake(f"Ready! Say '{self._wake_word.replace('_', ' ').title()}' to activate.")
        return self._model

    def set_wake_word(self, wake_word: str):
        """Set the wake word to listen for."""
        self._wake_word = wake_word

    def set_threshold(self, threshold: float):
        """Set detection threshold (0.0-1.0)."""
        self._threshold = max(0.0, min(1.0, threshold))

    def listen(
        self,
        selected_device: Dict,
        samplerate: int,
        timeout: float = None,
        warmup_delay: float = 1.0
    ) -> Optional[bool]:
        """
        Listen for wake word.

        Args:
            selected_device: Microphone device dict
            samplerate: Audio sample rate
            timeout: Max time to wait (None = forever)
            warmup_delay: Seconds to ignore after starting (avoids false triggers)

        Returns:
            True if wake word detected, False on timeout, None on error
        """
        model = self.init_model()

        # Reset model state to clear any buffered predictions
        if hasattr(model, 'reset'):
            model.reset()
            log_wake("[DEBUG] Model state reset")

        # Extra pause to let TTS audio fully stop and mic settle
        log_wake(f"[DEBUG] Waiting 1.0s for audio to settle...")
        time.sleep(1.0)

        # OpenWakeWord expects 16kHz
        target_rate = AUDIO_SAMPLE_RATE
        native_rate = int(samplerate)
        need_resample = native_rate != target_rate

        # Calculate chunk size for ~80ms of audio at native rate
        native_chunk = int(native_rate * 0.08)

        detected = False
        consecutive_detections = 0
        REQUIRED_DETECTIONS = 3  # Require 3 consecutive detections to trigger

        # Set start_time AFTER the sleep so warmup counts from stream start
        start_time = time.time()

        def audio_callback(indata, frames, time_info, status):
            nonlocal detected, consecutive_detections
            if detected:
                return
            if status:
                print(status)

            # Warmup delay - ignore audio for first X seconds to avoid false triggers
            elapsed = time.time() - start_time
            if elapsed < warmup_delay:
                # Still in warmup period, ignore this audio chunk
                return

            # Convert to float and get mono
            audio = indata[:, 0]

            # Resample to 16kHz if needed
            if need_resample:
                num_samples = int(len(audio) * target_rate / native_rate)
                audio = signal.resample(audio, num_samples)

            # Convert to 16-bit int for model
            audio_data = (audio * 32767).astype(np.int16)

            # Feed to wake word model
            prediction = model.predict(audio_data)

            # Debug: show score if significant
            if self._wake_word in prediction:
                score = prediction[self._wake_word]
                if score > 0.1:  # Only log if somewhat active
                    log_wake(f"[DEBUG] {self._wake_word}: {score:.3f} (threshold: {self._threshold}) [{consecutive_detections}/{REQUIRED_DETECTIONS}]")

            # Only trigger on the configured wake word - require multiple consecutive detections
            if self._wake_word in prediction and prediction[self._wake_word] > self._threshold:
                consecutive_detections += 1
                if consecutive_detections >= REQUIRED_DETECTIONS:
                    print(f"\n{log_wake(f'Detected: {self._wake_word} ({prediction[self._wake_word]:.2f}) after {consecutive_detections} confirmations')}")
                    detected = True
            else:
                # Reset counter if detection drops
                consecutive_detections = 0

        log_wake(f"Listening... (say '{self._wake_word.replace('_', ' ').title()}')")

        try:
            with sd.InputStream(
                samplerate=native_rate,
                blocksize=native_chunk,
                device=selected_device['index'],
                channels=1,
                dtype='float32',
                callback=audio_callback
            ):
                while not detected:
                    time.sleep(0.1)
                    if timeout and (time.time() - start_time) > timeout:
                        return False

            return True

        except Exception as e:
            print(f"Wake word error: {e}")
            return None

    @staticmethod
    def list_available_wakewords() -> List[str]:
        """List available pre-trained wake words."""
        return [
            "hey_jarvis",
            "alexa",
            "hey_mycroft",
            "timer",
            "weather"
        ]


# Global wake word engine instance
_wake_engine: Optional[WakeWordEngine] = None


def get_wake_engine() -> WakeWordEngine:
    """Get the global wake word engine instance."""
    global _wake_engine
    if _wake_engine is None:
        _wake_engine = WakeWordEngine()
    return _wake_engine


# Backward compatibility functions
def init_wake_word():
    """Initialize wake word model (backward compatibility)."""
    return get_wake_engine().init_model()


def listen_for_wake_word(
    selected_device: Dict,
    samplerate: int,
    timeout: float = None,
    warmup_delay: float = 1.0
) -> Optional[bool]:
    """Listen for wake word (backward compatibility)."""
    return get_wake_engine().listen(selected_device, samplerate, timeout, warmup_delay)


def list_available_wakewords() -> List[str]:
    """List available wake words (backward compatibility)."""
    return WakeWordEngine.list_available_wakewords()
