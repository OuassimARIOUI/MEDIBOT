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
import sys
import time
import numpy as np
import requests
from scipy.io.wavfile import write

# --- Charger les variables d'environnement (.env) ---
try:
    from dotenv import load_dotenv
    from pathlib import Path
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
        print(f"[ENV] .env chargé depuis {_env_path}")
except ImportError:
    pass  # python-dotenv pas installé

from whisper_listener import MediBotListener

# --- CONFIGURATION ---
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"
FS = 16000        # Fréquence d'échantillonnage Whisper
DURATION = 3      # 5s — bon compromis (8s trop long, 3s trop court)
TEMP_FILE = "temp_voice.wav"
MIN_ENERGY_THRESHOLD = 0.003  # Seuil bas pour ne rien rater (0.01 filtrait trop)

# --- Détection du mode (Pepper vs PC) ---
PEPPER_IP = os.getenv("PEPPER_IP")
PEPPER_PORT = int(os.getenv("PEPPER_PORT", "9559"))
USE_PEPPER = bool(PEPPER_IP)

# --- Session NAOqi singleton (évite d'en recréer une à chaque appel) ---
_pepper_session = None

def _get_pepper_session():
    """Retourne (ou crée) la session NAOqi partagée."""
    global _pepper_session
    if _pepper_session is not None:
        return _pepper_session
    try:
        import qi
        _pepper_session = qi.Session()
        _pepper_session.connect(f"tcp://{PEPPER_IP}:{PEPPER_PORT}")
        print(f"[PEPPER] ✅ Session NAOqi ouverte → {PEPPER_IP}:{PEPPER_PORT}")

        # Forcer le volume master à 100% dès la connexion
        try:
            ad = _pepper_session.service("ALAudioDevice")
            ad.setOutputVolume(100)
            print("[PEPPER] 🔊 Volume master → 100%")
        except Exception:
            pass

        return _pepper_session
    except Exception as e:
        print(f"[PEPPER] ❌ Impossible d'ouvrir la session : {e}")
        return None

print("Chargement du modèle Whisper...")
print("[INFO] Utilisation du modèle 'small' pour meilleure précision...")
listener = MediBotListener(model_size="small")

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
    """Parler via ALTextToSpeech du robot Pepper (session réutilisée)."""
    session = _get_pepper_session()
    if session is None:
        print("[PEPPER TTS] Pas de session NAOqi, fallback pyttsx3.")
        _speak_pc(text)
        return
    try:
        tts = session.service("ALTextToSpeech")
        tts.setLanguage("French")
        tts.setParameter("speed", 85)
        tts.setVolume(1.0)
        tts.say(text)
        print(f"[PEPPER TTS] 🗣️  Robot dit : {text[:80]}")
    except Exception as e:
        print(f"[PEPPER TTS] Erreur : {e}, fallback pyttsx3.")
        # Reset session en cas de déconnexion
        global _pepper_session
        _pepper_session = None
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
# AUDIO — LECTURE DE FICHIERS MUSICAUX (WAV)
# ===================================================================

def play_audio(wav_path: str) -> None:
    """
    Joue un fichier WAV instrumental.
    - Sur Pepper  : ALAudioPlayer (haut-parleur du robot)
    - Sur PC      : sounddevice ou simpleaudio (haut-parleur du PC)
    """
    if not wav_path or not os.path.exists(wav_path):
        print(f"[AUDIO] ⚠️ Fichier introuvable : {wav_path}")
        return

    print(f"[AUDIO] 🎵 Lecture : {os.path.basename(wav_path)}")

    if USE_PEPPER:
        _play_audio_pepper(wav_path)
    else:
        _play_audio_pc(wav_path)


