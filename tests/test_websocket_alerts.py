"""
Tests WebSocket temps réel (Flask-SocketIO)
============================================

Vérifie que:
- Le serveur SocketIO démarre et accepte les connexions
- POST /api/alerts émet l'événement 'new_alert' via WebSocket
- POST /api/alerts/<id>/acknowledge émet 'alert_acknowledged'
- Le payload WebSocket contient les bonnes données
- Les routes HTTP classiques continuent de fonctionner (rétro-compatibilité)
- Le fallback polling (/api/alerts/unhandled) reste opérationnel
"""

import sys
import os
import json
import sqlite3
import unittest
from unittest.mock import patch, MagicMock

# ─── Path setup ───────────────────────────────────────────────
# Permet d'importer app, alert_routes, etc. depuis api_server/
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_api_dir = os.path.join(_project_root, 'api_server')
sys.path.insert(0, _api_dir)
sys.path.insert(0, _project_root)

from app import create_app
from extensions import socketio


# ─── Helpers ──────────────────────────────────────────────────

def _create_test_db(path):
    """Crée une base SQLite de test avec le schéma complet."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            age INTEGER,
            room_number TEXT,
            discharge_date TEXT
        );
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
        );
        INSERT OR IGNORE INTO patients VALUES
            ('PAT001','Ouassim','ARIOUI',72,'203',NULL);
    """)
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════
#  TESTS
# ══════════════════════════════════════════════════════════════

