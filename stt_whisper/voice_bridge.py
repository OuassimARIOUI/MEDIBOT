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
DURATION = 5      # Fallback : durée maximale d'enregistrement (sécurité VAD)
TEMP_FILE = "temp_voice.wav"
MIN_ENERGY_THRESHOLD = 0.003  # Seuil bas pour ne rien rater (0.01 filtrait trop)

# ── Paramètres VAD (Voice Activity Detection) ───────────────────────────
# OPTIMISATION LATENCE : silence end-pointing 800→450ms, max 8→6s.
# Le robot répond ainsi ~350ms plus vite après la fin de la phrase.
VAD_CHUNK_MS = 30                # taille d'une trame d'analyse (ms)
VAD_START_THRESHOLD = 0.005      # énergie RMS requise pour déclencher l'enregistrement
VAD_SILENCE_MS = int(os.getenv("VAD_SILENCE_MS", "450"))   # 800→450ms : end-pointing plus rapide
VAD_PRE_ROLL_MS = 200            # on conserve 200 ms avant la détection (mot de début)
VAD_MIN_SPEECH_MS = 350          # on rejette les bruits < 350 ms
VAD_MAX_DURATION_S = 6           # plafond absolu (sécurité) — phrases courtes en gériatrie
VAD_LISTEN_TIMEOUT_S = 6         # si aucune voix détectée, on relâche la main

# ── Silence timeout après une question critique ────────────────────────
# Si le bot a posé une question qui attend une réponse et que le patient
# reste silencieux plus de SILENCE_TIMEOUT_S secondes, on notifie Rasa.
SILENCE_TIMEOUT_S = 5
_awaiting_answer_until: float = 0.0  # timestamp limite pour une réponse
_silence_keywords = (
    "ça va", "comment vous sentez",
    "voulez-vous que j'appelle", "voulez-vous que j appelle",
    "souhaitez-vous", "est-ce que vous allez bien",
)

# Fichier flag écrit par async_vision_pipeline lors d'une urgence vitale confirmée
_EMERGENCY_FLAG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs", "emergency.flag"
)
_last_emergency_announce: float = 0.0  # horodatage de la dernière annonce TTS urgence

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
# Modèle pilotable via env WHISPER_MODEL (defaut: "base" sur CPU, "small" sur GPU)
# "base" est ~3x plus rapide que "small" en CPU avec une précision FR très correcte.
listener = MediBotListener()

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


def _fetch_pepper_audio(remote_path: str, local_path: str):
    """
    Transfère le WAV enregistré sur Pepper via SFTP (ou SCP en fallback)
    et retourne un numpy array float32. Retourne None en cas d'échec.
    """
    transferred = False
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(PEPPER_IP, username="nao", password="nao", timeout=5)
        sftp = ssh.open_sftp()
        sftp.get(remote_path, local_path)
        sftp.close()
        ssh.close()
        transferred = True
        print(f"[PEPPER MIC] 📥 Fichier récupéré via SFTP → {local_path}")
    except ImportError:
        print("[PEPPER MIC] paramiko non installé, tentative scp...")
    except Exception as e:
        print(f"[PEPPER FETCH] SFTP échoué ({e}), tentative SCP...")

    if not transferred:
        try:
            import subprocess
            r = subprocess.run(
                ["scp", "-o", "StrictHostKeyChecking=no",
                 f"nao@{PEPPER_IP}:{remote_path}", local_path],
                capture_output=True, timeout=10
            )
            if r.returncode == 0:
                transferred = True
            else:
                print(f"[PEPPER FETCH] SCP échoué: {r.stderr.decode(errors='ignore')}")
        except Exception as e:
            print(f"[PEPPER FETCH] SCP erreur: {e}")

    if not transferred or not os.path.exists(local_path) or os.path.getsize(local_path) < 100:
        return None

    try:
        from scipy.io.wavfile import read as wavread
        _, data = wavread(local_path)
        if data.ndim > 1:
            data = data[:, 0]
        return data.astype(np.float32) / 32768.0
    except Exception as e:
        print(f"[PEPPER FETCH] Lecture WAV échouée: {e}")
        return None


