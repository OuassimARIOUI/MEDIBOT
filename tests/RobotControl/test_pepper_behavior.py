"""
Tests unitaires pour pepper_behavior.py - Module des comportements Choregraphe
==============================================================================

Tests du contrôleur de comportements/animations pour le robot Pepper.
Utilise des mocks pour simuler le SDK NAOqi.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Ajouter le chemin du module parent pour les imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from robot_control.pepper_behavior import PepperBehavior, run_behavior


class TestPepperBehaviorInit(unittest.TestCase):
    """Tests d'initialisation de PepperBehavior."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_behavior_service = Mock()
        self.mock_behavior_service.getInstalledBehaviors.return_value = [
            "animations/Stand/Gestures/Hey_1",
            "animations/Stand/Emotions/Positive/Happy_4",
            "animations/Stand/Emotions/Neutral/Calm_1"
        ]
        self.mock_session.service.return_value = self.mock_behavior_service
    
    def test_init_success(self):
        """Test d'initialisation réussie."""
        behavior = PepperBehavior(self.mock_session)
        
        self.mock_session.service.assert_called_with("ALBehaviorManager")
        self.assertIsNotNone(behavior.behavior_service)
    
    def test_init_caches_installed_behaviors(self):
        """Test que les comportements installés sont mis en cache."""
        behavior = PepperBehavior(self.mock_session)
        
        self.mock_behavior_service.getInstalledBehaviors.assert_called_once()
        self.assertEqual(len(behavior._installed_behaviors), 3)
    
    def test_init_failure(self):
        """Test d'initialisation échouée."""
        self.mock_session.service.side_effect = Exception("Service not found")
        
        with self.assertRaises(RuntimeError) as context:
            PepperBehavior(self.mock_session)
        
        self.assertIn("Cannot initialize behavior service", str(context.exception))


class TestRunBehavior(unittest.TestCase):
    """Tests pour la fonction run_behavior."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_behavior_service = Mock()
        self.mock_behavior_service.getInstalledBehaviors.return_value = [
            "animations/Stand/Gestures/Hey_1",
            "animations/Stand/Emotions/Positive/Happy_4"
        ]
        self.mock_behavior_service.isBehaviorInstalled.return_value = True
        self.mock_session.service.return_value = self.mock_behavior_service
    
    def test_run_behavior_success(self):
        """Test de l'exécution réussie d'un comportement."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.run_behavior("animations/Stand/Gestures/Hey_1")
        
        self.assertTrue(result)
        self.mock_behavior_service.runBehavior.assert_called_once_with(
            "animations/Stand/Gestures/Hey_1"
        )
    
    def test_run_behavior_not_found(self):
        """Test avec un comportement non installé."""
        self.mock_behavior_service.isBehaviorInstalled.return_value = False
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.run_behavior("nonexistent_behavior")
        
        self.assertFalse(result)
        self.mock_behavior_service.runBehavior.assert_not_called()
    
    def test_run_behavior_blocking(self):
        """Test de l'exécution bloquante (wait=True)."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.run_behavior("animations/Stand/Gestures/Hey_1", wait=True)
        
        self.assertTrue(result)
        self.mock_behavior_service.runBehavior.assert_called_once()
    
    def test_run_behavior_non_blocking(self):
        """Test de l'exécution non-bloquante (wait=False)."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.run_behavior("animations/Stand/Gestures/Hey_1", wait=False)
        
        self.assertTrue(result)
        self.mock_behavior_service.post.runBehavior.assert_called_once()
    
    def test_run_behavior_no_service(self):
        """Test sans service behavior."""
        behavior = PepperBehavior(self.mock_session)
        behavior.behavior_service = None
        
        result = behavior.run_behavior("animations/Stand/Gestures/Hey_1")
        
        self.assertFalse(result)
    
    def test_run_behavior_error_handling(self):
        """Test de la gestion d'erreur."""
        behavior = PepperBehavior(self.mock_session)
        self.mock_behavior_service.runBehavior.side_effect = Exception("Error")
        
        result = behavior.run_behavior("animations/Stand/Gestures/Hey_1")
        
        self.assertFalse(result)


class TestBehaviorExists(unittest.TestCase):
    """Tests pour la vérification d'existence de comportement."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_behavior_service = Mock()
        self.mock_behavior_service.getInstalledBehaviors.return_value = []
        self.mock_session.service.return_value = self.mock_behavior_service
    
    def test_behavior_exists_true(self):
        """Test quand le comportement existe."""
        self.mock_behavior_service.isBehaviorInstalled.return_value = True
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.behavior_exists("animations/Stand/Gestures/Hey_1")
        
        self.assertTrue(result)
    
    def test_behavior_exists_false(self):
        """Test quand le comportement n'existe pas."""
        self.mock_behavior_service.isBehaviorInstalled.return_value = False
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.behavior_exists("nonexistent")
        
        self.assertFalse(result)
    
    def test_behavior_exists_no_service(self):
        """Test sans service behavior."""
        behavior = PepperBehavior(self.mock_session)
        behavior.behavior_service = None
        
        result = behavior.behavior_exists("any_behavior")
        
        self.assertFalse(result)


