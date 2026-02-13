import whisper
import sounddevice as sd
import numpy as np
import requests
import pyttsx3
import os
from scipy.io.wavfile import write
from whisper_listener import MediBotListener  # Utilise ta classe optimisée

# --- CONFIGURATION ---
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"
FS = 16000      # Fréquence Whisper
DURATION = 4    # Temps d'écoute (ajustable)
TEMP_FILE = "temp_voice.wav"

# --- INITIALISATION ---
print("Chargement des modules (Whisper & TTS)...")
listener = MediBotListener() # Charge le modèle 'tiny' via ton fichier whisper_listener.py
engine = pyttsx3.init()
engine.setProperty('voice', 'french') # Optionnel : tente de forcer une voix française

def speak(text):
    """Fait parler le bot localement (simulation Pepper)."""
    if text:
        engine.say(text)
        engine.runAndWait()

def send_to_rasa(message):
    """Envoie le texte à RASA et traite la réponse vocale."""
    payload = {"sender": "user_voice", "message": message}
    try:
        response = requests.post(RASA_URL, json=payload)
        res_json = response.json()
        
        for msg in res_json:
            bot_text = msg.get('text')
            print(f"MediBot : {bot_text}")
            speak(bot_text)
            
    except Exception as e:
        print(f"Erreur de connexion RASA : {e}")

def run_voice_loop():
    """Boucle principale : Écoute -> Transcription -> RASA -> Voix."""
    print("\n=== MediBot est prêt ! (CTRL+C pour arrêter) ===")
    while True:
        print("\n--- ÉCOUTE en cours... ---")
        # Capture audio
        recording = sd.rec(int(DURATION * FS), samplerate=FS, channels=1, dtype='float32')
        sd.wait()
        
        # Sauvegarde pour Whisper
        write(TEMP_FILE, FS, recording)
        
        # Transcription via ton module listener (force le français)
        text = listener.transcribe(TEMP_FILE)
        
        if text and len(text) > 1: # Évite les bruits parasites d'une seule lettre
            print(f"Vous avez dit : {text}")
            send_to_rasa(text)
        else:
            print("... silence ou bruit non reconnu ...")

if __name__ == "__main__":
    try:
        run_voice_loop()
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du pont vocal.")
        if os.path.exists(TEMP_FILE):
            os.remove(TEMP_FILE)