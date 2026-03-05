#!/usr/bin/env python3
"""
_run_emotion.py — Point d'entrée de la détection d'émotions.

Conçu pour être lancé dans un venv SÉPARÉ (EMOTION_VENV_PYTHON)
qui contient deepface + tensorflow sans conflit avec Rasa.

Utilise :
  - deepface          → analyse des émotions sur chaque frame
  - mediapipe         → détection urgences (étouffement, respiration)
  - Pepper camera     → si PEPPER_IP est défini (sinon webcam PC)
  - alert_system.py   → envoie les alertes au dashboard Flask via HTTP
"""

import os
import sys
import time

# --- Ajouter le répertoire racine MEDIBOT au PYTHONPATH ---
# Permet d'importer robot_control.pepper_camera, etc.
ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
# Ajouter aussi le dossier courant (emotion_detection/)
SELF_DIR = os.path.dirname(os.path.abspath(__file__))
if SELF_DIR not in sys.path:
    sys.path.insert(0, SELF_DIR)

# --- Charger .env ---
try:
    from dotenv import load_dotenv
    from pathlib import Path
    _env = Path(__file__).resolve().parent.parent / ".env"
    if _env.exists():
        load_dotenv(dotenv_path=_env)
        print(f"[ENV] .env chargé depuis {_env}")
except ImportError:
    pass

# --- Configuration Pepper ---
PEPPER_IP = os.getenv("PEPPER_IP")
PEPPER_PORT = int(os.getenv("PEPPER_PORT", "9559"))
PATIENT_ID = os.getenv("PATIENT_ID", "PAT001")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:5000/api/alerts")

# --- Connexion Pepper (optionnelle) ---
pep_session = None
if PEPPER_IP:
    try:
        import qi
        pep_session = qi.Session()
        pep_session.connect(f"tcp://{PEPPER_IP}:{PEPPER_PORT}")
        print(f"[EMOTION] Session Pepper → {PEPPER_IP}:{PEPPER_PORT}")
    except ImportError:
        print("[EMOTION] Module 'qi' non disponible — mode webcam PC")
    except Exception as e:
        print(f"[EMOTION] Pepper non connecté ({e}) — mode webcam PC")

# --- Imports métier (deepface chargé ici, dans le bon venv) ---
from emotion_detector import EmotionPipeline
from emergency_detector import EmergencyDetector
from video_stream import VideoStream
from alert_system import AlertSystem

# --- Initialisation ---
pipeline = EmotionPipeline(
    patient_id=PATIENT_ID,
    pepper_session=pep_session,
    alert_url=DASHBOARD_URL,
)
emergency = EmergencyDetector()
alert_sys = AlertSystem(dashboard_url=DASHBOARD_URL)

# Source vidéo : caméra Pepper si connecté, sinon webcam PC (index 0)
video_src = "pepper" if pep_session else 0
stream = VideoStream(source=video_src, pepper_session=pep_session)
print(f"[EMOTION] Démarrage (source={'Pepper camera' if pep_session else 'webcam PC'})...")

# --- Boucle principale ---
try:
    while True:
        frame = stream.get_frame()
        if frame is None:
            time.sleep(0.2)
            continue

        # 1) Détection des émotions (deepface)
        emotion = pipeline.process_frame(frame)

        # 2) Détection d'urgences physiques (mediapipe : étouffement, respiration)
        is_emergency, reason = emergency.analyze_frame(frame)
        if is_emergency:
            print(f"[URGENCE] {reason}")
            alert_sys.send_alert(level=2, reason=reason, patient_id=PATIENT_ID)

        time.sleep(0.2)  # ~5 fps

except KeyboardInterrupt:
    print("\n[EMOTION] Arrêt demandé (CTRL+C).")
except Exception as e:
    print(f"[EMOTION] Erreur fatale : {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    stream.release()
    print("[EMOTION] Arrêt propre.")
