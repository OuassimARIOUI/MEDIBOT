"""
Tests unitaires pour pepper_motion.py - Module de mouvements et gestes
======================================================================

Tests du contrôleur de mouvements pour le robot Pepper.
Utilise des mocks pour simuler le SDK NAOqi.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Ajouter le chemin du module parent pour les imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from robot_control.pepper_motion import PepperMotion, nod_head, shake_head, idle_motion


class TestPepperMotionInit(unittest.TestCase):
    """Tests d'initialisation de PepperMotion."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_motion_service = Mock()
        self.mock_motion_service.robotIsWakeUp.return_value = True
        self.mock_session.service.return_value = self.mock_motion_service
    
    def test_init_success(self):
        """Test d'initialisation réussie."""
        motion = PepperMotion(self.mock_session)
        
        # Utilise assert_any_call car plusieurs services sont appelés lors de l'init
        self.mock_session.service.assert_any_call("ALMotion")
        self.assertIsNotNone(motion.motion_service)
    
    def test_init_failure(self):
        """Test d'initialisation échouée."""
        self.mock_session.service.side_effect = Exception("Service not found")
        
        with self.assertRaises(RuntimeError) as context:
            PepperMotion(self.mock_session)
        
        self.assertIn("Cannot initialize motion service", str(context.exception))
    
    def test_init_wakes_up_robot(self):
        """Test que le robot est réveillé s'il dort."""
        self.mock_motion_service.robotIsWakeUp.return_value = False
        
        motion = PepperMotion(self.mock_session)
        
        self.mock_motion_service.wakeUp.assert_called_once()
    
    def test_init_sets_head_stiffness(self):
        """Test que la rigidité de la tête est configurée."""
        motion = PepperMotion(self.mock_session)
        
        self.mock_motion_service.setStiffnesses.assert_called_with("Head", 1.0)


class TestNodHead(unittest.TestCase):
    """Tests pour le mouvement de hochement de tête."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_motion_service = Mock()
        self.mock_motion_service.robotIsWakeUp.return_value = True
        self.mock_motion_service.getAngles.return_value = [0.0]
        self.mock_session.service.return_value = self.mock_motion_service
    
    def test_nod_head_success(self):
        """Test du hochement de tête réussi."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.nod_head()
        
        self.assertTrue(result)
        # Vérifie que setAngles a été appelé (pour le mouvement)
        self.assertTrue(self.mock_motion_service.setAngles.called)
    
    def test_nod_head_multiple_times(self):
        """Test du hochement de tête multiple fois."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.nod_head(times=3)
        
        self.assertTrue(result)
        # Doit appeler setAngles plusieurs fois (2 appels par nod + 1 reset)
        self.assertGreaterEqual(self.mock_motion_service.setAngles.call_count, 6)
    
    def test_nod_head_custom_speed(self):
        """Test du hochement avec vitesse personnalisée."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.nod_head(times=1, speed=0.3)
        
        self.assertTrue(result)
    
    def test_nod_head_no_service(self):
        """Test du hochement sans service motion."""
        motion = PepperMotion(self.mock_session)
        motion.motion_service = None
        
        result = motion.nod_head()
        
        self.assertFalse(result)
    
    def test_nod_head_error_handling(self):
        """Test de la gestion d'erreur lors du hochement."""
        motion = PepperMotion(self.mock_session)
        self.mock_motion_service.setAngles.side_effect = Exception("Motor error")
        
        result = motion.nod_head()
        
        self.assertFalse(result)


