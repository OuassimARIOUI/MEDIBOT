"""
Tests unitaires pour pepper_main.py - Module d'orchestration principal
======================================================================

Tests du contrôleur principal qui coordonne tous les sous-systèmes du robot Pepper.
Utilise des mocks pour simuler le SDK NAOqi et les sous-systèmes.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import sys
import os
from pathlib import Path
from queue import Queue
import threading
import time

# Ajouter le chemin du module parent pour les imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestPepperControllerInit(unittest.TestCase):
    """Tests d'initialisation de PepperController."""
    
    def test_init_default_values(self):
        """Test des valeurs par défaut."""
        with patch.dict(os.environ, {}, clear=True):
            from robot_control.pepper_main import PepperController
            
            controller = PepperController()
            
            self.assertEqual(controller.ip, "127.0.0.1")
            self.assertEqual(controller.port, 9559)
    
    def test_init_with_env_vars(self):
        """Test avec variables d'environnement."""
        with patch.dict(os.environ, {"PEPPER_IP": "192.168.1.100", "PEPPER_PORT": "9560"}):
            from robot_control.pepper_main import PepperController
            
            controller = PepperController()
            
            self.assertEqual(controller.ip, "192.168.1.100")
            self.assertEqual(controller.port, 9560)
    
    def test_init_with_explicit_params(self):
        """Test avec paramètres explicites."""
        from robot_control.pepper_main import PepperController
        
        controller = PepperController(ip="10.0.0.1", port=1234)
        
        self.assertEqual(controller.ip, "10.0.0.1")
        self.assertEqual(controller.port, 1234)
    
    def test_init_subsystems_none(self):
        """Test que les sous-systèmes sont None à l'init."""
        from robot_control.pepper_main import PepperController
        
        controller = PepperController()
        
        self.assertIsNone(controller.session)
        self.assertIsNone(controller.tts)
        self.assertIsNone(controller.motion)
        self.assertIsNone(controller.leds)
        self.assertIsNone(controller.behavior)
        self.assertIsNone(controller.camera)


class TestPepperControllerConnect(unittest.TestCase):
    """Tests pour la connexion au robot."""
    
    @patch('robot_control.pepper_main.PepperTTS')
    @patch('robot_control.pepper_main.PepperMotion')
    @patch('robot_control.pepper_main.PepperLEDs')
    @patch('robot_control.pepper_main.PepperBehavior')
    @patch('robot_control.pepper_main.PepperCamera')
    def test_connect_success(self, mock_camera, mock_behavior, mock_leds, 
                             mock_motion, mock_tts):
        """Test de connexion réussie."""
        # Mock du module qi
        mock_qi = MagicMock()
        mock_session = MagicMock()
        mock_qi.Session.return_value = mock_session
        
        with patch.dict(sys.modules, {'qi': mock_qi}):
            from robot_control.pepper_main import PepperController
            
            controller = PepperController()
            result = controller.connect()
            
            self.assertTrue(result)
            mock_session.connect.assert_called_once()
            self.assertIsNotNone(controller.session)
    
    def test_connect_no_qi_module(self):
        """Test de connexion sans module qi."""
        # Supprimer qi des modules si présent
        with patch.dict(sys.modules, {'qi': None}):
            from robot_control.pepper_main import PepperController
            
            controller = PepperController()
            
            # Forcer ImportError
            with patch('builtins.__import__', side_effect=ImportError("No module qi")):
                result = controller.connect()
                
                self.assertFalse(result)
    
    @patch('robot_control.pepper_main.PepperTTS')
    @patch('robot_control.pepper_main.PepperMotion')
    @patch('robot_control.pepper_main.PepperLEDs')
    @patch('robot_control.pepper_main.PepperBehavior')
    @patch('robot_control.pepper_main.PepperCamera')
    def test_connect_initializes_subsystems(self, mock_camera, mock_behavior, 
                                            mock_leds, mock_motion, mock_tts):
        """Test que la connexion initialise les sous-systèmes."""
        mock_qi = MagicMock()
        mock_session = MagicMock()
        mock_qi.Session.return_value = mock_session
        
        with patch.dict(sys.modules, {'qi': mock_qi}):
            from robot_control.pepper_main import PepperController
            
            controller = PepperController()
            controller.connect()
            
            mock_tts.assert_called_once()
            mock_motion.assert_called_once()
            mock_leds.assert_called_once()
            mock_behavior.assert_called_once()
            mock_camera.assert_called_once()


