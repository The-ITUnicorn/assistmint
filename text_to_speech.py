import os
from TTS.api import TTS

import re

# Initialize Coqui TTS engine globally
tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=True, gpu=False)


def clean_text(text):
    """Remove unsupported characters from the text."""
    # Remove emojis and any non-ASCII characters
    return re.sub(r'[^\x00-\x7F]+', '', text)

def speak(text, speed=1.5):
    """Function to speak the provided text with SoX tempo adjustment"""
    # Clean the text before converting it to speech
    text = clean_text(text)
    
    output_file = "response.wav"
    tts.tts_to_file(text=text, file_path=output_file)
    
    # Use SoX to adjust the tempo of the generated audio without affecting pitch
    adjusted_file = "response_adjusted.wav"
    os.system(f"sox {output_file} {adjusted_file} tempo {speed}")
    
    # Play the adjusted audio
    os.system(f"aplay {adjusted_file}")  # Play the generated audio on Linux (use the appropriate command for other OS)

