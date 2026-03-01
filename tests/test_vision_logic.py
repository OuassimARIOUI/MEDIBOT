import pytest
import numpy as np
from unittest.mock import MagicMock
import time
from emotion_detection.emergency_detector import EmergencyDetector
from emotion_detection.emotion_rules import get_medibot_reaction

# 1. Test des Réactions (Emotion Rules) - OK
def test_emotion_rules_logic():
    res_sad = get_medibot_reaction("sad")
    assert "triste" in res_sad["msg"].lower()
    assert "BLEU" in res_sad["leds"]

# 2. Test de la Détection d'Urgence (Simulée) - OK
def test_choking_detection_logic():
    detector = EmergencyDetector()
    
    class MockLandmark:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    mock_landmarks = [MockLandmark(0.5, 0.5) for _ in range(33)]
    mock_landmarks[0] = MockLandmark(0.5, 0.2)   # Nez
    mock_landmarks[11] = MockLandmark(0.4, 0.5)  # Epaule G
    mock_landmarks[12] = MockLandmark(0.6, 0.5)  # Epaule D
    mock_landmarks[15] = MockLandmark(0.5, 0.35) # Poignet au cou

    assert detector.detect_choking_sign(mock_landmarks) is True

def test_emergency_alert_level():
    detector = EmergencyDetector()

    # On neutralise MediaPipe avec des landmarks simulés (non None)
    mock_result = MagicMock()
    mock_result.pose_landmarks = MagicMock()  # <-- Ne pas mettre None !
    mock_result.pose_landmarks.landmark = [MagicMock(x=0.5, y=0.5)] * 33
    detector.pose.process = MagicMock(return_value=mock_result)

    # On simule : pas d'étouffement
    detector.detect_choking_sign = MagicMock(return_value=False)

    # On force la respiration à False
    detector.detect_breathing = MagicMock(return_value=False)

    # On simule que 10 secondes se sont écoulées
    detector.last_check_time = time.time() - 11  # <-- Clé du fix !

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    emergency, reason = detector.analyze_frame(frame)

    assert emergency is True
    assert "respiration" in reason.lower()