class TestPepperControllerDisconnect(unittest.TestCase):
    """Tests pour la déconnexion du robot."""
    
    def test_disconnect_resets_session(self):
        """Test que disconnect réinitialise la session."""
        from robot_control.pepper_main import PepperController
        
        controller = PepperController()
        controller.session = Mock()
        controller.leds = Mock()
        controller.camera = Mock()
        
        controller.disconnect()
        
        self.assertIsNone(controller.session)
    
    def test_disconnect_releases_camera(self):
        """Test que disconnect libère la caméra."""
        from robot_control.pepper_main import PepperController
        
        controller = PepperController()
        mock_camera = Mock()
        controller.camera = mock_camera
        controller.session = Mock()
        
        controller.disconnect()
        
        mock_camera.release.assert_called_once()
    
    def test_disconnect_resets_leds(self):
        """Test que disconnect réinitialise les LEDs."""
        from robot_control.pepper_main import PepperController
        
        controller = PepperController()
        mock_leds = Mock()
        controller.leds = mock_leds
        controller.session = Mock()
        
        controller.disconnect()
        
        mock_leds.reset.assert_called_once()


class TestIsConnected(unittest.TestCase):
    """Tests pour vérifier l'état de connexion."""
    
    def test_is_connected_false_initially(self):
        """Test que le statut est faux initialement."""
        from robot_control.pepper_main import PepperController
        
        controller = PepperController()
        
        self.assertFalse(controller.is_connected())
    
    def test_is_connected_true_with_session(self):
        """Test avec session active."""
        from robot_control.pepper_main import PepperController
        
        controller = PepperController()
        controller.session = Mock()
        
        self.assertTrue(controller.is_connected())


class TestExecuteCommand(unittest.TestCase):
    """Tests pour l'exécution de commandes."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        from robot_control.pepper_main import PepperController
        
        self.controller = PepperController()
        self.controller.session = Mock()
        self.controller.tts = Mock()
        self.controller.motion = Mock()
        self.controller.leds = Mock()
        self.controller.behavior = Mock()
        
        # Configure les mocks pour retourner True par défaut
        self.controller.tts.speak.return_value = True
        self.controller.leds.set_emotion_led.return_value = True
        self.controller.motion.nod_head.return_value = True
        self.controller.behavior.run_behavior.return_value = True
    
    def test_execute_command_not_connected(self):
        """Test sans connexion."""
        from robot_control.pepper_main import PepperController
        
        controller = PepperController()
        
        result = controller.execute_command({"text": "Test"})
        
        self.assertFalse(result)
    
    def test_execute_command_with_text(self):
        """Test avec texte à parler."""
        result = self.controller.execute_command({"text": "Bonjour!"})
        
        self.assertTrue(result)
        self.controller.tts.speak.assert_called_once_with("Bonjour!")
    
    def test_execute_command_with_emotion(self):
        """Test avec émotion."""
        result = self.controller.execute_command({"emotion": "happy"})
        
        self.assertTrue(result)
        self.controller.leds.set_emotion_led.assert_called_once_with("happy")
    
    def test_execute_command_with_gesture_nod(self):
        """Test avec geste de hochement."""
        result = self.controller.execute_command({"gesture": "nod"})
        
        self.assertTrue(result)
        self.controller.motion.nod_head.assert_called_once()
    
    def test_execute_command_with_gesture_shake(self):
        """Test avec geste de secouement."""
        result = self.controller.execute_command({"gesture": "shake"})
        
        self.assertTrue(result)
        self.controller.motion.shake_head.assert_called_once()
    
    def test_execute_command_with_behavior(self):
        """Test avec comportement Choregraphe."""
        result = self.controller.execute_command({
            "behavior": "animations/Stand/Gestures/Hey_1"
        })
        
        self.assertTrue(result)
        self.controller.behavior.run_behavior.assert_called_once()
    
    def test_execute_command_combined(self):
        """Test avec plusieurs actions combinées."""
        result = self.controller.execute_command({
            "text": "Je suis content!",
            "emotion": "happy",
            "gesture": "nod"
        })
        
        self.assertTrue(result)
        self.controller.tts.speak.assert_called_once()
        self.controller.leds.set_emotion_led.assert_called_once()
        self.controller.motion.nod_head.assert_called_once()
    
    def test_execute_command_async(self):
        """Test en mode asynchrone (wait=False)."""
        result = self.controller.execute_command({
            "text": "Message asynchrone",
            "wait": False
        })
        
        self.assertTrue(result)
        self.controller.tts.speak_async.assert_called_once()
    
    def test_execute_command_error_handling(self):
        """Test de gestion d'erreur."""
        self.controller.tts.speak.side_effect = Exception("TTS Error")
        
        result = self.controller.execute_command({"text": "Test"})
        
        self.assertFalse(result)


