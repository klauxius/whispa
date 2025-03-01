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

dotenv.load_dotenv(os.path.expanduser('~/.config/whispa/.env'))

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

class WhispaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Whispa")
        
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.samplerate = 44100
        self.input_device = None
        
        # Create GUI elements
        self.status_label = ttk.Label(root, text="Ready")
        self.status_label.pack(pady=10)
        
        self.record_button = ttk.Button(root, text="Start Recording", command=self.toggle_recording)
        self.record_button.pack(pady=10)
        
        self.device_label = ttk.Label(root, text="Select Input Device:")
        self.device_label.pack(pady=5)
        
        # Get available devices
        devices = sd.query_devices()
        self.device_names = [f"{i}: {dev['name']}" for i, dev in enumerate(devices)]
        
        self.device_var = tk.StringVar(value=self.device_names[9])  # Default to pulse
        self.device_menu = ttk.Combobox(root, textvariable=self.device_var, values=self.device_names)
        self.device_menu.pack(pady=5)
        
        self.level_label = ttk.Label(root, text="Audio Level: 0.0")
        self.level_label.pack(pady=5)
        
        # Add shortcut information label
        self.shortcut_label = ttk.Label(root, text="Shortcut: Insert key to start/stop recording")
        self.shortcut_label.pack(pady=5)
        
        # Setup global keyboard listener
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        self.keyboard_listener.start()
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Bind escape key
        self.root.bind('<Escape>', lambda e: self.root.quit())

    def on_press(self, key):
        try:
            # Check if the key is Insert
            if key == keyboard.Key.insert:
                self.root.after(0, self.toggle_recording)
        except AttributeError:
            pass

    def on_closing(self):
        """Handle window closing"""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self.root.quit()

    def toggle_recording(self):
        if not self.is_recording:
            # Get selected device number
            device_num = int(self.device_var.get().split(':')[0])
            self.input_device = device_num
            
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
            
            with open(temp_file, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
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