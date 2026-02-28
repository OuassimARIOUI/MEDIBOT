import cv2
from deepface import DeepFace

# Initialisation de la caméra
cap = cv2.VideoCapture(0)

print("Appuyez sur 'q' pour quitter la fenêtre vidéo.")

while True:
    ret, frame = cap.read()
    if not ret: break

    try:
        # Analyse rapide (on ne force pas la détection pour éviter les lags)
        results = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        emotion = results[0]['dominant_emotion']
        
        # Affichage du texte sur l'image
        cv2.putText(frame, f"Emotion: {emotion}", (50, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    except:
        pass

    cv2.imshow('MediBot Vision - Test Empathie', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()