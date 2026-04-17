"""Quick verification that all emotion_detection imports work."""
import cv2
print("opencv", cv2.__version__)

import numpy as np
print("numpy", np.__version__)

import mediapipe as mp
print("mediapipe", mp.__version__)

pose = mp.solutions.pose.Pose(static_image_mode=True)
print("Pose init OK")
pose.close()

from emergency_detector import EmergencyDetector
print("EmergencyDetector import OK")

from emotion_detector import EmotionDetector
print("EmotionDetector import OK")

print("\nAll imports OK - emotion detection is ready!")
