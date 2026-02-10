"""
Tests unitaires pour pepper_leds.py - Module de contrôle des LEDs
=================================================================

Tests du contrôleur de LEDs pour exprimer les émotions du robot Pepper.
Utilise des mocks pour simuler le SDK NAOqi.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Ajouter le chemin du module parent pour les imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from robot_control.pepper_leds import PepperLEDs, set_emotion_led


class TestPepperLEDsInit(unittest.TestCase):
    """Tests d'initialisation de PepperLEDs."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_leds_service = Mock()
        self.mock_session.service.return_value = self.mock_leds_service
    
    def test_init_success(self):
        """Test d'initialisation réussie."""
        leds = PepperLEDs(self.mock_session)
        
        self.mock_session.service.assert_called_with("ALLeds")
        self.assertIsNotNone(leds.leds_service)
    
    def test_init_sets_neutral_state(self):
        """Test que l'état initial est neutre."""
        leds = PepperLEDs(self.mock_session)
        
        self.assertEqual(leds._current_emotion, "neutral")
    
    def test_init_failure(self):
        """Test d'initialisation échouée."""
        self.mock_session.service.side_effect = Exception("Service not found")
        
        with self.assertRaises(RuntimeError) as context:
            PepperLEDs(self.mock_session)
        
        self.assertIn("Cannot initialize LED service", str(context.exception))


class TestSetEmotionLED(unittest.TestCase):
    """Tests pour la fonction set_emotion_led."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_leds_service = Mock()
        self.mock_session.service.return_value = self.mock_leds_service
    
    def test_set_emotion_calm(self):
        """Test de l'émotion 'calm' (bleu)."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_emotion_led("calm")
        
        self.assertTrue(result)
        # Vérifie que fadeRGB a été appelé avec la couleur bleue
        calls = self.mock_leds_service.fadeRGB.call_args_list
        # La couleur bleue est 0x0066CC (26316 en décimal)
        self.assertTrue(any(str(0x0066CC) in str(call) for call in calls))
    
    def test_set_emotion_happy(self):
        """Test de l'émotion 'happy' (vert)."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_emotion_led("happy")
        
        self.assertTrue(result)
        self.assertEqual(leds._current_emotion, "happy")
    
    def test_set_emotion_stress(self):
        """Test de l'émotion 'stress' (orange)."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_emotion_led("stress")
        
        self.assertTrue(result)
        self.assertEqual(leds._current_emotion, "stress")
    
    def test_set_emotion_emergency(self):
        """Test de l'émotion 'emergency' (rouge)."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_emotion_led("emergency")
        
        self.assertTrue(result)
        self.assertEqual(leds._current_emotion, "emergency")
        # Vérifie que le clignotement d'urgence est lancé
        self.mock_leds_service.post.rotateEyes.assert_called()
    
    def test_set_emotion_neutral(self):
        """Test de l'émotion 'neutral' (blanc)."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_emotion_led("neutral")
        
        self.assertTrue(result)
        self.assertEqual(leds._current_emotion, "neutral")
    
    def test_set_emotion_case_insensitive(self):
        """Test que l'émotion est insensible à la casse."""
        leds = PepperLEDs(self.mock_session)
        
        result1 = leds.set_emotion_led("CALM")
        result2 = leds.set_emotion_led("Calm")
        result3 = leds.set_emotion_led("calm")
        
        self.assertTrue(result1)
        self.assertTrue(result2)
        self.assertTrue(result3)
    
    def test_set_emotion_with_whitespace(self):
        """Test avec des espaces autour de l'émotion."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_emotion_led("  happy  ")
        
        self.assertTrue(result)
        self.assertEqual(leds._current_emotion, "happy")
    
    def test_set_emotion_unknown(self):
        """Test avec une émotion inconnue (défaut: neutral)."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_emotion_led("unknown_emotion")
        
        self.assertTrue(result)
        self.assertEqual(leds._current_emotion, "neutral")
    
    def test_set_emotion_no_service(self):
        """Test sans service LED."""
        leds = PepperLEDs(self.mock_session)
        leds.leds_service = None
        
        result = leds.set_emotion_led("happy")
        
        self.assertFalse(result)
    
    def test_set_emotion_error_handling(self):
        """Test de la gestion d'erreur."""
        leds = PepperLEDs(self.mock_session)
        self.mock_leds_service.fadeRGB.side_effect = Exception("LED error")
        
        result = leds.set_emotion_led("happy")
        
        self.assertFalse(result)
    
    def test_set_emotion_with_fade(self):
        """Test avec transition en fondu."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_emotion_led("calm", fade=True)
        
        self.assertTrue(result)
        # Vérifie que fadeRGB a été appelé avec une durée > 0
        call_args = self.mock_leds_service.fadeRGB.call_args
        self.assertGreater(call_args[0][2], 0)  # durée > 0
    
    def test_set_emotion_without_fade(self):
        """Test sans transition en fondu."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_emotion_led("calm", fade=False)
        
        self.assertTrue(result)


