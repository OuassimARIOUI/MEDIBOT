"""
voice_bridge.py - Pont vocal entre le patient et Rasa.

Deux modes de fonctionnement :
  - MODE PC (défaut)     : microphone + haut-parleur du PC (développement/test)
  - MODE PEPPER          : microphone NAOqi + TTS ALTextToSpeech du robot

BUG CORRIGE 5+6 : La version précédente utilisait TOUJOURS pyttsx3 (PC)
et sounddevice (micro PC), même quand déployé sur Pepper.
Désormais, si PEPPER_IP est défini dans l'environnement, tout passe par le robot.
"""

import os
import time
import numpy as np
import requests
from scipy.io.wavfile import write
from whisper_listener import MediBotListener

# --- CONFIGURATION ---
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"
FS = 16000        # Fréquence d'échantillonnage Whisper
DURATION = 8      # BUG CORRIGE: 6s était trop court pour phrases longues
TEMP_FILE = "temp_voice.wav"
MIN_ENERGY_THRESHOLD = 0.01  # Seuil de détection de parole

# --- Détection du mode (Pepper vs PC) ---
PEPPER_IP = os.getenv("PEPPER_IP")
PEPPER_PORT = int(os.getenv("PEPPER_PORT", "9559"))
USE_PEPPER = bool(PEPPER_IP)

print("Chargement du modèle Whisper...")
print("[INFO] Utilisation du modèle 'base' pour meilleure précision...")
listener = MediBotListener(model_size="base")

# ===================================================================
# TTS — PAROLE DU ROBOT
# ===================================================================

def speak(text: str) -> None:
    """
    Fait parler le bot.
    - Sur Pepper  : ALTextToSpeech (voix du robot)
    - Sur PC      : pyttsx3 (simulation)
    BUG CORRIGE 5: n'utilisait que pyttsx3 même quand PEPPER_IP était défini.
    """
    if not text:
        return
    if USE_PEPPER:
        _speak_pepper(text)
    else:
        _speak_pc(text)


def _speak_pepper(text: str) -> None:
    """Parler via ALTextToSpeech du robot Pepper."""
    try:
        import qi
        session = qi.Session()
        session.connect(f"tcp://{PEPPER_IP}:{PEPPER_PORT}")
        tts = session.service("ALTextToSpeech")
        tts.setLanguage("French")
        tts.setParameter("speed", 90)
        tts.setParameter("volume", 0.85)
        tts.say(text)
        print(f"[PEPPER TTS] Robot dit : {text}")
    except ImportError:
        print("[PEPPER TTS] Module 'qi' non disponible, fallback pyttsx3.")
        _speak_pc(text)
    except Exception as e:
        print(f"[PEPPER TTS] Erreur : {e}, fallback pyttsx3.")
        _speak_pc(text)