class TestExecuteGesture(unittest.TestCase):
    """Tests pour l'exécution de gestes."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        from robot_control.pepper_main import PepperController
        
        self.controller = PepperController()
        self.controller.session = Mock()
        self.controller.motion = Mock()
        self.controller.motion.nod_head.return_value = True
        self.controller.motion.shake_head.return_value = True
        self.controller.motion.wave_hand.return_value = True
        self.controller.motion.look_at_direction.return_value = True
        self.controller.motion.idle_motion.return_value = True
        self.controller.motion.reset_posture.return_value = True
    
    def test_gesture_nod(self):
        """Test du geste nod."""
        result = self.controller._execute_gesture("nod")
        
        self.assertTrue(result)
        self.controller.motion.nod_head.assert_called_once()
    
    def test_gesture_shake(self):
        """Test du geste shake."""
        result = self.controller._execute_gesture("shake")
        
        self.assertTrue(result)
        self.controller.motion.shake_head.assert_called_once()
    
    def test_gesture_wave(self):
        """Test du geste wave."""
        result = self.controller._execute_gesture("wave")
        
        self.assertTrue(result)
        self.controller.motion.wave_hand.assert_called_once()
    
    def test_gesture_look_left(self):
        """Test du regard à gauche."""
        result = self.controller._execute_gesture("look_left")
        
        self.assertTrue(result)
        self.controller.motion.look_at_direction.assert_called_once_with("left")
    
    def test_gesture_look_right(self):
        """Test du regard à droite."""
        result = self.controller._execute_gesture("look_right")
        
        self.assertTrue(result)
        self.controller.motion.look_at_direction.assert_called_once_with("right")
    
    def test_gesture_idle(self):
        """Test du mouvement idle."""
        result = self.controller._execute_gesture("idle")
        
        self.assertTrue(result)
        self.controller.motion.idle_motion.assert_called_once()
    
    def test_gesture_reset(self):
        """Test de la réinitialisation."""
        result = self.controller._execute_gesture("reset")
        
        self.assertTrue(result)
        self.controller.motion.reset_posture.assert_called_once()
    
    def test_gesture_unknown(self):
        """Test d'un geste inconnu."""
        result = self.controller._execute_gesture("unknown_gesture")
        
        self.assertFalse(result)
    
    def test_gesture_case_insensitive(self):
        """Test insensibilité à la casse."""
        result = self.controller._execute_gesture("NOD")
        
        self.assertTrue(result)


class TestConvenienceMethods(unittest.TestCase):
    """Tests pour les méthodes de commodité."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        from robot_control.pepper_main import PepperController
        
        self.controller = PepperController()
        self.controller.session = Mock()
        self.controller.tts = Mock()
        self.controller.motion = Mock()
        self.controller.leds = Mock()
        
        self.controller.tts.speak.return_value = True
        self.controller.leds.set_emotion_led.return_value = True
        self.controller.motion.nod_head.return_value = True
    
    def test_speak(self):
        """Test de la méthode speak."""
        result = self.controller.speak("Bonjour!", emotion="happy")
        
        self.assertTrue(result)
        self.controller.tts.speak.assert_called_once()
    
    def test_react(self):
        """Test de la méthode react."""
        result = self.controller.react("happy", text="Super!")
        
        self.assertTrue(result)
        self.controller.leds.set_emotion_led.assert_called()
    
    def test_greet_with_name(self):
        """Test de greet avec nom."""
        result = self.controller.greet("Jean")
        
        self.assertTrue(result)
        # Vérifie que le nom est dans le texte
        call_args = self.controller.tts.speak.call_args
        self.assertIn("Jean", str(call_args))
    
    def test_greet_without_name(self):
        """Test de greet sans nom."""
        result = self.controller.greet()
        
        self.assertTrue(result)


class TestCommandQueue(unittest.TestCase):
    """Tests pour la file de commandes asynchrone."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        from robot_control.pepper_main import PepperController
        
        self.controller = PepperController()
        self.controller.session = Mock()
        self.controller.tts = Mock()
        self.controller.tts.speak.return_value = True
    
    def test_queue_command(self):
        """Test de mise en file d'une commande."""
        command = {"text": "Test"}
        
        self.controller.queue_command(command)
        
        self.assertFalse(self.controller._command_queue.empty())
    
    def test_start_creates_thread(self):
        """Test que start crée un thread."""
        self.controller.start()
        
        self.assertTrue(self.controller._running)
        self.assertIsNotNone(self.controller._loop_thread)
        
        # Nettoyage
        self.controller.stop()
    
    def test_stop_terminates_thread(self):
        """Test que stop termine le thread."""
        self.controller.start()
        time.sleep(0.1)  # Laisser le thread démarrer
        
        self.controller.stop()
        
        self.assertFalse(self.controller._running)
    
    def test_start_without_connection(self):
        """Test de start sans connexion."""
        from robot_control.pepper_main import PepperController
        
        controller = PepperController()  # Pas connecté
        
        controller.start()
        
        # Ne devrait pas créer de thread
        self.assertFalse(controller._running)


