"""
Tests unitaires pour pepper_tts.py - Module Text-to-Speech
===========================================================

Tests du contrôleur TTS pour le robot Pepper.
Utilise des mocks pour simuler le SDK NAOqi.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Ajouter le chemin du module parent pour les imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from robot_control.pepper_tts import PepperTTS, speak


class TestPepperTTS(unittest.TestCase):
    """Tests pour la classe PepperTTS."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        # Créer un mock de session NAOqi
        self.mock_session = Mock()
        self.mock_tts_service = Mock()
        
        # Configurer le mock pour retourner le service TTS
        self.mock_session.service.return_value = self.mock_tts_service
    
    def test_init_success(self):
        """Test d'initialisation réussie du TTS."""
        tts = PepperTTS(self.mock_session)
        
        self.mock_session.service.assert_called_with("ALTextToSpeech")
        self.assertIsNotNone(tts.tts_service)
        self.assertEqual(tts.language, "French")
    
    def test_init_failure(self):
        """Test d'initialisation échouée (service non disponible)."""
        self.mock_session.service.side_effect = Exception("Service not found")
        
        with self.assertRaises(RuntimeError) as context:
            PepperTTS(self.mock_session)
        
        self.assertIn("Cannot initialize TTS service", str(context.exception))
    
    def test_speak_success(self):
        """Test de la fonction speak avec succès."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.speak("Bonjour, comment allez-vous?")
        
        self.assertTrue(result)
        self.mock_tts_service.say.assert_called_once_with("Bonjour, comment allez-vous?")
    
    def test_speak_empty_text(self):
        """Test de speak avec texte vide."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.speak("")
        
        self.assertFalse(result)
        self.mock_tts_service.say.assert_not_called()
    
    def test_speak_whitespace_only(self):
        """Test de speak avec uniquement des espaces."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.speak("   ")
        
        self.assertFalse(result)
        self.mock_tts_service.say.assert_not_called()
    
    def test_speak_none_text(self):
        """Test de speak avec None."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.speak(None)
        
        self.assertFalse(result)
    
    def test_speak_strips_whitespace(self):
        """Test que speak nettoie les espaces en début/fin."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.speak("  Bonjour  ")
        
        self.assertTrue(result)
        self.mock_tts_service.say.assert_called_once_with("Bonjour")
    
    def test_speak_error_handling(self):
        """Test de la gestion d'erreur lors du speak."""
        tts = PepperTTS(self.mock_session)
        self.mock_tts_service.say.side_effect = Exception("Robot error")
        
        result = tts.speak("Test")
        
        self.assertFalse(result)
    
    def test_speak_async_success(self):
        """Test de speak asynchrone."""
        tts = PepperTTS(self.mock_session)
        self.mock_tts_service.post.say.return_value = 12345
        
        task_id = tts.speak_async("Message asynchrone")
        
        self.assertEqual(task_id, 12345)
        self.mock_tts_service.post.say.assert_called_once_with("Message asynchrone")
    
    def test_speak_async_empty_text(self):
        """Test de speak_async avec texte vide."""
        tts = PepperTTS(self.mock_session)
        
        task_id = tts.speak_async("")
        
        self.assertIsNone(task_id)
    
    def test_stop_speaking(self):
        """Test de l'arrêt de la parole."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.stop_speaking()
        
        self.assertTrue(result)
        self.mock_tts_service.stopAll.assert_called_once()
    
    def test_stop_speaking_error(self):
        """Test de l'arrêt avec erreur."""
        tts = PepperTTS(self.mock_session)
        self.mock_tts_service.stopAll.side_effect = Exception("Error")
        
        result = tts.stop_speaking()
        
        self.assertFalse(result)


