import sys
from pathlib import Path

root = Path(__file__).resolve().parent
# Ajoute la racine du projet au PYTHONPATH pour que les imports
# comme "emotion_detection.emergency_detector" fonctionnent depuis tests/
sys.path.insert(0, str(root))
# Ajoute emotion_detection/ pour les imports bare comme "from alert_system import ..."
# utilisés en interne par emotion_detector.py
sys.path.insert(0, str(root / "emotion_detection"))