class TestCallbacks(unittest.TestCase):
    """Tests pour les callbacks."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        from robot_control.pepper_main import PepperController
        
        self.controller = PepperController()
        self.controller.session = Mock()
        self.controller.tts = Mock()
        self.controller.tts.speak.return_value = True
    
    def test_set_on_command_complete(self):
        """Test de définition du callback de complétion."""
        callback = Mock()
        
        self.controller.set_on_command_complete(callback)
        self.controller.execute_command({"text": "Test"})
        
        callback.assert_called_once()
    
    def test_set_on_error(self):
        """Test de définition du callback d'erreur."""
        callback = Mock()
        self.controller.tts.speak.side_effect = Exception("Error")
        
        self.controller.set_on_error(callback)
        self.controller.execute_command({"text": "Test"})
        
        callback.assert_called_once()


class TestContextManager(unittest.TestCase):
    """Tests pour le gestionnaire de contexte."""
    
    @patch('robot_control.pepper_main.PepperTTS')
    @patch('robot_control.pepper_main.PepperMotion')
    @patch('robot_control.pepper_main.PepperLEDs')
    @patch('robot_control.pepper_main.PepperBehavior')
    @patch('robot_control.pepper_main.PepperCamera')
    def test_context_manager_connects(self, mock_camera, mock_behavior, 
                                      mock_leds, mock_motion, mock_tts):
        """Test que le context manager se connecte."""
        mock_qi = MagicMock()
        mock_session = MagicMock()
        mock_qi.Session.return_value = mock_session
        
        with patch.dict(sys.modules, {'qi': mock_qi}):
            from robot_control.pepper_main import PepperController
            
            with PepperController() as controller:
                self.assertIsNotNone(controller.session)
    
    def test_context_manager_disconnects(self):
        """Test que le context manager se déconnecte."""
        from robot_control.pepper_main import PepperController
        
        controller = PepperController()
        controller.session = Mock()
        controller.camera = Mock()
        controller.leds = Mock()
        
        controller.__enter__()
        controller.__exit__(None, None, None)
        
        self.assertIsNone(controller.session)


class TestConvenienceFunctions(unittest.TestCase):
    """Tests pour les fonctions de commodité globales."""
    
    def test_create_controller(self):
        """Test de création de contrôleur."""
        from robot_control.pepper_main import create_controller
        
        # Sans qi module, la connexion échouera mais l'objet sera créé
        controller = create_controller()
        
        self.assertIsNotNone(controller)


class TestGestureMap(unittest.TestCase):
    """Tests pour le mapping des gestes."""
    
    def test_gesture_map_contains_basics(self):
        """Test que les gestes de base sont définis."""
        from robot_control.pepper_main import PepperController
        
        required_gestures = ["nod", "shake", "wave", "idle", "reset"]
        
        for gesture in required_gestures:
            self.assertIn(gesture, PepperController.GESTURE_MAP)
    
    def test_gesture_map_contains_look_directions(self):
        """Test que les directions de regard sont définies."""
        from robot_control.pepper_main import PepperController
        
        look_gestures = ["look_left", "look_right", "look_up", "look_down"]
        
        for gesture in look_gestures:
            self.assertIn(gesture, PepperController.GESTURE_MAP)


if __name__ == "__main__":
    unittest.main()
