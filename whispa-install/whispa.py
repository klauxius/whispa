from openai import OpenAI
import sounddevice as sd
import numpy as np
import threading
import time
import os
import dotenv
import scipy.io.wavfile as wavfile
import queue
import tkinter as tk
from tkinter import ttk
from pynput import keyboard
import json

dotenv.load_dotenv(os.path.expanduser('~/.config/whispa/.env'))

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Define supported languages
LANGUAGES = {
    "Auto-detect": "",  # Empty string means auto-detect
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Russian": "ru",
    "Japanese": "ja",
    "Chinese": "zh",
    "Hindi": "hi",
    "Arabic": "ar"
}

class WhispaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Whispa")
        
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.samplerate = 44100
        self.input_device = None
        
        # Settings file path
        self.settings_file = os.path.expanduser('~/.config/whispa/settings.json')
        self.load_settings()
        
        # Create GUI elements
        self.create_gui()
        
        # Setup keyboard listener with custom global hotkey handling
        try:
            # Global flag to track if insert key is pressed
            self.insert_pressed = False
            
            # Use regular Listener but check for insert key specifically
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release)
            self.keyboard_listener.daemon = True
            self.keyboard_listener.start()
            print("Keyboard listener started successfully")
        except Exception as e:
            print(f"Failed to start keyboard listener: {e}")
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Bind additional keyboard shortcuts to the window
        self.root.bind('<Insert>', lambda e: self.toggle_recording())
        self.root.bind('<Escape>', lambda e: self.root.quit())

    def create_gui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.pack(pady=10)
        
        # Record button
        self.record_button = ttk.Button(main_frame, text="Start Recording", command=self.toggle_recording)
        self.record_button.pack(pady=10)
        
        # Device selection
        device_frame = ttk.LabelFrame(main_frame, text="Audio Device")
        device_frame.pack(pady=5, fill="x")
        
        # Get available devices
        devices = sd.query_devices()
        self.device_names = [f"{i}: {dev['name']}" for i, dev in enumerate(devices)]
        
        # Default to previously selected device or pulse
        default_device = self.settings.get('device', 9)
        try:
            default_device_str = next(d for d in self.device_names if d.startswith(f"{default_device}:"))
        except (StopIteration, IndexError):
            default_device_str = self.device_names[9] if len(self.device_names) > 9 else self.device_names[0]
        
        self.device_var = tk.StringVar(value=default_device_str)
        self.device_menu = ttk.Combobox(device_frame, textvariable=self.device_var, values=self.device_names)
        self.device_menu.pack(pady=5, padx=5, fill="x")
        
        # Language selection
        lang_frame = ttk.LabelFrame(main_frame, text="Language")
        lang_frame.pack(pady=5, fill="x")
        
        # Default to previously selected language or Auto-detect
        default_lang = self.settings.get('language_name', "Auto-detect")
        self.language_var = tk.StringVar(value=default_lang)
        self.language_menu = ttk.Combobox(lang_frame, textvariable=self.language_var, values=list(LANGUAGES.keys()))
        self.language_menu.pack(pady=5, padx=5, fill="x")
        
        # Audio level
        self.level_label = ttk.Label(main_frame, text="Audio Level: 0.0")
        self.level_label.pack(pady=5)
        
        # Shortcut info
        self.shortcut_label = ttk.Label(main_frame, text="Shortcut: Insert key to start/stop recording")
        self.shortcut_label.pack(pady=5)
        
    def load_settings(self):
        """Load user settings"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    self.settings = json.load(f)
            else:
                self.settings = {
                    'device': 9,  # Default to pulse
                    'language_name': "Auto-detect",
                    'language_code': ""
                }
        except Exception as e:
            print(f"Error loading settings: {str(e)}")
            self.settings = {
                'device': 9,
                'language_name': "Auto-detect",
                'language_code': ""
            }
    
    def save_settings(self):
        """Save user settings"""
        try:
            # Extract device ID from the selection
            device_str = self.device_var.get()
            device_id = int(device_str.split(':')[0])
            
            # Get language selection
            language_name = self.language_var.get()
            language_code = LANGUAGES.get(language_name, "")
            
            self.settings = {
                'device': device_id,
                'language_name': language_name,
                'language_code': language_code
            }
            
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f)
        except Exception as e:
            print(f"Error saving settings: {str(e)}")

    def on_key_press(self, key):
        try:
            # Check if the key is Insert
            if key == keyboard.Key.insert and not self.insert_pressed:
                print("Insert key detected (global)!")
                self.insert_pressed = True
                self.root.after(0, self.toggle_recording)
        except Exception as e:
            print(f"Error in key press handler: {e}")

    def on_key_release(self, key):
        try:
            # Reset insert pressed state when released
            if key == keyboard.Key.insert:
                self.insert_pressed = False
            elif key == keyboard.Key.esc:
                # Don't close the app when Esc is pressed globally
                pass
        except Exception as e:
            print(f"Error in key release handler: {e}")

    def on_closing(self):
        """Handle window closing"""
        self.save_settings()
        if hasattr(self, 'keyboard_listener'):
            self.keyboard_listener.stop()
        self.root.quit()

    def toggle_recording(self):
        if not self.is_recording:
            # Get selected device number
            device_str = self.device_var.get()
            device_num = int(device_str.split(':')[0])
            self.input_device = device_num
            
            # Save current settings
            self.save_settings()
            
            self.is_recording = True
            self.record_button.config(text="Stop Recording")
            self.status_label.config(text="Recording...")
            threading.Thread(target=self.record_audio, daemon=True).start()
        else:
            self.is_recording = False
            self.record_button.config(text="Start Recording")
            self.status_label.config(text="Processing...")
            threading.Thread(target=self.process_queued_audio, daemon=True).start()

    def record_audio(self):
        try:
            with sd.InputStream(device=self.input_device,
                              samplerate=self.samplerate,
                              channels=1,
                              dtype='float32',
                              blocksize=1024,
                              callback=self.audio_callback):
                while self.is_recording:
                    time.sleep(0.1)
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}")
            self.is_recording = False
            self.record_button.config(text="Start Recording")

    def audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Status: {status}")
        if self.is_recording:
            self.audio_queue.put(indata.copy())
            level = np.max(np.abs(indata))
            self.root.after(0, self.update_level, level)

    def update_level(self, level):
        self.level_label.config(text=f"Audio Level: {level:.3f}")

    def process_queued_audio(self):
        chunks = []
        while not self.audio_queue.empty():
            chunks.append(self.audio_queue.get())
        
        if chunks:
            audio_data = np.concatenate(chunks)
            audio_data = audio_data * 5.0  # Increase gain
            
            if np.max(np.abs(audio_data)) < 0.01:
                self.status_label.config(text="Audio too quiet")
                return
                
            self.status_label.config(text="Transcribing...")
            text = self.transcribe_audio(audio_data)
            
            if text.strip():
                self.status_label.config(text="Typing text...")
                self.type_text(text)
            else:
                self.status_label.config(text="No text transcribed")
        
        self.status_label.config(text="Ready")

    def transcribe_audio(self, audio):
        temp_file = "temp_audio.wav"
        audio_int16 = (audio * 32767).astype(np.int16)
        
        try:
            wavfile.write(temp_file, self.samplerate, audio_int16)
            
            # Get selected language code
            language_name = self.language_var.get()
            language_code = LANGUAGES.get(language_name, "")
            
            # Build API parameters
            params = {
                "model": "whisper-1",
                "file": open(temp_file, "rb")
            }
            
            # Only add language if a specific one is selected
            if language_code:
                params["language"] = language_code
                
            transcript = client.audio.transcriptions.create(**params)
            return transcript.text
        except Exception as e:
            self.status_label.config(text=f"Transcription error: {str(e)}")
            return ""
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def type_text(self, text):
        from pynput.keyboard import Controller, Key
        keyboard = Controller()
        
        for char in text:
            keyboard.press(char)
            keyboard.release(char)
            time.sleep(0.05)

def main():
    root = tk.Tk()
    app = WhispaGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()