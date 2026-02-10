"""
Tests unitaires pour pepper_camera.py - Module d'accès caméra
=============================================================

Tests du contrôleur de caméra pour le robot Pepper.
Utilise des mocks pour simuler le SDK NAOqi.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Ajouter le chemin du module parent pour les imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from robot_control.pepper_camera import PepperCamera, get_frame


class TestPepperCameraInit(unittest.TestCase):
    """Tests d'initialisation de PepperCamera."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_session.service.return_value = self.mock_video_service
    
    def test_init_success(self):
        """Test d'initialisation réussie."""
        camera = PepperCamera(self.mock_session)
        
        self.mock_session.service.assert_called_with("ALVideoDevice")
        self.assertIsNotNone(camera.video_service)
    
    def test_init_default_settings(self):
        """Test des paramètres par défaut."""
        camera = PepperCamera(self.mock_session)
        
        self.assertEqual(camera._camera_id, PepperCamera.CAMERA_TOP)
        self.assertEqual(camera._resolution, PepperCamera.RESOLUTION_VGA)
        self.assertEqual(camera._colorspace, PepperCamera.COLORSPACE_BGR)
        self.assertEqual(camera._fps, 10)
    
    def test_init_failure(self):
        """Test d'initialisation échouée."""
        self.mock_session.service.side_effect = Exception("Service not found")
        
        with self.assertRaises(RuntimeError) as context:
            PepperCamera(self.mock_session)
        
        self.assertIn("Cannot initialize camera service", str(context.exception))
    
    def test_init_no_subscriber(self):
        """Test que pas d'abonnement à l'init."""
        camera = PepperCamera(self.mock_session)
        
        self.assertIsNone(camera._subscriber_id)


class TestSubscribe(unittest.TestCase):
    """Tests pour l'abonnement à la caméra."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_video_service.subscribeCamera.return_value = "subscriber_123"
        self.mock_session.service.return_value = self.mock_video_service
    
    def test_subscribe_success(self):
        """Test d'abonnement réussi."""
        camera = PepperCamera(self.mock_session)
        
        result = camera.subscribe("TestApp")
        
        self.assertTrue(result)
        self.assertEqual(camera._subscriber_id, "subscriber_123")
        self.mock_video_service.subscribeCamera.assert_called_once()
    
    def test_subscribe_with_custom_params(self):
        """Test d'abonnement avec paramètres personnalisés."""
        camera = PepperCamera(self.mock_session)
        
        result = camera.subscribe(
            name="CustomApp",
            camera_id=PepperCamera.CAMERA_BOTTOM,
            resolution=PepperCamera.RESOLUTION_QVGA,
            colorspace=PepperCamera.COLORSPACE_RGB,
            fps=15
        )
        
        self.assertTrue(result)
        # Vérifier que les paramètres sont mis à jour
        self.assertEqual(camera._camera_id, PepperCamera.CAMERA_BOTTOM)
        self.assertEqual(camera._resolution, PepperCamera.RESOLUTION_QVGA)
        self.assertEqual(camera._colorspace, PepperCamera.COLORSPACE_RGB)
        self.assertEqual(camera._fps, 15)
    
    def test_subscribe_unsubscribes_existing(self):
        """Test que l'abonnement annule l'existant."""
        camera = PepperCamera(self.mock_session)
        camera._subscriber_id = "old_subscriber"
        
        camera.subscribe("NewApp")
        
        self.mock_video_service.unsubscribe.assert_called_once_with("old_subscriber")
    
    def test_subscribe_no_service(self):
        """Test d'abonnement sans service."""
        camera = PepperCamera(self.mock_session)
        camera.video_service = None
        
        result = camera.subscribe()
        
        self.assertFalse(result)
    
    def test_subscribe_error_handling(self):
        """Test de la gestion d'erreur."""
        camera = PepperCamera(self.mock_session)
        self.mock_video_service.subscribeCamera.side_effect = Exception("Error")
        
        result = camera.subscribe()
        
        self.assertFalse(result)