def _play_audio_pepper(wav_path: str) -> None:
    """Joue un WAV via ALAudioPlayer de Pepper.
    
    Étapes :
    1. Transfert du fichier WAV vers Pepper via SFTP (paramiko) ou SCP
    2. Lecture sur le haut-parleur du robot via ALAudioPlayer.playFile()
    """
    session = _get_pepper_session()
    if session is None:
        print("[PEPPER AUDIO] Pas de session NAOqi, fallback PC.")
        _play_audio_pc(wav_path)
        return

    remote_path = "/home/nao/medibot_song.wav"

    # --- Étape 1 : Transférer le fichier WAV vers Pepper ---
    transferred = False
    # Tenter SFTP via paramiko (plus fiable que scp, surtout sur Windows)
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(PEPPER_IP, port=22, username="nao", password="nao", timeout=5)
        sftp = ssh.open_sftp()
        sftp.put(wav_path, remote_path)
        sftp.close()
        ssh.close()
        transferred = True
        print(f"[PEPPER AUDIO] ✅ Fichier transféré via SFTP → {remote_path}")
    except ImportError:
        print("[PEPPER AUDIO] paramiko non installé, tentative SCP...")
    except Exception as e:
        print(f"[PEPPER AUDIO] SFTP échoué ({e}), tentative SCP...")

    # Fallback SCP si paramiko indisponible ou échoué
    if not transferred:
        try:
            import subprocess
            scp_result = subprocess.run(
                ["scp", "-o", "StrictHostKeyChecking=no",
                 "-o", "UserKnownHostsFile=/dev/null",
                 wav_path, f"nao@{PEPPER_IP}:{remote_path}"],
                capture_output=True, timeout=15
            )
            if scp_result.returncode == 0:
                transferred = True
                print(f"[PEPPER AUDIO] ✅ Fichier transféré via SCP → {remote_path}")
            else:
                print(f"[PEPPER AUDIO] SCP échoué: {scp_result.stderr.decode(errors='ignore')}")
        except Exception as e:
            print(f"[PEPPER AUDIO] SCP erreur : {e}")

    if not transferred:
        print("[PEPPER AUDIO] ⚠️ Impossible de transférer le fichier, fallback PC.")
        _play_audio_pc(wav_path)
        return

    # --- Étape 2 : Jouer sur le robot via ALAudioPlayer ---
    try:
        audio_player = session.service("ALAudioPlayer")
        # playFile() est bloquant et joue le fichier directement
        audio_player.playFile(remote_path)
        print(f"[PEPPER AUDIO] 🔊 Robot joue la musique.")
    except Exception as e:
        print(f"[PEPPER AUDIO] Erreur lecture ({e}), fallback PC.")
        global _pepper_session
        _pepper_session = None
        _play_audio_pc(wav_path)