class TestShakeHead(unittest.TestCase):
    """Tests pour le mouvement de secouement de tête."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_motion_service = Mock()
        self.mock_motion_service.robotIsWakeUp.return_value = True
        self.mock_motion_service.getAngles.return_value = [0.0]
        self.mock_session.service.return_value = self.mock_motion_service
    
    def test_shake_head_success(self):
        """Test du secouement de tête réussi."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.shake_head()
        
        self.assertTrue(result)
        self.assertTrue(self.mock_motion_service.setAngles.called)
    
    def test_shake_head_multiple_times(self):
        """Test du secouement multiple fois."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.shake_head(times=4)
        
        self.assertTrue(result)
    
    def test_shake_head_no_service(self):
        """Test du secouement sans service motion."""
        motion = PepperMotion(self.mock_session)
        motion.motion_service = None
        
        result = motion.shake_head()
        
        self.assertFalse(result)
    
    def test_shake_head_error_handling(self):
        """Test de la gestion d'erreur lors du secouement."""
        motion = PepperMotion(self.mock_session)
        self.mock_motion_service.setAngles.side_effect = Exception("Motor error")
        
        result = motion.shake_head()
        
        self.assertFalse(result)


class TestLookAtDirection(unittest.TestCase):
    """Tests pour les mouvements directionnels de la tête."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_motion_service = Mock()
        self.mock_motion_service.robotIsWakeUp.return_value = True
        self.mock_session.service.return_value = self.mock_motion_service
    
    def test_look_left(self):
        """Test du regard vers la gauche."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.look_at_direction("left")
        
        self.assertTrue(result)
        # Vérifie que HeadYaw a été modifié
        calls = self.mock_motion_service.setAngles.call_args_list
        self.assertTrue(any("HeadYaw" in str(call) for call in calls))
    
    def test_look_right(self):
        """Test du regard vers la droite."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.look_at_direction("right")
        
        self.assertTrue(result)
    
    def test_look_up(self):
        """Test du regard vers le haut."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.look_at_direction("up")
        
        self.assertTrue(result)
    
    def test_look_down(self):
        """Test du regard vers le bas."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.look_at_direction("down")
        
        self.assertTrue(result)
    
    def test_look_center(self):
        """Test du regard vers le centre."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.look_at_direction("center")
        
        self.assertTrue(result)
    
    def test_look_invalid_direction(self):
        """Test avec une direction invalide."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.look_at_direction("diagonal")
        
        self.assertFalse(result)
    
    def test_look_case_insensitive(self):
        """Test que la direction est insensible à la casse."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.look_at_direction("LEFT")
        
        self.assertTrue(result)


class TestIdleMotion(unittest.TestCase):
    """Tests pour le mouvement idle."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_motion_service = Mock()
        self.mock_motion_service.robotIsWakeUp.return_value = True
        self.mock_session.service.return_value = self.mock_motion_service
    
    @patch('time.time')
    @patch('time.sleep')
    def test_idle_motion_success(self, mock_sleep, mock_time):
        """Test du mouvement idle réussi."""
        # Simuler le passage du temps
        mock_time.side_effect = [0, 1, 2, 3, 4, 5, 6]
        
        motion = PepperMotion(self.mock_session)
        
        result = motion.idle_motion(duration=2.0)
        
        self.assertTrue(result)
    
    def test_idle_motion_no_service(self):
        """Test du mouvement idle sans service."""
        motion = PepperMotion(self.mock_session)
        motion.motion_service = None
        
        result = motion.idle_motion()
        
        self.assertFalse(result)


class TestResetPosture(unittest.TestCase):
    """Tests pour la réinitialisation de la posture."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_motion_service = Mock()
        self.mock_motion_service.robotIsWakeUp.return_value = True
        self.mock_session.service.return_value = self.mock_motion_service
    
    def test_reset_posture_success(self):
        """Test de la réinitialisation réussie."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.reset_posture()
        
        self.assertTrue(result)
        # Vérifie que les angles sont réinitialisés à 0
        calls = self.mock_motion_service.setAngles.call_args_list
        self.assertTrue(any(call[0][1] == 0.0 for call in calls))
    
    def test_reset_posture_error(self):
        """Test de la réinitialisation avec erreur."""
        motion = PepperMotion(self.mock_session)
        self.mock_motion_service.setAngles.side_effect = Exception("Error")
        
        result = motion.reset_posture()
        
        self.assertFalse(result)


class TestWaveHand(unittest.TestCase):
    """Tests pour le geste de salutation."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_motion_service = Mock()
        self.mock_motion_service.robotIsWakeUp.return_value = True
        self.mock_motion_service.getAngles.return_value = [0.0]
        self.mock_session.service.return_value = self.mock_motion_service
    
    def test_wave_hand_right(self):
        """Test du salut avec la main droite."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.wave_hand("right")
        
        self.assertTrue(result)
    
    def test_wave_hand_left(self):
        """Test du salut avec la main gauche."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.wave_hand("left")
        
        self.assertTrue(result)
    
    def test_wave_hand_no_service(self):
        """Test du salut sans service motion."""
        motion = PepperMotion(self.mock_session)
        motion.motion_service = None
        
        result = motion.wave_hand()
        
        self.assertFalse(result)