def _speak_pc(text: str) -> None:
    """Parler via pyttsx3 (simulation PC)."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        try:
            engine.setProperty('voice', 'french')
        except Exception:
            pass
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"[PC TTS] Erreur pyttsx3 : {e}")


# ===================================================================
# MIC — ÉCOUTE DU PATIENT
# ===================================================================

def record_audio() -> np.ndarray:
    """
    Enregistre l'audio du patient.
    - Sur Pepper : ALAudioDevice (micro de la tête du robot)
    - Sur PC     : sounddevice (microphone du PC)
    BUG CORRIGE 6: n'utilisait que sounddevice, donc le patient devait
    parler dans le micro du laptop et non dans celui du robot.
    """
    if USE_PEPPER:
        return _record_pepper()
    else:
        return _record_pc()


def _record_pepper() -> np.ndarray:
    """
    Capture audio depuis les microphones de Pepper (ALAudioRecorder).
    Enregistre sur /home/nao/temp_medibot.wav, puis le lit localement
    si le fichier est accessible (montage NFS ou copie préalable).
    Fallback: micro PC si ALAudioRecorder indisponible.
    """
    try:
        import qi

        session = qi.Session()
        session.connect(f"tcp://{PEPPER_IP}:{PEPPER_PORT}")

        recorder = session.service("ALAudioRecorder")
        remote_path = "/home/nao/temp_medibot.wav"

        # Enregistrement depuis le micro frontal de la tête (channel 3)
        # Tuple : (Left, Right, Front, Rear) — Front uniquement
        recorder.startMicrophonesRecording(remote_path, "wav", FS, (0, 0, 1, 0))
        print(f"[PEPPER MIC] Écoute en cours ({DURATION}s)...")
        time.sleep(DURATION)
        recorder.stopMicrophonesRecording()
        print("[PEPPER MIC] Enregistrement terminé.")

        # Tentative de lecture du fichier si accessible via chemin monté
        local_copy = os.path.join(os.path.dirname(__file__), "pepper_audio.wav")
        if os.path.exists(local_copy):
            from scipy.io.wavfile import read as wavread
            rate, data = wavread(local_copy)
            if data.ndim > 1:
                data = data[:, 0]
            return data.astype(np.float32) / 32768.0

        # Si fichier non accessible localement, fallback PC
        print("[PEPPER MIC] Fichier distant non monté localement, fallback micro PC.")
        return _record_pc()

    except ImportError:
        print("[PEPPER MIC] Module 'qi' non disponible, fallback micro PC.")
        return _record_pc()
    except Exception as e:
        print(f"[PEPPER MIC] Erreur ({e}), fallback micro PC.")
        return _record_pc()


def _record_pc() -> np.ndarray:
    """Capture audio depuis le microphone du PC (mode simulation)."""
    try:
        import sounddevice as sd
        recording = sd.rec(int(DURATION * FS), samplerate=FS, channels=1, dtype='float32')
        sd.wait()
        return recording
    except Exception as e:
        print(f"[PC MIC] Erreur sounddevice : {e}")
        return np.zeros((int(DURATION * FS), 1), dtype='float32')


# ===================================================================
# UTILITAIRES
# ===================================================================

def has_speech(audio_data: np.ndarray, threshold: float = MIN_ENERGY_THRESHOLD) -> bool:
    """Détecte si l'audio contient de la parole (énergie RMS > seuil)."""
    energy = np.sqrt(np.mean(audio_data ** 2))
    return energy > threshold


def send_to_rasa(message: str) -> None:
    """Envoie le texte transcrit à Rasa et fait parler le bot avec la réponse."""
    payload = {"sender": "user_voice", "message": message}
    try:
        response = requests.post(RASA_URL, json=payload, timeout=10)
        res_json = response.json()
        for msg in res_json:
            bot_text = msg.get('text')
            if bot_text:
                print(f"MediBot : {bot_text}")
                speak(bot_text)
    except Exception as e:
        print(f"[RASA] Erreur de connexion : {e}")


# ===================================================================
# BOUCLE PRINCIPALE
# ===================================================================

def run_voice_loop() -> None:
    """Boucle principale : Écoute → Transcription → Rasa → Voix."""
    mode = "PEPPER" if USE_PEPPER else "SIMULATION PC"
    print(f"\n=== MediBot est prêt ! Mode : {mode} (CTRL+C pour arrêter) ===")
    if USE_PEPPER:
        print(f"[INFO] Robot  : {PEPPER_IP}:{PEPPER_PORT}")
        print("[INFO] TTS    : ALTextToSpeech (voix du robot)")
        print("[INFO] MIC    : ALAudioRecorder (microphone de la tête)")
    else:
        print("[INFO] TTS    : pyttsx3 (haut-parleur PC)")
        print("[INFO] MIC    : sounddevice (microphone PC)")
    print("[ASTUCE] Parlez clairement. Exemples : 'Je suis Ouassim' ou 'SOS j'ai besoin d'aide'\n")

    while True:
        icon = "🤖" if USE_PEPPER else "🎤"
        print(f"\n{icon} --- ÉCOUTE en cours ({DURATION}s)... ---")

        recording = record_audio()

        if not has_speech(recording):
            print("   ... Aucune voix détectée (trop silencieux) ...")
            continue

        write(TEMP_FILE, FS, recording)

        print("   ⏳ Transcription en cours...")
        text = listener.transcribe(TEMP_FILE)

        if text and len(text) > 2:
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