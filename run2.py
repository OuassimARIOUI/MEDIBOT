import cv2
import time
import os
from emotion_detection.emotion_detector import EmotionDetector
from emotion_detection.emergency_detector import EmergencyDetector
from emotion_detection.alert_system import AlertSystem

def log_vision(msg, color="\033[95m"):
    print(f"{color}[VISION] {msg}\033[0m")

def main():
    log_vision("Démarrage du moteur de vision (venv2)...", "\033[96m")
    
    # Initialisation des moteurs
    emotion_engine = EmotionDetector()
    emergency_engine = EmergencyDetector()
    alert_sys = AlertSystem() # Envoie les alertes à http://localhost:5000/alerts

    # Utilisation de la webcam (ou caméra robot si mappée sur PC)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        log_vision("Erreur: Impossible d'accéder à la caméra", "\033[91m")
        return

    log_vision("Surveillance active (Émotions + Urgences)")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # 1. Détection d'Urgence (Respiration / Étouffement)
        emergency, reason = emergency_engine.analyze_frame(frame)
        if emergency:
            log_vision(f"!!! ALERTE DETECTÉE : {reason} !!!", "\033[91m")
            alert_sys.send_alert(level=2, reason=reason)

        # 2. Détection d'Émotion
        else:
            emotion = emotion_engine.analyze_emotion(frame)
            if emotion != "neutral":
                log_vision(f"Patient ressenti : {emotion}")
                alert_sys.send_alert(level=1, reason=f"Emotion: {emotion}")

        # Affichage retour vidéo
        cv2.imshow("MediBot Vision Engine (venv2)", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()