class TestSetLanguage(unittest.TestCase):
    """Tests pour le changement de langue."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_tts_service = Mock()
        self.mock_session.service.return_value = self.mock_tts_service
    
    def test_set_language_french(self):
        """Test du changement vers le français."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_language("fr")
        
        self.assertTrue(result)
        self.mock_tts_service.setLanguage.assert_called_with("French")
        self.assertEqual(tts.language, "French")
    
    def test_set_language_english(self):
        """Test du changement vers l'anglais."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_language("en")
        
        self.assertTrue(result)
        self.mock_tts_service.setLanguage.assert_called_with("English")
        self.assertEqual(tts.language, "English")
    
    def test_set_language_unsupported(self):
        """Test avec une langue non supportée."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_language("xyz")
        
        self.assertFalse(result)
    
    def test_set_language_error(self):
        """Test de la gestion d'erreur lors du changement de langue."""
        tts = PepperTTS(self.mock_session)
        self.mock_tts_service.setLanguage.side_effect = Exception("Language error")
        
        result = tts.set_language("en")
        
        self.assertFalse(result)


class TestVoiceSettings(unittest.TestCase):
    """Tests pour les paramètres de voix."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_tts_service = Mock()
        self.mock_session.service.return_value = self.mock_tts_service
    
    def test_set_volume_valid(self):
        """Test du réglage du volume avec valeur valide."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_volume(0.5)
        
        self.assertTrue(result)
        self.mock_tts_service.setParameter.assert_called_with("volume", 0.5)
    
    def test_set_volume_min(self):
        """Test du volume minimum."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_volume(0.0)
        
        self.assertTrue(result)
    
    def test_set_volume_max(self):
        """Test du volume maximum."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_volume(1.0)
        
        self.assertTrue(result)
    
    def test_set_volume_invalid_low(self):
        """Test du volume avec valeur trop basse."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_volume(-0.1)
        
        self.assertFalse(result)
    
    def test_set_volume_invalid_high(self):
        """Test du volume avec valeur trop haute."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_volume(1.5)
        
        self.assertFalse(result)
    
    def test_set_speed_valid(self):
        """Test du réglage de vitesse valide."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_speed(100)
        
        self.assertTrue(result)
        self.mock_tts_service.setParameter.assert_called_with("speed", 100)
    
    def test_set_speed_invalid_low(self):
        """Test de vitesse trop basse."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_speed(30)
        
        self.assertFalse(result)
    
    def test_set_speed_invalid_high(self):
        """Test de vitesse trop haute."""
        tts = PepperTTS(self.mock_session)
        
        result = tts.set_speed(250)
        
        self.assertFalse(result)


class TestConvenienceFunction(unittest.TestCase):
    """Tests pour la fonction de commodité speak()."""
    
    def test_speak_without_session(self):
        """Test de speak() sans session."""
        result = speak("Test", session=None)
        
        self.assertFalse(result)
    
    def test_speak_with_mock_session(self):
        """Test de speak() avec session mock."""
        mock_session = Mock()
        mock_tts_service = Mock()
        mock_session.service.return_value = mock_tts_service
        
        result = speak("Bonjour", session=mock_session)
        
        self.assertTrue(result)
        mock_tts_service.say.assert_called_once_with("Bonjour")


class TestSupportedLanguages(unittest.TestCase):
    """Tests pour la liste des langues supportées."""
    
    def test_supported_languages_exist(self):
        """Vérifie que les langues principales sont supportées."""
        self.assertIn("fr", PepperTTS.SUPPORTED_LANGUAGES)
        self.assertIn("en", PepperTTS.SUPPORTED_LANGUAGES)
        self.assertIn("es", PepperTTS.SUPPORTED_LANGUAGES)
        self.assertIn("de", PepperTTS.SUPPORTED_LANGUAGES)
    
    def test_language_mapping(self):
        """Vérifie le mapping des codes de langue."""
        self.assertEqual(PepperTTS.SUPPORTED_LANGUAGES["fr"], "French")
        self.assertEqual(PepperTTS.SUPPORTED_LANGUAGES["en"], "English")


if __name__ == "__main__":
    unittest.main()
