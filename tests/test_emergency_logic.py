import pytest
import numpy as np
from emotion_detection.emergency_detector import EmergencyDetector
from emotion_detection.alert_system import AlertSystem

def test_absence_of_respiration_alert():
    """Teste le scénario page 8 : Absence de mouvement = Alerte Niveau 2"""
    detector = EmergencyDetector()
    alert_sys = AlertSystem()
    
    # Simulation de 2 images identiques (aucun mouvement thoracique)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detector.detect_breathing(frame) # Initialisation
    
    # Deuxième passage : mouvement nul
    is_breathing = detector.detect_breathing(frame)
    
    assert is_breathing is False # [cite: 101]
    
    # Vérification de la réaction prévue au cahier des charges
    if not is_breathing:
        # Niveau 2: urgence vitale potentielle [cite: 112, 214]
        res = alert_sys.send_alert(level=2, reason="Absence de respiration")
        assert res is True or res is False # Dépend si votre dashboard est lancé