def _record_pepper() -> np.ndarray:
    """
    Capture audio depuis les microphones de Pepper (ALAudioRecorder).
    1. Enregistre sur /home/nao/temp_medibot.wav via NAOqi pendant DURATION secondes
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

        try:
            recorder.stopMicrophonesRecording()
        except Exception:
            pass

        # [Left, Right, Front, Rear] — Front uniquement (le plus proche du patient)
        channels = [0, 0, 1, 0]
        print(f"[PEPPER MIC] 🎤 Écoute en cours ({DURATION}s)...")
        recorder.startMicrophonesRecording(remote_path, "wav", FS, channels)
        time.sleep(DURATION)
        recorder.stopMicrophonesRecording()
        print("[PEPPER MIC] ✅ Enregistrement terminé.")

        audio = _fetch_pepper_audio(remote_path, local_path)
        if audio is not None:
            energy = float(np.sqrt(np.mean(audio ** 2)))
            print(f"[PEPPER MIC] 📊 Énergie audio : {energy:.4f} (seuil: {MIN_ENERGY_THRESHOLD})")
            return audio

        print("[PEPPER MIC] ⚠️ Fichier audio vide ou introuvable, fallback micro PC.")
        return _record_pc()

    except Exception as e:
        print(f"[PEPPER MIC] Erreur ({e}), fallback micro PC.")
        if "connection" in str(e).lower() or "disconnected" in str(e).lower():
            global _pepper_session
            _pepper_session = None
        return _record_pc()


def _record_pc() -> np.ndarray:
    """
    Capture audio via VAD streaming (énergie RMS, end-pointing sur silence).

    Principe :
        1. Ouvre un flux micro en continu (InputStream)
        2. Analyse des trames de 30 ms
        3. Déclenche l'enregistrement quand l'énergie dépasse VAD_START_THRESHOLD
        4. Conserve un pre-roll de 200 ms (pour attraper le début du mot)
        5. Ferme quand 800 ms de silence consécutif sont détectés
        6. Rejette les énoncés trop courts (< 400 ms)
        7. Plafond absolu : VAD_MAX_DURATION_S secondes

    Retourne un numpy float32 contenant uniquement la parole détectée
    (ou un array vide en cas de timeout / silence total).
    """
    try:
        import sounddevice as sd
        from collections import deque

        chunk_samples = int(FS * VAD_CHUNK_MS / 1000)
        preroll_chunks = max(1, VAD_PRE_ROLL_MS // VAD_CHUNK_MS)
        silence_chunks_needed = max(1, VAD_SILENCE_MS // VAD_CHUNK_MS)
        min_speech_chunks = max(1, VAD_MIN_SPEECH_MS // VAD_CHUNK_MS)
        max_chunks = int(VAD_MAX_DURATION_S * 1000 / VAD_CHUNK_MS)
        listen_timeout_chunks = int(VAD_LISTEN_TIMEOUT_S * 1000 / VAD_CHUNK_MS)

        preroll = deque(maxlen=preroll_chunks)
        recorded = []
        speaking = False
        silence_run = 0
        idle_run = 0
        speech_chunks = 0

        with sd.InputStream(samplerate=FS, channels=1, dtype='float32',
                            blocksize=chunk_samples) as stream:
            while True:
                chunk, _ = stream.read(chunk_samples)
                chunk = chunk.flatten()
                energy = float(np.sqrt(np.mean(chunk ** 2)))

                if not speaking:
                    preroll.append(chunk)
                    if energy > VAD_START_THRESHOLD:
                        # Début détecté → on garde le pre-roll
                        recorded.extend(preroll)
                        recorded.append(chunk)
                        speaking = True
                        silence_run = 0
                        speech_chunks = 1
                    else:
                        idle_run += 1
                        if idle_run >= listen_timeout_chunks:
                            # Rien entendu → on relâche proprement
                            return np.zeros(0, dtype=np.float32)
                else:
                    recorded.append(chunk)
                    speech_chunks += 1
                    if energy > VAD_START_THRESHOLD:
                        silence_run = 0
                    else:
                        silence_run += 1
                        if silence_run >= silence_chunks_needed:
                            break  # fin naturelle détectée

                    if len(recorded) >= max_chunks:
                        break  # plafond atteint

        if speech_chunks < min_speech_chunks:
            return np.zeros(0, dtype=np.float32)  # rejeté (bruit bref)

        return np.concatenate(recorded).astype(np.float32)

    except Exception as e:
        print(f"[PC MIC] Erreur sounddevice/VAD : {e}")
        return np.zeros(int(DURATION * FS), dtype=np.float32)


# ===================================================================
# UTILITAIRES
# ===================================================================

def _is_vision_emergency_active() -> bool:
    """
    Vérifie si une urgence vitale a été détectée par la caméra.
    Lit le fichier flag écrit par async_vision_pipeline.
    Le flag expire automatiquement après 10 minutes.
    """
    if not os.path.exists(_EMERGENCY_FLAG):
        return False
    try:
        with open(_EMERGENCY_FLAG, encoding="utf-8") as _f:
            ts = float(_f.readline().strip())
        if time.time() - ts > 600:  # expire après 10 min
            try:
                os.remove(_EMERGENCY_FLAG)
            except Exception:
                pass
            return False
        return True
    except Exception:
        return False


def has_speech(audio_data: np.ndarray, threshold: float = MIN_ENERGY_THRESHOLD) -> bool:
    """Détecte si l'audio contient de la parole (énergie RMS > seuil)."""
    energy = np.sqrt(np.mean(audio_data ** 2))
    return energy > threshold