class TestStopBehavior(unittest.TestCase):
    """Tests pour l'arrêt de comportements."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_behavior_service = Mock()
        self.mock_behavior_service.getInstalledBehaviors.return_value = []
        self.mock_session.service.return_value = self.mock_behavior_service
    
    def test_stop_behavior_success(self):
        """Test de l'arrêt réussi d'un comportement."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.stop_behavior("animations/Stand/Gestures/Hey_1")
        
        self.assertTrue(result)
        self.mock_behavior_service.stopBehavior.assert_called_once()
    
    def test_stop_behavior_error(self):
        """Test de l'arrêt avec erreur."""
        behavior = PepperBehavior(self.mock_session)
        self.mock_behavior_service.stopBehavior.side_effect = Exception("Error")
        
        result = behavior.stop_behavior("any_behavior")
        
        self.assertFalse(result)
    
    def test_stop_all_behaviors_success(self):
        """Test de l'arrêt de tous les comportements."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.stop_all_behaviors()
        
        self.assertTrue(result)
        self.mock_behavior_service.stopAllBehaviors.assert_called_once()
    
    def test_stop_all_behaviors_error(self):
        """Test de l'arrêt de tous avec erreur."""
        behavior = PepperBehavior(self.mock_session)
        self.mock_behavior_service.stopAllBehaviors.side_effect = Exception("Error")
        
        result = behavior.stop_all_behaviors()
        
        self.assertFalse(result)
    
    def test_stop_behavior_no_service(self):
        """Test d'arrêt sans service."""
        behavior = PepperBehavior(self.mock_session)
        behavior.behavior_service = None
        
        result = behavior.stop_behavior("any")
        
        self.assertFalse(result)


class TestGetBehaviors(unittest.TestCase):
    """Tests pour obtenir les listes de comportements."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_behavior_service = Mock()
        self.installed = [
            "animations/Stand/Gestures/Hey_1",
            "animations/Stand/Emotions/Positive/Happy_4"
        ]
        self.mock_behavior_service.getInstalledBehaviors.return_value = self.installed
        self.mock_behavior_service.getRunningBehaviors.return_value = ["animations/Stand/Gestures/Hey_1"]
        self.mock_session.service.return_value = self.mock_behavior_service
    
    def test_get_running_behaviors(self):
        """Test pour obtenir les comportements en cours."""
        behavior = PepperBehavior(self.mock_session)
        
        running = behavior.get_running_behaviors()
        
        self.assertEqual(len(running), 1)
        self.assertIn("animations/Stand/Gestures/Hey_1", running)
    
    def test_get_running_behaviors_no_service(self):
        """Test sans service."""
        behavior = PepperBehavior(self.mock_session)
        behavior.behavior_service = None
        
        running = behavior.get_running_behaviors()
        
        self.assertEqual(running, [])
    
    def test_get_installed_behaviors(self):
        """Test pour obtenir les comportements installés."""
        behavior = PepperBehavior(self.mock_session)
        
        installed = behavior.get_installed_behaviors()
        
        self.assertEqual(len(installed), 2)
    
    def test_get_installed_behaviors_returns_copy(self):
        """Test que la liste retournée est une copie."""
        behavior = PepperBehavior(self.mock_session)
        
        installed1 = behavior.get_installed_behaviors()
        installed1.append("new_behavior")
        installed2 = behavior.get_installed_behaviors()
        
        self.assertNotEqual(len(installed1), len(installed2))


class TestRunByCategory(unittest.TestCase):
    """Tests pour l'exécution par catégorie."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_behavior_service = Mock()
        self.mock_behavior_service.getInstalledBehaviors.return_value = [
            "animations/Stand/Gestures/Hey_1",
            "animations/Stand/Emotions/Positive/Happy_4"
        ]
        self.mock_behavior_service.isBehaviorInstalled.return_value = True
        self.mock_session.service.return_value = self.mock_behavior_service
    
    def test_run_by_category_greeting(self):
        """Test de la catégorie greeting."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.run_by_category("greeting")
        
        self.assertTrue(result)
    
    def test_run_by_category_happy(self):
        """Test de la catégorie happy."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.run_by_category("happy")
        
        self.assertTrue(result)
    
    def test_run_by_category_unknown(self):
        """Test avec une catégorie inconnue."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.run_by_category("unknown_category")
        
        self.assertFalse(result)
    
    def test_run_by_category_case_insensitive(self):
        """Test que la catégorie est insensible à la casse."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.run_by_category("GREETING")
        
        self.assertTrue(result)
    
    def test_run_by_category_no_available_behavior(self):
        """Test quand aucun comportement de la catégorie n'est installé."""
        self.mock_behavior_service.isBehaviorInstalled.return_value = False
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.run_by_category("greeting")
        
        self.assertFalse(result)


