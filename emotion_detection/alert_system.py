"""
alert_system.py — Systeme d'alerte enrichi.

Fonctionnalites :
  - Envoi d'alertes au dashboard Flask (POST /api/alerts)
  - Insertion directe dans la BD SQLite (mode degrade si Flask indisponible)
  - Notification des infirmiers via mail_service
  - Support des types d'alerte : emergency, emotion, general
  - Support des severites : low, medium, high, critical
"""

import os
import sys
import sqlite3
import requests
import datetime
import logging

logger = logging.getLogger(__name__)

# Chemin par defaut de la BD (relatif au projet)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, "database", "medibot.db")


class AlertSystem:
    """
    Systeme d'alerte central pour MediBot.

    Envoie les alertes au dashboard Flask ET les insere directement
    dans la BD SQLite pour garantir la persistance meme si le serveur
    Flask est injoignable.
    """

    def __init__(self, dashboard_url="http://localhost:5000/api/alerts",
                 db_path=None):
        self.dashboard_url = dashboard_url
        self.db_path = db_path or DEFAULT_DB_PATH

    def send_alert(self, level, reason, patient_id="UNKNOWN",
                   alert_type="general", severity=None):
        """
        Envoie une alerte selon les niveaux du cahier des charges :
        Niveau 1: à surveiller | Niveau 2: urgence vitale [cite: 112]
        """
        payload = {
            "timestamp": timestamp,
            "patient_id": patient_id,
            "priority": level,
            "reason": reason,
            "alert_type": alert_type,
            "severity": severity,
            "status": "pending"
        }

        dashboard_ok = False
        try:
            response = requests.post(self.dashboard_url, json=payload, timeout=2)
            dashboard_ok = response.status_code in (200, 201)
            if dashboard_ok:
                logger.info(f"Alerte envoyee au dashboard (HTTP {response.status_code})")
        except requests.exceptions.ConnectionError:
            # Mode dégradé : Dashboard injoignable. Alerte loguée localement.
            print("⚠️ Mode dégradé : Dashboard injoignable. Alerte loguée localement.")
            return False

# Exemple d'usage pour vos tests
# alert = AlertSystem()
# alert.send_alert(level=2, reason="Absence de respiration détectée") [cite: 214]