class TestUnsubscribe(unittest.TestCase):
    """Tests pour se désabonner de la caméra."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_video_service.subscribeCamera.return_value = "subscriber_123"
        self.mock_session.service.return_value = self.mock_video_service
    
    def test_unsubscribe_success(self):
        """Test de désabonnement réussi."""
        camera = PepperCamera(self.mock_session)
        camera.subscribe()
        
        result = camera.unsubscribe()
        
        self.assertTrue(result)
        self.assertIsNone(camera._subscriber_id)
        self.mock_video_service.unsubscribe.assert_called_with("subscriber_123")
    
    def test_unsubscribe_not_subscribed(self):
        """Test de désabonnement sans abonnement."""
        camera = PepperCamera(self.mock_session)
        
        result = camera.unsubscribe()
        
        self.assertFalse(result)
    
    def test_unsubscribe_error_handling(self):
        """Test de la gestion d'erreur."""
        camera = PepperCamera(self.mock_session)
        camera._subscriber_id = "subscriber_123"
        self.mock_video_service.unsubscribe.side_effect = Exception("Error")
        
        result = camera.unsubscribe()
        
        self.assertFalse(result)


class TestGetFrame(unittest.TestCase):
    """Tests pour obtenir une image."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_video_service.subscribeCamera.return_value = "subscriber_123"
        
        # Données d'image simulées
        # Format: [width, height, channels, colorspace, timestamp_s, timestamp_us, data]
        self.mock_image_data = [
            640, 480, 3, 13,          # width, height, channels, colorspace
            1234567, 123456,          # timestamp_s, timestamp_us
            b'\x00' * (640 * 480 * 3) # raw data
        ]
        self.mock_video_service.getImageRemote.return_value = self.mock_image_data
        self.mock_session.service.return_value = self.mock_video_service
    
    def test_get_frame_success(self):
        """Test de capture d'image réussie."""
        camera = PepperCamera(self.mock_session)
        camera.subscribe()
        
        frame = camera.get_frame()
        
        self.assertIsNotNone(frame)
        self.assertEqual(frame["width"], 640)
        self.assertEqual(frame["height"], 480)
        self.assertEqual(frame["channels"], 3)
    
    def test_get_frame_has_data(self):
        """Test que le frame contient des données."""
        camera = PepperCamera(self.mock_session)
        camera.subscribe()
        
        frame = camera.get_frame()
        
        self.assertIn("data", frame)
        self.assertIsNotNone(frame["data"])
    
    def test_get_frame_has_timestamp(self):
        """Test que le frame contient un timestamp."""
        camera = PepperCamera(self.mock_session)
        camera.subscribe()
        
        frame = camera.get_frame()
        
        self.assertIn("timestamp", frame)
        self.assertIsInstance(frame["timestamp"], float)
    
    def test_get_frame_auto_subscribe(self):
        """Test que get_frame s'abonne automatiquement."""
        camera = PepperCamera(self.mock_session)
        
        frame = camera.get_frame()
        
        self.mock_video_service.subscribeCamera.assert_called()
    
    def test_get_frame_no_service(self):
        """Test sans service vidéo."""
        camera = PepperCamera(self.mock_session)
        camera.video_service = None
        
        frame = camera.get_frame()
        
        self.assertIsNone(frame)
    
    def test_get_frame_no_data(self):
        """Test quand aucune donnée n'est retournée."""
        camera = PepperCamera(self.mock_session)
        camera.subscribe()
        self.mock_video_service.getImageRemote.return_value = None
        
        frame = camera.get_frame()
        
        self.assertIsNone(frame)
    
    def test_get_frame_error_handling(self):
        """Test de la gestion d'erreur."""
        camera = PepperCamera(self.mock_session)
        camera.subscribe()
        self.mock_video_service.getImageRemote.side_effect = Exception("Camera error")
        
        frame = camera.get_frame()
        
        self.assertIsNone(frame)