class TestPlayAnimation(unittest.TestCase):
    """Tests pour jouer des animations par émotion."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_behavior_service = Mock()
        self.mock_behavior_service.getInstalledBehaviors.return_value = []
        self.mock_behavior_service.isBehaviorInstalled.return_value = True
        self.mock_session.service.return_value = self.mock_behavior_service
    
    def test_play_animation_happy(self):
        """Test de l'animation happy."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.play_animation("happy")
        
        self.assertTrue(result)
    
    def test_play_animation_calm(self):
        """Test de l'animation calm."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.play_animation("calm")
        
        self.assertTrue(result)
    
    def test_play_animation_stress(self):
        """Test de l'animation stress (empathy)."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.play_animation("stress")
        
        self.assertTrue(result)
    
    def test_play_animation_unknown_defaults_to_calm(self):
        """Test qu'une émotion inconnue utilise calm."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.play_animation("unknown_emotion")
        
        # Doit utiliser la catégorie calm par défaut
        self.assertTrue(result)


class TestIsBehaviorRunning(unittest.TestCase):
    """Tests pour vérifier si un comportement est en cours."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_behavior_service = Mock()
        self.mock_behavior_service.getInstalledBehaviors.return_value = []
        self.mock_behavior_service.getRunningBehaviors.return_value = [
            "animations/Stand/Gestures/Hey_1"
        ]
        self.mock_session.service.return_value = self.mock_behavior_service
    
    def test_is_behavior_running_specific_true(self):
        """Test si un comportement spécifique est en cours."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.is_behavior_running("animations/Stand/Gestures/Hey_1")
        
        self.assertTrue(result)
    
    def test_is_behavior_running_specific_false(self):
        """Test si un comportement spécifique n'est pas en cours."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.is_behavior_running("other_behavior")
        
        self.assertFalse(result)
    
    def test_is_any_behavior_running_true(self):
        """Test si un quelconque comportement est en cours."""
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.is_behavior_running()  # Sans nom = any
        
        self.assertTrue(result)
    
    def test_is_any_behavior_running_false(self):
        """Test quand aucun comportement n'est en cours."""
        self.mock_behavior_service.getRunningBehaviors.return_value = []
        behavior = PepperBehavior(self.mock_session)
        
        result = behavior.is_behavior_running()
        
        self.assertFalse(result)


class TestConvenienceFunction(unittest.TestCase):
    """Tests pour la fonction de commodité run_behavior."""
    
    def test_run_behavior_without_session(self):
        """Test sans session."""
        result = run_behavior("any_behavior", session=None)
        
        self.assertFalse(result)
    
    def test_run_behavior_with_session(self):
        """Test avec session mock."""
        mock_session = Mock()
        mock_behavior_service = Mock()
        mock_behavior_service.getInstalledBehaviors.return_value = []
        mock_behavior_service.isBehaviorInstalled.return_value = True
        mock_session.service.return_value = mock_behavior_service
        
        result = run_behavior("animations/Stand/Gestures/Hey_1", session=mock_session)
        
        self.assertTrue(result)


class TestBehaviorCategories(unittest.TestCase):
    """Tests pour les catégories de comportements."""
    
    def test_categories_defined(self):
        """Vérifie que les catégories principales sont définies."""
        required = ["greeting", "happy", "calm", "empathy", "thinking"]
        
        for category in required:
            self.assertIn(category, PepperBehavior.BEHAVIOR_CATEGORIES)
    
    def test_categories_have_behaviors(self):
        """Vérifie que chaque catégorie a des comportements."""
        for category, behaviors in PepperBehavior.BEHAVIOR_CATEGORIES.items():
            self.assertIsInstance(behaviors, list)
            self.assertGreater(len(behaviors), 0, f"Category {category} is empty")
    
    def test_greeting_behaviors_contain_hey(self):
        """Vérifie que greeting contient des comportements Hey."""
        greetings = PepperBehavior.BEHAVIOR_CATEGORIES["greeting"]
        self.assertTrue(any("Hey" in b for b in greetings))


if __name__ == "__main__":
    unittest.main()