def send_to_rasa(message: str, max_retries: int = 3) -> None:
    """Envoie le texte transcrit à Rasa et fait parler le bot avec la réponse.
    
    Gère deux types de messages Rasa :
    - text       → prononcé via TTS (speak)
    - play_audio → fichier WAV joué via play_audio()

    Si la réponse du bot contient une question critique (ex. « voulez-vous
    que j'appelle quelqu'un ? »), arme un timer de silence SILENCE_TIMEOUT_S
    secondes. Si le patient reste muet après, un intent silence_timeout
    sera envoyé par la boucle principale.
    """
    global _awaiting_answer_until
    payload = {"sender": "user_voice", "message": message}
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(RASA_URL, json=payload, timeout=30)
            res_json = response.json()
            combined_text = ""
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
                    combined_text += " " + bot_text.lower()

            # Armer le timer de silence si le bot a posé une question critique
            if any(k in combined_text for k in _silence_keywords):
                _awaiting_answer_until = time.time() + SILENCE_TIMEOUT_S
                print(f"[VAD] ⏱️  Attente réponse patient ({SILENCE_TIMEOUT_S}s max)")
            else:
                _awaiting_answer_until = 0.0
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

def run_voice_loop(is_emergency_fn=None) -> None:
    """
    Boucle principale : Écoute → Transcription → Rasa → Voix.

    Args:
        is_emergency_fn: callable() -> bool optionnel, fourni par l'orchestrateur.
                         Si retourne True, le cycle Rasa est suspendu (urgence vitale).
    """
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
        if USE_PEPPER:
            print(f"\n{icon} --- ÉCOUTE Pepper ({DURATION}s)... ---")
        else:
            print(f"\n{icon} --- En écoute (VAD actif, max {VAD_MAX_DURATION_S}s)... ---")

        recording = record_audio()

        # VAD renvoie array vide = rien entendu → vérifier si on attendait une réponse critique
        if recording.size == 0:
            global _awaiting_answer_until
            if _awaiting_answer_until > 0 and time.time() >= _awaiting_answer_until:
                print("\n[VAD] 🔕 Silence de 5s après question critique → notification Rasa")
                _awaiting_answer_until = 0.0  # désarmer avant l'envoi
                try:
                    send_to_rasa("/silence_timeout")
                except Exception as _e:
                    print(f"[VAD] Erreur notification silence : {_e}")
            continue

        if not has_speech(recording):
            print("   ... Aucune voix détectée (trop silencieux) ...")
            continue

        write(TEMP_FILE, FS, recording)

        duration_s = len(recording) / FS
        print(f"   ⏳ Transcription en cours ({duration_s:.1f}s captées)...")
        text = listener.transcribe(TEMP_FILE)

        if text and len(text) > 2:
            print(f"✅ Vous avez dit : {text}")
            send_to_rasa(text)
        else:
            print("   ❌ Aucun texte reconnu (bruit ou souffle)")


if __name__ == "__main__":
    try:
        run_voice_loop()
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt du pont vocal.")
        if os.path.exists(TEMP_FILE):
            os.remove(TEMP_FILE)