class TestEmotionColors(unittest.TestCase):
    """Tests pour les couleurs des émotions."""
    
    def test_emotion_colors_defined(self):
        """Vérifie que toutes les couleurs principales sont définies."""
        required_emotions = ["calm", "happy", "stress", "emergency", "neutral"]
        
        for emotion in required_emotions:
            self.assertIn(emotion, PepperLEDs.EMOTION_COLORS)
    
    def test_calm_is_blue(self):
        """Vérifie que 'calm' est bleu."""
        color = PepperLEDs.EMOTION_COLORS["calm"]
        # Bleu a une composante bleue dominante
        blue = color & 0xFF
        green = (color >> 8) & 0xFF
        red = (color >> 16) & 0xFF
        self.assertGreater(blue, red)  # Plus de bleu que de rouge
    
    def test_happy_is_green(self):
        """Vérifie que 'happy' est vert."""
        color = PepperLEDs.EMOTION_COLORS["happy"]
        blue = color & 0xFF
        green = (color >> 8) & 0xFF
        red = (color >> 16) & 0xFF
        self.assertGreater(green, red)  # Plus de vert que de rouge
    
    def test_emergency_is_red(self):
        """Vérifie que 'emergency' est rouge."""
        color = PepperLEDs.EMOTION_COLORS["emergency"]
        blue = color & 0xFF
        green = (color >> 8) & 0xFF
        red = (color >> 16) & 0xFF
        self.assertEqual(red, 255)  # Rouge maximum
        self.assertEqual(green, 0)
        self.assertEqual(blue, 0)


class TestColorConversion(unittest.TestCase):
    """Tests pour la conversion de couleurs."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_leds_service = Mock()
        self.mock_session.service.return_value = self.mock_leds_service
    
    def test_hex_to_rgb_white(self):
        """Test de conversion blanc."""
        leds = PepperLEDs(self.mock_session)
        
        r, g, b = leds._hex_to_rgb(0xFFFFFF)
        
        self.assertAlmostEqual(r, 1.0)
        self.assertAlmostEqual(g, 1.0)
        self.assertAlmostEqual(b, 1.0)
    
    def test_hex_to_rgb_black(self):
        """Test de conversion noir."""
        leds = PepperLEDs(self.mock_session)
        
        r, g, b = leds._hex_to_rgb(0x000000)
        
        self.assertAlmostEqual(r, 0.0)
        self.assertAlmostEqual(g, 0.0)
        self.assertAlmostEqual(b, 0.0)
    
    def test_hex_to_rgb_red(self):
        """Test de conversion rouge."""
        leds = PepperLEDs(self.mock_session)
        
        r, g, b = leds._hex_to_rgb(0xFF0000)
        
        self.assertAlmostEqual(r, 1.0)
        self.assertAlmostEqual(g, 0.0)
        self.assertAlmostEqual(b, 0.0)
    
    def test_hex_to_rgb_green(self):
        """Test de conversion vert."""
        leds = PepperLEDs(self.mock_session)
        
        r, g, b = leds._hex_to_rgb(0x00FF00)
        
        self.assertAlmostEqual(r, 0.0)
        self.assertAlmostEqual(g, 1.0)
        self.assertAlmostEqual(b, 0.0)


class TestSetColorRGB(unittest.TestCase):
    """Tests pour la définition de couleur RGB."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_leds_service = Mock()
        self.mock_session.service.return_value = self.mock_leds_service
    
    def test_set_color_rgb_valid(self):
        """Test avec valeurs RGB valides."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_color_rgb(0.5, 0.3, 0.7)
        
        self.assertTrue(result)
        self.mock_leds_service.fadeRGB.assert_called()
    
    def test_set_color_rgb_clamps_high(self):
        """Test que les valeurs sont bornées (max 1.0)."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_color_rgb(1.5, 2.0, 1.2)
        
        self.assertTrue(result)
    
    def test_set_color_rgb_clamps_low(self):
        """Test que les valeurs sont bornées (min 0.0)."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_color_rgb(-0.5, -0.2, -1.0)
        
        self.assertTrue(result)
    
    def test_set_color_rgb_different_groups(self):
        """Test avec différents groupes de LEDs."""
        leds = PepperLEDs(self.mock_session)
        
        result_eyes = leds.set_color_rgb(1.0, 0.0, 0.0, group="eyes")
        result_chest = leds.set_color_rgb(0.0, 1.0, 0.0, group="chest")
        
        self.assertTrue(result_eyes)
        self.assertTrue(result_chest)
    
    def test_set_color_rgb_no_service(self):
        """Test sans service LED."""
        leds = PepperLEDs(self.mock_session)
        leds.leds_service = None
        
        result = leds.set_color_rgb(1.0, 0.0, 0.0)
        
        self.assertFalse(result)


class TestIntensity(unittest.TestCase):
    """Tests pour le réglage de l'intensité."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_leds_service = Mock()
        self.mock_session.service.return_value = self.mock_leds_service
    
    def test_set_intensity_valid(self):
        """Test avec intensité valide."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_intensity(0.5)
        
        self.assertTrue(result)
        self.mock_leds_service.setIntensity.assert_called()
    
    def test_set_intensity_min(self):
        """Test avec intensité minimale."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_intensity(0.0)
        
        self.assertTrue(result)
    
    def test_set_intensity_max(self):
        """Test avec intensité maximale."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_intensity(1.0)
        
        self.assertTrue(result)
    
    def test_set_intensity_clamped(self):
        """Test que l'intensité est bornée."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.set_intensity(1.5)
        
        self.assertTrue(result)
        # L'intensité devrait être bornée à 1.0
        call_args = self.mock_leds_service.setIntensity.call_args
        self.assertLessEqual(call_args[0][1], 1.0)