def _play_audio_pc(wav_path: str) -> None:
    """Joue un WAV sur les haut-parleurs du PC."""
    try:
        import sounddevice as sd
        from scipy.io.wavfile import read as wavread
        rate, data = wavread(wav_path)
        if data.ndim > 1:
            data = data[:, 0]  # Mono
        # Convertir en float32 pour sounddevice
        audio = data.astype(np.float32) / 32768.0
        sd.play(audio, samplerate=rate)
        sd.wait()  # Attendre la fin de la lecture
        print(f"[PC AUDIO] ✅ Lecture terminée.")
    except ImportError:
        # Fallback : utiliser le module wave + pyaudio ou autre
        print("[PC AUDIO] sounddevice non disponible, tentative avec wave...")
        try:
            import wave
            import struct
            import pyaudio
            wf = wave.open(wav_path, 'rb')
            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )
            chunk = 1024
            data_chunk = wf.readframes(chunk)
            while data_chunk:
                stream.write(data_chunk)
                data_chunk = wf.readframes(chunk)
            stream.stop_stream()
            stream.close()
            p.terminate()
            print(f"[PC AUDIO] ✅ Lecture terminée (pyaudio).")
        except Exception as e2:
            print(f"[PC AUDIO] ❌ Impossible de jouer l'audio : {e2}")
    except Exception as e:
        print(f"[PC AUDIO] Erreur : {e}")


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
    1. Enregistre sur /home/nao/temp_medibot.wav via NAOqi
    2. Récupère le fichier via SFTP (paramiko) ou SCP
    3. Lit le WAV localement et retourne un numpy array
    """
    session = _get_pepper_session()
    if session is None:
        print("[PEPPER MIC] Pas de session NAOqi, fallback micro PC.")
        return _record_pc()
    try:
        recorder = session.service("ALAudioRecorder")
        remote_path = "/home/nao/temp_medibot.wav"
        local_path = os.path.join(os.path.dirname(__file__), "pepper_audio.wav")

        # Supprimer l'ancien enregistrement distant s'il existe
        try:
            recorder.stopMicrophonesRecording()
        except Exception:
            pass

        # Enregistrement — micro frontal + gauche
        # NAOqi attend une LISTE (AL::ALValue), PAS un tuple
        # [Left, Right, Front, Rear] — 1=actif, 0=inactif
        channels = [0, 0, 1, 0]   # Front uniquement (le plus proche du patient)
        print(f"[PEPPER MIC] 🎤 Écoute en cours ({DURATION}s)...")
        recorder.startMicrophonesRecording(remote_path, "wav", FS, channels)
        time.sleep(DURATION)
        recorder.stopMicrophonesRecording()
        print("[PEPPER MIC] ✅ Enregistrement terminé.")

        # --- Récupérer le fichier via SFTP ---
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(PEPPER_IP, username="nao", password="nao", timeout=5)
            sftp = ssh.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            ssh.close()
            print(f"[PEPPER MIC] 📥 Fichier récupéré via SFTP → {local_path}")
        except ImportError:
            # paramiko pas installé → essayer scp via subprocess
            print("[PEPPER MIC] paramiko non installé, tentative scp...")
            import subprocess
            result = subprocess.run(
                ["scp", f"nao@{PEPPER_IP}:{remote_path}", local_path],
                capture_output=True, timeout=10
            )
            if result.returncode != 0:
                print(f"[PEPPER MIC] ⚠️ SCP échoué : {result.stderr.decode()}")
                print("[PEPPER MIC] Fallback micro PC.")
                return _record_pc()
        except Exception as e:
            print(f"[PEPPER MIC] ⚠️ Transfert échoué ({e}), fallback micro PC.")
            return _record_pc()

        # --- Lire le WAV récupéré ---
        if os.path.exists(local_path) and os.path.getsize(local_path) > 100:
            from scipy.io.wavfile import read as wavread
            rate, data = wavread(local_path)
            if data.ndim > 1:
                data = data[:, 0]  # Mono uniquement
            audio = data.astype(np.float32) / 32768.0
            energy = np.sqrt(np.mean(audio ** 2))
            print(f"[PEPPER MIC] 📊 Énergie audio : {energy:.4f} (seuil: {MIN_ENERGY_THRESHOLD})")
            return audio
        else:
            print("[PEPPER MIC] ⚠️ Fichier audio vide ou introuvable, fallback micro PC.")
            return _record_pc()

    except Exception as e:
        print(f"[PEPPER MIC] Erreur ({e}), fallback micro PC.")
        # Ne reset la session que si c'est une erreur de connexion
        if "connection" in str(e).lower() or "disconnected" in str(e).lower():
            global _pepper_session
            _pepper_session = None
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


def send_to_rasa(message: str, max_retries: int = 3) -> None:
    """Envoie le texte transcrit à Rasa et fait parler le bot avec la réponse.
    
    Gère deux types de messages Rasa :
    - text       → prononcé via TTS (speak)
    - play_audio → fichier WAV joué via play_audio()
    """
    payload = {"sender": "user_voice", "message": message}
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(RASA_URL, json=payload, timeout=30)
            res_json = response.json()
            for msg in res_json:
                # --- Message audio instrumental ---
                custom = msg.get('custom') or {}
                audio_path = custom.get('play_audio')
                if audio_path:
                    play_audio(audio_path)
                    continue
                # --- Message texte classique ---
                bot_text = msg.get('text')
                if bot_text:
                    print(f"MediBot : {bot_text}")
                    speak(bot_text)
            return  # Succès, on quitte
        except requests.exceptions.ConnectionError:
            if attempt < max_retries:
                print(f"[RASA] Serveur pas encore prêt, tentative {attempt}/{max_retries}... (attente 5s)")
                time.sleep(5)
            else:
                print(f"[RASA] ⚠️ Serveur Rasa injoignable sur {RASA_URL}")
                print(f"[RASA]    Vérifiez que Rasa tourne : curl {RASA_URL}")
        except Exception as e:
            print(f"[RASA] Erreur : {e}")
            return


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
    print("[ASTUCE] Parlez clairement. Exemples : 'Je suis Ouassim' ou 'SOS j'ai besoin d'aide'")

    # Attendre que Rasa soit prêt (il met ~60s pour charger le modèle)
    print("\n[INFO] Attente que Rasa soit prêt...")
    for i in range(24):  # 24 × 5s = 2 min max
        try:
            r = requests.get(RASA_URL.replace("/webhooks/rest/webhook", "/"), timeout=3)
            if r.status_code == 200:
                print("[INFO] ✅ Rasa est prêt !\n")
                break
        except Exception:
            pass
        print(f"[INFO] Rasa pas encore prêt... ({(i+1)*5}s)")
        time.sleep(5)
    else:
        print("[WARN] ⚠️ Rasa n'a pas répondu après 2 min. On continue quand même.\n")

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