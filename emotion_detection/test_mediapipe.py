import cv2
import mediapipe as mp
from emotion_detection.emergency_detector import EmergencyDetector

# Initialisation
detector = EmergencyDetector()
cap = cv2.VideoCapture(0)

print("--- TEST GESTUELLE URGENCE ---")
print("Instructions : Portez vos mains à votre gorge pour tester l'alerte.")
print("Appuyez sur 'q' pour quitter.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Analyse via le module EmergencyDetector (qui utilise MediaPipe)
    emergency, reason = detector.analyze_frame(frame)

    # Affichage
    color = (0, 0, 255) if emergency and "étouffement" in reason else (0, 255, 0)
    status = "ALERTE : ÉTOUFFEMENT" if emergency and "étouffement" in reason else "Normal"
    
    cv2.putText(frame, status, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
    cv2.imshow('Test MediaPipe - MediBot', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()