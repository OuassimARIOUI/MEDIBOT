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
DURATION = 6    # Temps d'écoute augmenté pour phrases complètes
TEMP_FILE = "temp_voice.wav"
MIN_ENERGY_THRESHOLD = 0.01  # Seuil pour détecter la parole (ajustable)

# --- INITIALISATION ---
print("Chargement des modules (Whisper & TTS)...")
print("[INFO] Utilisation du modèle 'base' pour meilleure précision...")
listener = MediBotListener(model_size="base") # Modèle plus précis que 'tiny'
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

def has_speech(audio_data, threshold=MIN_ENERGY_THRESHOLD):
    """Détecte si l'audio contient de la parole (énergie > seuil)."""
    energy = np.sqrt(np.mean(audio_data**2))
    return energy > threshold

def run_voice_loop():
    """Boucle principale : Écoute -> Transcription -> RASA -> Voix."""
    print("\n=== MediBot est prêt ! (CTRL+C pour arrêter) ===")
    print("[ASTUCE] Parlez clairement pendant 3-5 secondes.")
    print("[ASTUCE] Exemples : 'Je suis Ariou Ouassim' ou 'SOS j'ai besoin d'aide'\n")
    
    while True:
        print("\n🎤 --- ÉCOUTE en cours... ---")
        # Capture audio
        recording = sd.rec(int(DURATION * FS), samplerate=FS, channels=1, dtype='float32')
        sd.wait()
        
        # Vérification de l'activité vocale
        if not has_speech(recording):
            print("   ... Aucune voix détectée (trop silencieux) ...")
            continue
        
        # Sauvegarde pour Whisper
        write(TEMP_FILE, FS, recording)
        
        # Transcription via ton module listener (force le français)
        print("   ⏳ Transcription en cours...")
        text = listener.transcribe(TEMP_FILE)
        
        if text and len(text) > 2: # Évite les bruits parasites
            print(f"✅ Vous avez dit : {text}")
            send_to_rasa(text)
        else:
            print("   ❌ Aucun texte reconnu (bruit parasite)")

if __name__ == "__main__":
    try:
        run_voice_loop()
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du pont vocal.")
        if os.path.exists(TEMP_FILE):
            os.remove(TEMP_FILE)