class TestBlink(unittest.TestCase):
    """Tests pour le clignotement."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_leds_service = Mock()
        self.mock_session.service.return_value = self.mock_leds_service
    
    @patch('time.sleep')
    def test_blink_success(self, mock_sleep):
        """Test du clignotement réussi."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.blink(times=2)
        
        self.assertTrue(result)
        # fadeRGB doit être appelé plusieurs fois (noir et couleur)
        self.assertGreaterEqual(self.mock_leds_service.fadeRGB.call_count, 4)
    
    @patch('time.sleep')
    def test_blink_with_custom_color(self, mock_sleep):
        """Test du clignotement avec couleur personnalisée."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.blink(color=0xFF0000, times=1)
        
        self.assertTrue(result)
    
    def test_blink_no_service(self):
        """Test du clignotement sans service."""
        leds = PepperLEDs(self.mock_session)
        leds.leds_service = None
        
        result = leds.blink()
        
        self.assertFalse(result)


class TestTurnOff(unittest.TestCase):
    """Tests pour l'extinction des LEDs."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_leds_service = Mock()
        self.mock_session.service.return_value = self.mock_leds_service
    
    def test_turn_off_success(self):
        """Test de l'extinction réussie."""
        leds = PepperLEDs(self.mock_session)
        
        result = leds.turn_off()
        
        self.assertTrue(result)
        # fadeRGB doit être appelé avec noir (0x000000)
        self.mock_leds_service.fadeRGB.assert_called()
    
    def test_turn_off_error(self):
        """Test de l'extinction avec erreur."""
        leds = PepperLEDs(self.mock_session)
        self.mock_leds_service.fadeRGB.side_effect = Exception("Error")
        
        result = leds.turn_off()
        
        self.assertFalse(result)


class TestReset(unittest.TestCase):
    """Tests pour la réinitialisation."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_leds_service = Mock()
        self.mock_session.service.return_value = self.mock_leds_service
    
    def test_reset_success(self):
        """Test de la réinitialisation réussie."""
        leds = PepperLEDs(self.mock_session)
        leds.set_emotion_led("emergency")
        
        result = leds.reset()
        
        self.assertTrue(result)
        self.assertEqual(leds._current_emotion, "neutral")


class TestGetCurrentEmotion(unittest.TestCase):
    """Tests pour obtenir l'émotion actuelle."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_leds_service = Mock()
        self.mock_session.service.return_value = self.mock_leds_service
    
    def test_get_current_emotion_initial(self):
        """Test de l'émotion initiale."""
        leds = PepperLEDs(self.mock_session)
        
        emotion = leds.get_current_emotion()
        
        self.assertEqual(emotion, "neutral")
    
    def test_get_current_emotion_after_change(self):
        """Test après changement d'émotion."""
        leds = PepperLEDs(self.mock_session)
        leds.set_emotion_led("happy")
        
        emotion = leds.get_current_emotion()
        
        self.assertEqual(emotion, "happy")


class TestConvenienceFunction(unittest.TestCase):
    """Tests pour la fonction de commodité."""
    
    def test_set_emotion_led_without_session(self):
        """Test sans session."""
        result = set_emotion_led("happy", session=None)
        
        self.assertFalse(result)
    
    def test_set_emotion_led_with_session(self):
        """Test avec session mock."""
        mock_session = Mock()
        mock_leds_service = Mock()
        mock_session.service.return_value = mock_leds_service
        
        result = set_emotion_led("calm", session=mock_session)
        
        self.assertTrue(result)


class TestLEDGroups(unittest.TestCase):
    """Tests pour les groupes de LEDs."""
    
    def test_led_groups_defined(self):
        """Vérifie que les groupes principaux sont définis."""
        self.assertIn("eyes", PepperLEDs.LED_GROUPS)
        self.assertIn("chest", PepperLEDs.LED_GROUPS)
    
    def test_eyes_maps_to_face_leds(self):
        """Vérifie que 'eyes' correspond à FaceLeds."""
        self.assertEqual(PepperLEDs.LED_GROUPS["eyes"], "FaceLeds")


if __name__ == "__main__":
    unittest.main()
