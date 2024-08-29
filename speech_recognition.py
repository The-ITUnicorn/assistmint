import sounddevice as sd
import vosk
import queue
import json
import os
import time

def list_microphones():
    devices = sd.query_devices()
    input_devices = [device for device in devices if device['max_input_channels'] > 0]
    for i, device in enumerate(input_devices):
        print(f"{i}: {device['name']}")
    return input_devices

def select_microphone_and_samplerate(input_devices):
    device_index = int(input("Select the microphone by entering the corresponding number: "))
    selected_device = input_devices[device_index]
    
    device_info = sd.query_devices(device_index)
    samplerates = device_info['default_samplerate']
    
    max_sample_rate = samplerates

    print(f"Selected microphone: {selected_device['name']}")
    print(f"Highest supported sample rate: {max_sample_rate} Hz")
    
    return selected_device, max_sample_rate

def vosk_speech_to_text(selected_device, samplerate, model_path = "vosk-model/vosk-model-small-en-us-0.15"):

    """Function to capture audio from the selected microphone and use Vosk to transcribe"""
    if not os.path.exists(model_path):
        print(f"Model not found at {model_path}. Please ensure the model is correctly placed.")
        return ""
    
    model = vosk.Model(model_path)
    q = queue.Queue()

    def callback(indata, frames, time, status):
        if status:
            print(status)
        q.put(bytes(indata))

    # Increased blocksize and latency for more stable performance
    try:
        with sd.RawInputStream(samplerate=int(samplerate), blocksize=8192, latency='high', device=selected_device['index'], dtype='int16', channels=1, callback=callback):
            print("# Say something!")
            rec = vosk.KaldiRecognizer(model, samplerate)
            while True:
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = rec.Result()
                    text = json.loads(result).get('text', '')
                    print(f"Detected: {text}")
                    return text
                else:
                    partial_result = rec.PartialResult()
                    print(f"Partial: {json.loads(partial_result).get('partial', '')}")
    except Exception as e:
        print(f"An error occurred during audio processing: {e}")