class TestWebSocketAlerts(unittest.TestCase):
    """Tests d'intégration WebSocket pour les alertes temps réel."""

    @classmethod
    def setUpClass(cls):
        """Crée l'app Flask + la base de test une seule fois."""
        cls.db_path = os.path.join(_project_root, 'test_ws_medibot.db')
        _create_test_db(cls.db_path)

        os.environ['DB_PATH'] = cls.db_path
        cls.app = create_app()
        cls.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        """Supprime la base de test."""
        os.environ.pop('DB_PATH', None)
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)

    def setUp(self):
        """Crée un client SocketIO de test pour chaque test."""
        self.client = socketio.test_client(
            self.app,
            flask_test_client=self.app.test_client(),
        )
        self.http = self.app.test_client()

    def tearDown(self):
        if self.client.is_connected():
            self.client.disconnect()

    # ── Connexion SocketIO ────────────────────────────────────

    def test_socketio_connect(self):
        """Le client SocketIO se connecte sans erreur."""
        self.assertTrue(self.client.is_connected())

    def test_socketio_disconnect_reconnect(self):
        """Déconnexion puis reconnexion fonctionne."""
        self.client.disconnect()
        self.assertFalse(self.client.is_connected())
        self.client.connect()
        self.assertTrue(self.client.is_connected())

    # ── Émission new_alert au POST /api/alerts ────────────────

    def test_new_alert_emitted_on_create(self):
        """POST /api/alerts émet un événement 'new_alert' via WebSocket."""
        resp = self.http.post('/api/alerts', json={
            'patient_id': 'PAT001',
            'message': 'Test alerte WebSocket',
            'alert_type': 'emergency',
            'severity': 'high',
        })
        self.assertEqual(resp.status_code, 201)

        received = self.client.get_received()
        ws_events = [e for e in received if e['name'] == 'new_alert']
        self.assertEqual(len(ws_events), 1)

    def test_new_alert_payload_contains_required_fields(self):
        """Le payload new_alert contient id, patient_id, severity, message."""
        self.http.post('/api/alerts', json={
            'patient_id': 'PAT001',
            'message': 'Vérification payload',
            'alert_type': 'general',
            'severity': 'medium',
        })

        received = self.client.get_received()
        ws_events = [e for e in received if e['name'] == 'new_alert']
        payload = ws_events[0]['args'][0]

        self.assertIn('id', payload)
        self.assertEqual(payload['patient_id'], 'PAT001')
        self.assertEqual(payload['severity'], 'medium')
        self.assertEqual(payload['message'], 'Vérification payload')
        self.assertIn('timestamp', payload)

    def test_new_alert_payload_alert_type(self):
        """Le champ alert_type est correctement transmis."""
        self.http.post('/api/alerts', json={
            'patient_id': 'PAT001',
            'message': 'Urgence respiratoire',
            'alert_type': 'emergency',
            'severity': 'high',
        })

        received = self.client.get_received()
        payload = [e for e in received if e['name'] == 'new_alert'][0]['args'][0]
        self.assertEqual(payload['alert_type'], 'emergency')

    def test_new_alert_legacy_priority_mapping(self):
        """Le format legacy (priority → severity) fonctionne avec WebSocket."""
        self.http.post('/api/alerts', json={
            'patient_id': 'PAT001',
            'reason': 'Chute détectée',
            'priority': 3,
        })

        received = self.client.get_received()
        payload = [e for e in received if e['name'] == 'new_alert'][0]['args'][0]
        self.assertEqual(payload['severity'], 'high')
        self.assertEqual(payload['message'], 'Chute détectée')

    def test_multiple_alerts_emit_multiple_events(self):
        """Plusieurs POST émettent chacun un événement distinct."""
        for i in range(3):
            self.http.post('/api/alerts', json={
                'patient_id': 'PAT001',
                'message': f'Alerte #{i}',
            })

        received = self.client.get_received()
        ws_events = [e for e in received if e['name'] == 'new_alert']
        self.assertEqual(len(ws_events), 3)

    # ── Émission alert_acknowledged ───────────────────────────

    def test_acknowledge_emits_event(self):
        """POST acknowledge émet 'alert_acknowledged' avec le bon alert_id."""
        # Créer une alerte
        resp = self.http.post('/api/alerts', json={
            'patient_id': 'PAT001',
            'message': 'À acquitter',
        })
        alert_id = resp.get_json()['alert_id']

        # Vider les events reçus (new_alert)
        self.client.get_received()

        # Acquitter
        resp2 = self.http.post(f'/api/alerts/{alert_id}/acknowledge', json={
            'handled_by': 'Infirmière Test',
        })
        self.assertEqual(resp2.status_code, 200)

        received = self.client.get_received()
        ack_events = [e for e in received if e['name'] == 'alert_acknowledged']
        self.assertEqual(len(ack_events), 1)
        self.assertEqual(ack_events[0]['args'][0]['alert_id'], alert_id)
        self.assertEqual(ack_events[0]['args'][0]['handled_by'], 'Infirmière Test')

    def test_acknowledge_nonexistent_alert(self):
        """Acquitter une alerte inexistante renvoie 404 sans crash WebSocket."""
        resp = self.http.post('/api/alerts/99999/acknowledge', json={
            'handled_by': 'Test',
        })
        self.assertEqual(resp.status_code, 404)

        received = self.client.get_received()
        ack_events = [e for e in received if e['name'] == 'alert_acknowledged']
        self.assertEqual(len(ack_events), 0)

    # ── Rétro-compatibilité HTTP (polling fallback) ───────────

    def test_http_create_still_returns_201(self):
        """POST /api/alerts renvoie toujours 201 + JSON correct."""
        resp = self.http.post('/api/alerts', json={
            'patient_id': 'PAT001',
            'message': 'Test HTTP classique',
        })
        data = resp.get_json()
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(data['success'])
        self.assertIn('alert_id', data)

    def test_http_unhandled_returns_alerts(self):
        """GET /api/alerts/unhandled continue de fonctionner (polling)."""
        # Créer une alerte
        self.http.post('/api/alerts', json={
            'patient_id': 'PAT001',
            'message': 'Visible en polling',
        })

        resp = self.http.get('/api/alerts/unhandled')
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data['success'])
        self.assertGreater(data['count'], 0)

    def test_http_create_no_json_returns_error(self):
        """POST sans JSON renvoie une erreur (400 ou 500)."""
        resp = self.http.post('/api/alerts', data='not json',
                              content_type='text/plain')
        self.assertIn(resp.status_code, (400, 500))
        self.assertFalse(resp.get_json()['success'])

    def test_health_check(self):
        """GET /api/health fonctionne avec SocketIO activé."""
        resp = self.http.get('/api/health')
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['status'], 'ok')

    # ── Isolation & robustesse ────────────────────────────────

    def test_no_event_without_create(self):
        """Aucun événement WebSocket si on ne crée pas d'alerte."""
        received = self.client.get_received()
        ws_events = [e for e in received if e['name'] == 'new_alert']
        self.assertEqual(len(ws_events), 0)

    def test_ws_event_id_matches_http_response(self):
        """L'alert_id du WebSocket correspond à celui du HTTP."""
        resp = self.http.post('/api/alerts', json={
            'patient_id': 'PAT001',
            'message': 'Sync id check',
        })
        http_id = resp.get_json()['alert_id']

        received = self.client.get_received()
        ws_id = [e for e in received if e['name'] == 'new_alert'][0]['args'][0]['id']
        self.assertEqual(ws_id, http_id)


# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    unittest.main()