class TestBreathing(unittest.TestCase):
    """Tests pour l'animation de respiration."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_motion_service = Mock()
        self.mock_motion_service.robotIsWakeUp.return_value = True
        self.mock_session.service.return_value = self.mock_motion_service
    
    def test_enable_breathing(self):
        """Test de l'activation de la respiration."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.set_breathing(True)
        
        self.assertTrue(result)
        self.mock_motion_service.setBreathEnabled.assert_called_with("Body", True)
    
    def test_disable_breathing(self):
        """Test de la désactivation de la respiration."""
        motion = PepperMotion(self.mock_session)
        
        result = motion.set_breathing(False)
        
        self.assertTrue(result)
        self.mock_motion_service.setBreathEnabled.assert_called_with("Body", False)
    
    def test_set_breathing_error(self):
        """Test de la gestion d'erreur pour la respiration."""
        motion = PepperMotion(self.mock_session)
        self.mock_motion_service.setBreathEnabled.side_effect = Exception("Error")
        
        result = motion.set_breathing(True)
        
        self.assertFalse(result)


class TestConvenienceFunctions(unittest.TestCase):
    """Tests pour les fonctions de commodité."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_motion_service = Mock()
        self.mock_motion_service.robotIsWakeUp.return_value = True
        self.mock_motion_service.getAngles.return_value = [0.0]
        self.mock_session.service.return_value = self.mock_motion_service
    
    def test_nod_head_function(self):
        """Test de la fonction nod_head()."""
        result = nod_head(self.mock_session, times=2)
        self.assertTrue(result)
    
    def test_shake_head_function(self):
        """Test de la fonction shake_head()."""
        result = shake_head(self.mock_session, times=2)
        self.assertTrue(result)
    
    @patch('time.time')
    @patch('time.sleep')
    def test_idle_motion_function(self, mock_sleep, mock_time):
        """Test de la fonction idle_motion()."""
        mock_time.side_effect = [0, 1, 2, 3, 4, 5, 6]
        
        result = idle_motion(self.mock_session, duration=2.0)
        self.assertTrue(result)


class TestSpeedConstants(unittest.TestCase):
    """Tests pour les constantes de vitesse."""
    
    def test_smooth_speed_is_slowest(self):
        """Vérifie que SMOOTH_SPEED est la plus lente."""
        self.assertLess(PepperMotion.SMOOTH_SPEED, PepperMotion.NORMAL_SPEED)
        self.assertLess(PepperMotion.NORMAL_SPEED, PepperMotion.FAST_SPEED)
    
    def test_speeds_are_positive(self):
        """Vérifie que les vitesses sont positives."""
        self.assertGreater(PepperMotion.SMOOTH_SPEED, 0)
        self.assertGreater(PepperMotion.NORMAL_SPEED, 0)
        self.assertGreater(PepperMotion.FAST_SPEED, 0)


if __name__ == "__main__":
    unittest.main()