class TestGetFrameAsArray(unittest.TestCase):
    """Tests pour obtenir une image en tant que numpy array."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_video_service.subscribeCamera.return_value = "subscriber_123"
        
        # Données d'image simulées
        self.mock_image_data = [
            320, 240, 3, 13,
            1234567, 123456,
            b'\x00' * (320 * 240 * 3)
        ]
        self.mock_video_service.getImageRemote.return_value = self.mock_image_data
        self.mock_session.service.return_value = self.mock_video_service
    
    @patch('robot_control.pepper_camera.PepperCamera.get_frame')
    def test_get_frame_as_array_without_numpy(self, mock_get_frame):
        """Test sans numpy installé."""
        mock_get_frame.return_value = {
            "width": 320,
            "height": 240,
            "channels": 3,
            "data": b'\x00' * (320 * 240 * 3)
        }
        
        camera = PepperCamera(self.mock_session)
        
        # Simuler l'absence de numpy
        with patch.dict('sys.modules', {'numpy': None}):
            # Importer à nouveau pour que le patch prenne effet
            import importlib
            try:
                result = camera.get_frame_as_array()
                # Si numpy n'est vraiment pas disponible, result sera None
            except ImportError:
                pass  # C'est le comportement attendu


class TestSetCamera(unittest.TestCase):
    """Tests pour changer de caméra."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_video_service.subscribeCamera.return_value = "subscriber_123"
        self.mock_session.service.return_value = self.mock_video_service
    
    def test_set_camera_top(self):
        """Test du changement vers la caméra du haut."""
        camera = PepperCamera(self.mock_session)
        
        result = camera.set_camera(PepperCamera.CAMERA_TOP)
        
        self.assertTrue(result)
        self.assertEqual(camera._camera_id, PepperCamera.CAMERA_TOP)
    
    def test_set_camera_bottom(self):
        """Test du changement vers la caméra du bas."""
        camera = PepperCamera(self.mock_session)
        
        result = camera.set_camera(PepperCamera.CAMERA_BOTTOM)
        
        self.assertTrue(result)
        self.assertEqual(camera._camera_id, PepperCamera.CAMERA_BOTTOM)
    
    def test_set_camera_invalid(self):
        """Test avec ID de caméra invalide."""
        camera = PepperCamera(self.mock_session)
        
        result = camera.set_camera(99)
        
        self.assertFalse(result)


class TestSetResolution(unittest.TestCase):
    """Tests pour changer la résolution."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_video_service.subscribeCamera.return_value = "subscriber_123"
        self.mock_session.service.return_value = self.mock_video_service
    
    def test_set_resolution_vga(self):
        """Test du changement vers VGA."""
        camera = PepperCamera(self.mock_session)
        
        result = camera.set_resolution(PepperCamera.RESOLUTION_VGA)
        
        self.assertTrue(result)
        self.assertEqual(camera._resolution, PepperCamera.RESOLUTION_VGA)
    
    def test_set_resolution_qvga(self):
        """Test du changement vers QVGA."""
        camera = PepperCamera(self.mock_session)
        
        result = camera.set_resolution(PepperCamera.RESOLUTION_QVGA)
        
        self.assertTrue(result)
    
    def test_set_resolution_invalid(self):
        """Test avec résolution invalide."""
        camera = PepperCamera(self.mock_session)
        
        result = camera.set_resolution(99)
        
        self.assertFalse(result)


class TestGetResolution(unittest.TestCase):
    """Tests pour obtenir la résolution actuelle."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_session.service.return_value = self.mock_video_service
    
    def test_get_resolution_default(self):
        """Test de la résolution par défaut."""
        camera = PepperCamera(self.mock_session)
        
        width, height = camera.get_resolution()
        
        self.assertEqual(width, 640)
        self.assertEqual(height, 480)
    
    def test_get_resolution_after_change(self):
        """Test après changement de résolution."""
        self.mock_video_service.subscribeCamera.return_value = "sub"
        camera = PepperCamera(self.mock_session)
        camera.set_resolution(PepperCamera.RESOLUTION_QVGA)
        
        width, height = camera.get_resolution()
        
        self.assertEqual(width, 320)
        self.assertEqual(height, 240)


