from deepface import DeepFace
import cv2

class EmotionDetector:
    def __init__(self):
        # On définit les émotions qu'on souhaite suivre
        self.target_emotions = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']

    def analyze_emotion(self, frame):
        try:
            # Analyse l'émotion dominante
            results = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            # DeepFace renvoie une liste (au cas où il y a plusieurs visages)
            return results[0]['dominant_emotion']
        except Exception as e:
            print(f"Erreur analyse : {e}")
            return "unknown"