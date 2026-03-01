import cv2
import rasa
import numpy as np
from deepface import DeepFace

print(f"\n--- DIAGNOSTIC ENVIRONNEMENT ---")
print(f"Numpy: {np.__version__} (Cible: 1.23.x ou 1.24.x)")
print(f"OpenCV: {cv2.__version__} (Cible: 4.8.x)")

try:
    # Test de chargement du modèle d'émotion
    print("Tentative de chargement du modèle Emotion...")
    DeepFace.build_model("Emotion")
    print("✅ DEEPFACE: OK (Modèle chargé)")
except Exception as e:
    print(f"❌ DEEPFACE Error: {e}")

try:
    print(f"Rasa Version: {rasa.__version__}")
    print("✅ RASA: OK")
except Exception as e:
    print(f"❌ RASA Error: {e}")