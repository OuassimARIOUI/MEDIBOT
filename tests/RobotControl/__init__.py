"""
Tests RobotControl - Tests unitaires pour le module robot_control
=================================================================

Ce package contient tous les tests unitaires pour les modules de contrôle
du robot Pepper dans le projet MediBot.

Modules testés:
    - test_pepper_tts.py      : Tests TTS (Text-to-Speech)
    - test_pepper_motion.py   : Tests mouvements et gestes
    - test_pepper_leds.py     : Tests LEDs émotionnelles
    - test_pepper_behavior.py : Tests comportements Choregraphe
    - test_pepper_camera.py   : Tests accès caméra
    - test_pepper_main.py     : Tests orchestration principale

Exécution des tests:
    # Tous les tests RobotControl
    python -m pytest tests/RobotControl/ -v
    
    # Un fichier spécifique
    python -m pytest tests/RobotControl/test_pepper_tts.py -v
    
    # Avec couverture
    python -m pytest tests/RobotControl/ --cov=robot_control --cov-report=html

Notes:
    - Tous les tests utilisent des mocks pour simuler NAOqi
    - Aucune connexion réelle au robot n'est nécessaire
    - Les tests vérifient la logique, pas l'intégration hardware

Author: MediBot Team
"""

import sys
from pathlib import Path

# Ajouter le chemin du projet pour les imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
