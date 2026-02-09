"""
Audio Device Management - Microphone selection and configuration.
"""

import sounddevice as sd
from typing import List, Dict, Tuple, Optional

from assistmint.core.logger import stt


def list_microphones() -> List[Dict]:
    """List all available input devices (microphones)."""
    devices = sd.query_devices()
    input_devices = []
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            dev = dict(device)
            dev['index'] = i
            input_devices.append(dev)
    for i, device in enumerate(input_devices):
        print(f"{i}: {device['name']} (device {device['index']})")
    return input_devices


def get_default_microphone(input_devices: List[Dict]) -> Tuple[Dict, int]:
    """Get first available microphone without prompting."""
    selected_device = input_devices[0]
    samplerate = int(selected_device['default_samplerate'])
    print(f"Using microphone: {selected_device['name']} ({samplerate} Hz)")
    return selected_device, samplerate


def select_microphone_and_samplerate(input_devices: List[Dict]) -> Tuple[Dict, int]:
    """Prompt user to select a microphone."""
    choice = int(input("Select the microphone by entering the corresponding number: "))
    selected_device = input_devices[choice]
    samplerate = int(selected_device['default_samplerate'])
    print(f"Selected microphone: {selected_device['name']}")
    print(f"Sample rate: {samplerate} Hz")
    return selected_device, samplerate


def get_microphone_by_index(input_devices: List[Dict], index: int) -> Tuple[Dict, int]:
    """Get microphone by index without prompting."""
    selected_device = input_devices[index]
    samplerate = int(selected_device['default_samplerate'])
    print(f"Using device {index}: {selected_device['name']} ({samplerate} Hz)")
    return selected_device, samplerate
