"""
run2.py -- Boucle principale de detection MediBot.

Lance la detection d'emotions (DeepFace) et d'urgences (MediaPipe)
en temps reel via la webcam ou la camera Pepper.

Quand une urgence est detectee (etouffement, absence de respiration) :
  -> Alerte CRITIQUE inseree en BD + Dashboard mis a jour + Infirmiers notifies

Quand une emotion est detectee (happy, sad, angry, fear...) :
  -> Emotion enregistree dans emotion_logs + Alerte si detresse + Dashboard MAJ
"""

import cv2
import time
import os
import sys
import logging

# Ajouter le dossier emotion_detection au path pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "emotion_detection"))

from emotion_detection.emotion_detector import EmotionDetector
from emotion_detection.emergency_detector import EmergencyDetector
from emotion_detection.alert_system import AlertSystem

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("MediBot.run2")

# ID du patient surveille (configurable via variable d'environnement)
PATIENT_ID = os.getenv("PATIENT_ID", "PAT001")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:5000/api/alerts")


def main():
    print("=" * 60)
    print("  MEDIBOT - Demarrage Vision + Analyse")
    print("=" * 60)
    print(f"  Patient : {PATIENT_ID}")
    print(f"  Dashboard : {DASHBOARD_URL}")
    print("=" * 60)
    print()

    # Initialisation des detecteurs
    detector = EmotionDetector()
    emergency = EmergencyDetector(
        patient_id=PATIENT_ID,
        dashboard_url=DASHBOARD_URL
    )
    alert_system = AlertSystem(dashboard_url=DASHBOARD_URL)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERREUR] Impossible d'ouvrir la camera.")
        return

    print("[SENSEUR] Camera ouverte. Surveillance en cours...")
    print("[SENSEUR] Appuyez sur 'q' pour quitter.\n")

    # Dictionnaire de correspondance Severite par emotion
    severity_map = {
        "sad": "medium",
        "angry": "high",
        "fear": "high",
        "surprise": "low",
        "neutral": "low",
        "happy": "low",
        "disgust": "low",
    }

    # Compteur pour eviter le spam console
    frame_count = 0
    last_emotion_logged = None
    last_emotion_time = 0
    EMOTION_LOG_COOLDOWN = 10  # secondes entre deux logs BD pour la meme emotion

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # ============================================================
        # 1. DETECTION D'URGENCE (priorite maximale)
        # ============================================================
        is_emergency, reason = emergency.analyze_frame(frame)

        if is_emergency:
            # L'EmergencyDetector gere deja :
            #   - Insertion BD (severity='critical', alert_type='emergency')
            #   - Envoi au dashboard Flask
            #   - Notification infirmiers
            #   - Alerte vocale Pepper
            print(f"\n{'!'*60}")
            print(f"  [URGENCE] {reason}")
            print(f"  -> Alerte CRITIQUE envoyee (BD + Dashboard + Infirmiers)")
            print(f"{'!'*60}\n")

        # ============================================================
        # 2. DETECTION D'EMOTION
        # ============================================================
        emotion = detector.analyze_emotion(frame)

        if emotion != "unknown" and emotion != "neutral":
            severity = severity_map.get(emotion, "medium")
            now = time.time()

            # Affichage console
            if frame_count % 5 == 0:  # Affichage toutes les 5 frames
                print(f"  [EMOTION] Detecte: {emotion} (severite: {severity})")

            # Enregistrer l'emotion dans la BD (avec cooldown)
            if emotion != last_emotion_logged or (now - last_emotion_time) > EMOTION_LOG_COOLDOWN:
                alert_system.log_emotion(
                    patient_id=PATIENT_ID,
                    emotion=emotion,
                    severity=severity
                )
                last_emotion_logged = emotion
                last_emotion_time = now
                logger.info(f"Emotion '{emotion}' enregistree en BD pour {PATIENT_ID}")

                # Si emotion de detresse -> alerte + notification
                if severity in ("high", "medium") and emotion in ("sad", "angry", "fear"):
                    alert_system.send_emotion_alert(
                        emotion=emotion,
                        patient_id=PATIENT_ID,
                        severity=severity
                    )
                    print(f"  -> Alerte EMOTION envoyee [{severity.upper()}]: {emotion}")

        # Affichage video
        cv2.imshow("MediBot - Sensor Engine", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    print("\n[SENSEUR] Arret de la surveillance.")
    print("[SENSEUR] Toutes les donnees ont ete sauvegardees en BD.")


if __name__ == "__main__":
    main()