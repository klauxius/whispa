from openai import OpenAI
import sounddevice as sd
import numpy as np
from pynput import keyboard
import threading
import time
import os
import dotenv
import scipy.io.wavfile as wavfile

dotenv.load_dotenv(os.path.expanduser('~/.config/whispa/.env'))

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Global flags and variables
is_recording = False
audio_data = []
samplerate = 16000

def on_press(key):
    global is_recording
    try:
        # Check for Super (Meta) + F9 combination
        if key == keyboard.Key.f9 and keyboard.Controller().meta_pressed:
            if not is_recording:
                is_recording = True
                threading.Thread(target=record_audio).start()
    except AttributeError:
        pass

def on_release(key):
    global is_recording
    if key == keyboard.Key.f9:
        is_recording = False
    if key == keyboard.Key.esc:
        return False  # Stop the listener

def record_audio():
    global audio_data
    audio_data = []
    print("Recording... (Release F9 to stop)")
    
    # Configure input stream with higher gain
    with sd.InputStream(samplerate=samplerate, channels=1, dtype='float32', blocksize=1024) as stream:
        while is_recording:
            audio_chunk, overflowed = stream.read(1024)  # Smaller chunks for more frequent updates
            if not overflowed:
                # Apply gain and add to audio data
                audio_chunk = audio_chunk * 5.0  # Increase the gain
                audio_data.extend(audio_chunk[:, 0])
                if len(audio_chunk) > 0:
                    print(f"Current audio level: {np.max(np.abs(audio_chunk)):.3f}")
    
    print(f"Recording stopped. Total audio length: {len(audio_data)} samples")
    process_audio()

def process_audio():
    global audio_data
    if audio_data:
        print(f"Processing audio data of length: {len(audio_data)}")
        print(f"Audio data range: min={np.min(audio_data):.3f}, max={np.max(audio_data):.3f}")
        audio_array = np.array(audio_data)
        text = transcribe_audio(audio_array)
        print(f"Transcribed text: {text}")
        if text.strip():  # Only type if there's actual text
            type_text(text)
        else:
            print("Warning: Received empty transcription")
    else:
        print("Warning: No audio data to process")
    audio_data = []

def transcribe_audio(audio):
    print("Transcribing...")
    
    # Save the audio data as a temporary file
    temp_file = "temp_audio.wav"
    
    # Convert float32 array to int16
    audio_int16 = (audio * 32767).astype(np.int16)
    print(f"Converted audio stats - min: {np.min(audio_int16)}, max: {np.max(audio_int16)}")
    
    # Write the audio data to a WAV file
    wavfile.write(temp_file, samplerate, audio_int16)
    print(f"Saved audio file: {os.path.getsize(temp_file)} bytes")
    
    try:
        with open(temp_file, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        print("Transcription successful")
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        return ""
    
    # Remove the temporary file
    os.remove(temp_file)
    
    return transcript.text

def type_text(text):
    print(f"Typing: {text}")
    for char in text:
        keyboard.Controller().press(char)
        keyboard.Controller().release(char)
        time.sleep(0.05)  # Add a small delay between keystrokes

def main():
    # Print audio device information
    print("\nAudio Device Information:")
    print(f"Default input device: {sd.default.device[0]}")
    devices = sd.query_devices()
    print("\nAvailable audio devices:")
    for i, dev in enumerate(devices):
        print(f"{i}: {dev['name']} (inputs: {dev['max_input_channels']})")
    
    print("\nHold 'Super + F9' to record, release to stop and transcribe. Press 'Esc' to quit.")
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

if __name__ == "__main__":
    main()