class TestIsSubscribed(unittest.TestCase):
    """Tests pour vérifier l'état d'abonnement."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_video_service.subscribeCamera.return_value = "subscriber_123"
        self.mock_session.service.return_value = self.mock_video_service
    
    def test_is_subscribed_false_initially(self):
        """Test que le statut est faux initialement."""
        camera = PepperCamera(self.mock_session)
        
        self.assertFalse(camera.is_subscribed())
    
    def test_is_subscribed_true_after_subscribe(self):
        """Test après abonnement."""
        camera = PepperCamera(self.mock_session)
        camera.subscribe()
        
        self.assertTrue(camera.is_subscribed())
    
    def test_is_subscribed_false_after_unsubscribe(self):
        """Test après désabonnement."""
        camera = PepperCamera(self.mock_session)
        camera.subscribe()
        camera.unsubscribe()
        
        self.assertFalse(camera.is_subscribed())


class TestRelease(unittest.TestCase):
    """Tests pour libérer les ressources."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_video_service.subscribeCamera.return_value = "subscriber_123"
        self.mock_session.service.return_value = self.mock_video_service
    
    def test_release_calls_unsubscribe(self):
        """Test que release appelle unsubscribe."""
        camera = PepperCamera(self.mock_session)
        camera.subscribe()
        
        camera.release()
        
        self.mock_video_service.unsubscribe.assert_called()


class TestContextManager(unittest.TestCase):
    """Tests pour le gestionnaire de contexte."""
    
    def setUp(self):
        """Configuration avant chaque test."""
        self.mock_session = Mock()
        self.mock_video_service = Mock()
        self.mock_video_service.subscribeCamera.return_value = "subscriber_123"
        self.mock_session.service.return_value = self.mock_video_service
    
    def test_context_manager_subscribes(self):
        """Test que le context manager s'abonne."""
        camera = PepperCamera(self.mock_session)
        
        with camera:
            self.mock_video_service.subscribeCamera.assert_called()
    
    def test_context_manager_releases(self):
        """Test que le context manager libère les ressources."""
        camera = PepperCamera(self.mock_session)
        
        with camera:
            pass
        
        self.mock_video_service.unsubscribe.assert_called()


class TestConvenienceFunction(unittest.TestCase):
    """Tests pour la fonction de commodité."""
    
    def test_get_frame_without_session(self):
        """Test sans session."""
        result = get_frame(session=None)
        
        self.assertIsNone(result)
    
    def test_get_frame_with_session(self):
        """Test avec session mock."""
        mock_session = Mock()
        mock_video_service = Mock()
        mock_video_service.subscribeCamera.return_value = "sub"
        mock_video_service.getImageRemote.return_value = [
            640, 480, 3, 13, 123, 456, b'\x00' * 100
        ]
        mock_session.service.return_value = mock_video_service
        
        result = get_frame(session=mock_session)
        
        self.assertIsNotNone(result)


class TestCameraConstants(unittest.TestCase):
    """Tests pour les constantes de la caméra."""
    
    def test_camera_ids(self):
        """Test des IDs de caméra."""
        self.assertEqual(PepperCamera.CAMERA_TOP, 0)
        self.assertEqual(PepperCamera.CAMERA_BOTTOM, 1)
        self.assertEqual(PepperCamera.CAMERA_DEPTH, 2)
    
    def test_resolution_constants(self):
        """Test des constantes de résolution."""
        self.assertEqual(PepperCamera.RESOLUTION_QQVGA, 0)
        self.assertEqual(PepperCamera.RESOLUTION_QVGA, 1)
        self.assertEqual(PepperCamera.RESOLUTION_VGA, 2)
        self.assertEqual(PepperCamera.RESOLUTION_4VGA, 3)
    
    def test_colorspace_constants(self):
        """Test des constantes d'espace colorimétrique."""
        self.assertEqual(PepperCamera.COLORSPACE_RGB, 11)
        self.assertEqual(PepperCamera.COLORSPACE_BGR, 13)
    
    def test_resolution_dimensions(self):
        """Test des dimensions de résolution."""
        dims = PepperCamera.RESOLUTION_DIMENSIONS
        
        self.assertEqual(dims[0], (160, 120))
        self.assertEqual(dims[1], (320, 240))
        self.assertEqual(dims[2], (640, 480))
        self.assertEqual(dims[3], (1280, 960))


if __name__ == "__main__":
    unittest.main()
