"""
Tests unitaires pour le service d'alertes (alert_service.py)
Ce fichier teste toutes les fonctionnalités du système d'alertes d'urgence.
"""

import unittest
import sqlite3
import os
import sys
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import json

# Ajouter le chemin du module parent pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rasa_bot', 'actions'))

# Import du service d'alertes
from rasa_bot.actions import alert_service
from rasa_bot.actions.alert_service import (
    get_patient_info,
    save_alert_to_db,
    send_alert_to_dashboard,
    trigger_emergency_alert,
    trigger_nurse_call
)


class TestAlertService(unittest.TestCase):
    """Tests pour le service d'alertes d'urgence"""
    
    @classmethod
    def setUpClass(cls):
        """Configuration initiale avant tous les tests"""
        # Créer une base de données de test en mémoire
        cls.test_db_path = ":memory:"
        os.environ["DB_PATH"] = cls.test_db_path
        
    def setUp(self):
        """Configuration avant chaque test"""
        # Créer une connexion de test partagée pour les données
        self.test_db = ":memory:"
        self.conn = sqlite3.connect(self.test_db, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Créer le schéma de test
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                age INTEGER,
                room_number TEXT,
                discharge_date TEXT
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                message TEXT,
                alert_type TEXT DEFAULT 'general',
                severity TEXT DEFAULT 'medium',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                handled INTEGER DEFAULT 0,
                handled_at DATETIME,
                handled_by TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
            )
        """)
        
        # Insérer des données de test (correspondant au schema.sql)
        self.cursor.execute("""
            INSERT INTO patients (patient_id, first_name, last_name, age, room_number, discharge_date)
            VALUES ('PAT001', 'Ouassim', 'ARIOUI', 72, '203', '05/02/2026')
        """)
        
        self.cursor.execute("""
            INSERT INTO patients (patient_id, first_name, last_name, age, room_number, discharge_date)
            VALUES ('PAT002', 'Asmaa', 'BOUKRAA', 68, '204', '10/02/2026')
        """)
        
        self.cursor.execute("""
            INSERT INTO patients (patient_id, first_name, last_name, age, room_number, discharge_date)
            VALUES ('PAT003', 'Test', 'Patient', 50, NULL, '15/02/2026')
        """)
        
        self.conn.commit()
        
    def tearDown(self):
        """Nettoyage après chaque test"""
        self.conn.close()
    
    # ========== Tests pour get_patient_info ==========
    
    @patch('rasa_bot.actions.alert_service.get_connection')
    def test_get_patient_info_success(self, mock_get_connection):
        """Test : Récupération réussie des informations d'un patient"""
        # Configurer le mock
        mock_get_connection.return_value = self.conn
        
        # Exécuter la fonction
        result = get_patient_info('PAT001')
        
        # Vérifications
        self.assertIsNotNone(result)
        self.assertEqual(result['patient_id'], 'PAT001')
        self.assertEqual(result['first_name'], 'Ouassim')
        self.assertEqual(result['last_name'], 'ARIOUI')
        self.assertEqual(result['room_number'], '203')
    
    @patch('rasa_bot.actions.alert_service.get_connection')
    def test_get_patient_info_not_found(self, mock_get_connection):
        """Test : Patient inexistant"""
        mock_get_connection.return_value = self.conn
        
        result = get_patient_info('PAT999')
        
        self.assertIsNone(result)
    
    @patch('rasa_bot.actions.alert_service.get_connection')
    def test_get_patient_info_no_room_number(self, mock_get_connection):
        """Test : Patient sans numéro de chambre"""
        mock_get_connection.return_value = self.conn
        
        result = get_patient_info('PAT003')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['room_number'], 'Non spécifié')
    
    # ========== Tests pour save_alert_to_db ==========
    
    @patch('rasa_bot.actions.alert_service.get_connection')
    def test_save_alert_to_db_success(self, mock_get_connection):
        """Test : Sauvegarde réussie d'une alerte"""
        # Créer un mock qui ne ferme pas vraiment la connexion
        mock_conn = MagicMock(wraps=self.conn)
        mock_conn.cursor.return_value = self.conn.cursor()
        mock_conn.commit = self.conn.commit
        mock_conn.close = MagicMock()  # Ne fait rien quand close() est appelé
        mock_get_connection.return_value = mock_conn
        
        alert_id = save_alert_to_db(
            patient_id='PAT001',
            room_number='203',
            patient_name='Ouassim ARIOUI',
            message='J\'ai très mal'
        )
        
        # Vérifications
        self.assertIsNotNone(alert_id)
        self.assertGreater(alert_id, 0)
        
        # Vérifier que l'alerte a bien été insérée
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,))
        alert = cursor.fetchone()
        cursor.close()
        self.assertIsNotNone(alert)
        self.assertIn('URGENCE - Chambre 203 - Ouassim ARIOUI', alert[2])
    
    @patch('rasa_bot.actions.alert_service.get_connection')
    def test_save_alert_to_db_message_format(self, mock_get_connection):
        """Test : Format du message d'alerte"""
        # Créer un mock qui ne ferme pas vraiment la connexion
        mock_conn = MagicMock(wraps=self.conn)
        mock_conn.cursor.return_value = self.conn.cursor()
        mock_conn.commit = self.conn.commit
        mock_conn.close = MagicMock()  # Ne fait rien quand close() est appelé
        mock_get_connection.return_value = mock_conn
        
        alert_id = save_alert_to_db(
            patient_id='PAT002',
            room_number='204',
            patient_name='Asmaa BOUKRAA',
            message='Test d\'urgence'
        )
        
        # Créer un nouveau curseur pour vérifier
        cursor = self.conn.cursor()
        cursor.execute("SELECT message FROM alerts WHERE alert_id = ?", (alert_id,))
        message = cursor.fetchone()[0]
        cursor.close()
        
        expected = "URGENCE - Chambre 204 - Asmaa BOUKRAA: Test d'urgence"
        self.assertEqual(message, expected)
    
    # ========== Tests pour send_alert_to_dashboard ==========
    
    @patch('rasa_bot.actions.alert_service.requests.post')
    def test_send_alert_to_dashboard_success(self, mock_post):
        """Test : Envoi réussi d'une alerte au dashboard"""
        # Configurer le mock pour simuler une réponse réussie
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = send_alert_to_dashboard(
            patient_id='PAT001',
            room_number='203',
            patient_name='Ouassim ARIOUI',
            message='Urgence détectée',
            alert_type='URGENCE'
        )
        
        # Vérifications
        self.assertTrue(result)
        mock_post.assert_called_once()
        
        # Vérifier les données envoyées
        call_args = mock_post.call_args
        sent_data = call_args[1]['json']
        
        self.assertEqual(sent_data['patient_id'], 'PAT001')
        self.assertEqual(sent_data['patient_name'], 'Ouassim ARIOUI')
        self.assertEqual(sent_data['room_number'], '203')
        self.assertEqual(sent_data['alert_type'], 'URGENCE')
        self.assertEqual(sent_data['status'], 'ACTIVE')
    
    @patch('rasa_bot.actions.alert_service.requests.post')
    def test_send_alert_to_dashboard_201_response(self, mock_post):
        """Test : Envoi réussi avec code 201"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response
        
        result = send_alert_to_dashboard(
            patient_id='PAT001',
            room_number='203',
            patient_name='Ouassim ARIOUI',
            message='Test',
            alert_type='URGENCE'
        )
        
        self.assertTrue(result)
    
    @patch('rasa_bot.actions.alert_service.requests.post')
    def test_send_alert_to_dashboard_connection_error(self, mock_post):
        """Test : Erreur de connexion au dashboard"""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()
        
        result = send_alert_to_dashboard(
            patient_id='PAT001',
            room_number='203',
            patient_name='Ouassim ARIOUI',
            message='Test',
            alert_type='URGENCE'
        )
        
        self.assertFalse(result)
    
    @patch('rasa_bot.actions.alert_service.requests.post')
    def test_send_alert_to_dashboard_timeout(self, mock_post):
        """Test : Timeout lors de l'envoi"""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()
        
        result = send_alert_to_dashboard(
            patient_id='PAT001',
            room_number='203',
            patient_name='Ouassim ARIOUI',
            message='Test',
            alert_type='URGENCE'
        )
        
        self.assertFalse(result)
    
    @patch('rasa_bot.actions.alert_service.requests.post')
    def test_send_alert_to_dashboard_http_error(self, mock_post):
        """Test : Erreur HTTP (404, 500, etc.)"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        result = send_alert_to_dashboard(
            patient_id='PAT001',
            room_number='203',
            patient_name='Ouassim ARIOUI',
            message='Test',
            alert_type='URGENCE'
        )
        
        self.assertFalse(result)
    
    @patch('rasa_bot.actions.alert_service.requests.post')
    def test_send_alert_to_dashboard_url_and_headers(self, mock_post):
        """Test : Vérification de l'URL et des headers"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        send_alert_to_dashboard(
            patient_id='PAT001',
            room_number='203',
            patient_name='Test Patient',
            message='Test',
            alert_type='URGENCE'
        )
        
        # Vérifier l'URL appelée
        call_args = mock_post.call_args
        self.assertIn('http://localhost:5000/api/alerts', str(call_args))
        
        # Vérifier les headers
        self.assertEqual(call_args[1]['headers']['Content-Type'], 'application/json')
    
    # ========== Tests pour trigger_emergency_alert ==========
    
    @patch('rasa_bot.actions.alert_service.send_alert_to_dashboard')
    @patch('rasa_bot.actions.alert_service.save_alert_to_db')
    @patch('rasa_bot.actions.alert_service.get_patient_info')
    def test_trigger_emergency_alert_success(self, mock_get_patient, mock_save, mock_send):
        """Test : Déclenchement réussi d'une alerte d'urgence"""
        # Configurer les mocks
        mock_get_patient.return_value = {
            'patient_id': 'PAT001',
            'first_name': 'Ouassim',
            'last_name': 'ARIOUI',
            'room_number': '203'
        }
        mock_save.return_value = 1
        mock_send.return_value = True
        
        # Exécuter la fonction
        result = trigger_emergency_alert(
            patient_id='PAT001',
            message='Urgence détectée',
            user_message='J\'ai très mal'
        )
        
        # Vérifications
        self.assertTrue(result['success'])
        # Quand le dashboard répond OK, pas de sauvegarde locale → alert_id est None
        self.assertIsNone(result['alert_id'])
        self.assertTrue(result['dashboard_sent'])
        self.assertEqual(result['patient_name'], 'Ouassim ARIOUI')
        self.assertEqual(result['room_number'], '203')
        self.assertIn('J\'ai très mal', result['message'])
        
        # Vérifier que les fonctions ont été appelées
        mock_get_patient.assert_called_once_with('PAT001')
        mock_save.assert_not_called()  # Pas de fallback quand dashboard OK
        mock_send.assert_called_once()
    
    @patch('rasa_bot.actions.alert_service.get_patient_info')
    def test_trigger_emergency_alert_patient_not_found(self, mock_get_patient):
        """Test : Patient non trouvé lors du déclenchement d'alerte"""
        mock_get_patient.return_value = None
        
        result = trigger_emergency_alert(
            patient_id='PAT999',
            message='Urgence'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Patient non trouvé')
        self.assertIsNone(result['alert_id'])
    
    @patch('rasa_bot.actions.alert_service.send_alert_to_dashboard')
    @patch('rasa_bot.actions.alert_service.save_alert_to_db')
    @patch('rasa_bot.actions.alert_service.get_patient_info')
    def test_trigger_emergency_alert_without_user_message(self, mock_get_patient, mock_save, mock_send):
        """Test : Alerte sans message utilisateur"""
        mock_get_patient.return_value = {
            'patient_id': 'PAT001',
            'first_name': 'Ouassim',
            'last_name': 'ARIOUI',
            'room_number': '203'
        }
        mock_save.return_value = 2
        mock_send.return_value = True
        
        result = trigger_emergency_alert(
            patient_id='PAT001',
            message='Urgence détectée'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Urgence détectée')
    
    @patch('rasa_bot.actions.alert_service.send_alert_to_dashboard')
    @patch('rasa_bot.actions.alert_service.save_alert_to_db')
    @patch('rasa_bot.actions.alert_service.get_patient_info')
    def test_trigger_emergency_alert_dashboard_failure(self, mock_get_patient, mock_save, mock_send):
        """Test : Échec d'envoi au dashboard mais alerte sauvegardée"""
        mock_get_patient.return_value = {
            'patient_id': 'PAT001',
            'first_name': 'Ouassim',
            'last_name': 'ARIOUI',
            'room_number': '203'
        }
        mock_save.return_value = 3
        mock_send.return_value = False  # Dashboard hors ligne
        
        result = trigger_emergency_alert(
            patient_id='PAT001',
            message='Urgence'
        )
        
        # L'alerte est considérée comme réussie même si dashboard échoue
        self.assertTrue(result['success'])
        self.assertFalse(result['dashboard_sent'])
        self.assertEqual(result['alert_id'], 3)
    
    # ========== Tests pour trigger_nurse_call ==========
    
    @patch('rasa_bot.actions.alert_service.send_alert_to_dashboard')
    @patch('rasa_bot.actions.alert_service.save_alert_to_db')
    @patch('rasa_bot.actions.alert_service.get_patient_info')
    def test_trigger_nurse_call_success(self, mock_get_patient, mock_save, mock_send):
        """Test : Appel d'infirmière réussi"""
        mock_get_patient.return_value = {
            'patient_id': 'PAT002',
            'first_name': 'Asmaa',
            'last_name': 'Boukraa',
            'room_number': '204'
        }
        mock_save.return_value = 4
        mock_send.return_value = True
        
        result = trigger_nurse_call(
            patient_id='PAT002',
            reason='Patient ne se sent pas bien'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['alert_id'], 4)
        self.assertTrue(result['dashboard_sent'])
        self.assertEqual(result['patient_name'], 'Asmaa Boukraa')
        
        # Vérifier que le type d'alerte est correct
        mock_send.assert_called_once()
        call_args = mock_send.call_args[1]
        self.assertEqual(call_args['alert_type'], 'APPEL_INFIRMIERE')
    
    @patch('rasa_bot.actions.alert_service.get_patient_info')
    def test_trigger_nurse_call_patient_not_found(self, mock_get_patient):
        """Test : Patient non trouvé lors de l'appel infirmière"""
        mock_get_patient.return_value = None
        
        result = trigger_nurse_call(
            patient_id='PAT999',
            reason='Test'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Patient non trouvé')
    
    @patch('rasa_bot.actions.alert_service.send_alert_to_dashboard')
    @patch('rasa_bot.actions.alert_service.save_alert_to_db')
    @patch('rasa_bot.actions.alert_service.get_patient_info')
    def test_trigger_nurse_call_default_reason(self, mock_get_patient, mock_save, mock_send):
        """Test : Appel infirmière avec raison par défaut"""
        mock_get_patient.return_value = {
            'patient_id': 'PAT001',
            'first_name': 'Ouassim',
            'last_name': 'Arioui',
            'room_number': '203'
        }
        mock_save.return_value = 5
        mock_send.return_value = True
        
        result = trigger_nurse_call(patient_id='PAT001')
        
        self.assertTrue(result['success'])
    
    # ========== Tests d'intégration ==========
    
    @patch('rasa_bot.actions.alert_service.requests.post')
    @patch('rasa_bot.actions.alert_service.get_connection')
    def test_full_emergency_workflow(self, mock_get_connection, mock_post):
        """Test : Workflow complet d'une urgence"""
        # Créer un mock qui ne ferme pas vraiment la connexion
        mock_conn = MagicMock(wraps=self.conn)
        mock_conn.cursor.return_value = self.conn.cursor()
        mock_conn.commit = self.conn.commit
        mock_conn.close = MagicMock()  # Ne fait rien quand close() est appelé
        mock_get_connection.return_value = mock_conn
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Déclencher l'alerte
        result = trigger_emergency_alert(
            patient_id='PAT001',
            message='Urgence détectée',
            user_message='Je n\'arrive pas à respirer'
        )
        
        # Vérifications complètes
        self.assertTrue(result['success'])
        # Dashboard a répondu 200 → pas de sauvegarde locale → alert_id None
        self.assertIsNone(result['alert_id'])
        self.assertTrue(result['dashboard_sent'])
        self.assertEqual(result['patient_name'], 'Ouassim ARIOUI')
        self.assertEqual(result['room_number'], '203')


class TestAlertServiceEdgeCases(unittest.TestCase):
    """Tests pour les cas limites et les scénarios d'erreur"""
    
    def setUp(self):
        """Configuration avant chaque test"""
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()
        
        # Créer le schéma minimal
        self.cursor.execute("""
            CREATE TABLE patients (
                patient_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                room_number TEXT
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                message TEXT,
                alert_type TEXT DEFAULT 'general',
                severity TEXT DEFAULT 'medium',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                handled INTEGER DEFAULT 0,
                handled_at DATETIME,
                handled_by TEXT
            )
        """)
        
        self.conn.commit()
    
    def tearDown(self):
        """Nettoyage"""
        self.conn.close()
    
    @patch('rasa_bot.actions.alert_service.get_connection')
    def test_empty_patient_name(self, mock_get_connection):
        """Test : Patient avec prénom/nom vides"""
        self.cursor.execute("""
            INSERT INTO patients (patient_id, first_name, last_name, room_number)
            VALUES ('PAT999', '', '', '999')
        """)
        self.conn.commit()
        
        mock_get_connection.return_value = self.conn
        
        result = get_patient_info('PAT999')
        self.assertIsNotNone(result)
        self.assertEqual(result['first_name'], '')
    
    @patch('rasa_bot.actions.alert_service.get_connection')
    def test_special_characters_in_message(self, mock_get_connection):
        """Test : Caractères spéciaux dans le message"""
        self.cursor.execute("""
            INSERT INTO patients (patient_id, first_name, last_name, room_number)
            VALUES ('PAT001', 'Test', 'User', '100')
        """)
        self.conn.commit()
        
        mock_get_connection.return_value = self.conn
        
        special_message = "J'ai mal!!! @#$%^&* <script>alert('test')</script>"
        alert_id = save_alert_to_db('PAT001', '100', 'Test User', special_message)
        
        self.assertIsNotNone(alert_id)


def run_tests():
    """Fonction pour exécuter tous les tests"""
    # Créer une suite de tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Ajouter tous les tests
    suite.addTests(loader.loadTestsFromTestCase(TestAlertService))
    suite.addTests(loader.loadTestsFromTestCase(TestAlertServiceEdgeCases))
    
    # Exécuter les tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Retourner le résultat
    return result.wasSuccessful()


if __name__ == '__main__':
    print("=" * 70)
    print("TESTS DU SERVICE D'ALERTES MEDIBOT")
    print("=" * 70)
    print()
    
    success = run_tests()
    
    print()
    print("=" * 70)
    if success:
        print(" TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS!")
    else:
        print(" CERTAINS TESTS ONT ÉCHOUÉ")
    print("=" * 70)
    
    sys.exit(0 if success else 1)
