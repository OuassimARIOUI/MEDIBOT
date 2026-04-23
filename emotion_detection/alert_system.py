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

# URL de l'API Rasa (tracker des slots)
RASA_TRACKER_URL = os.getenv(
    "RASA_URL", "http://localhost:5005"
) + "/conversations/user_voice/tracker"

# ==== RÈGLE MÉTIER STRICTE ============================================
# Un patient valide a IMPÉRATIVEMENT un ID de la forme PATxxx (ex: PAT001).
# Toute autre valeur (Inconnu, UNKNOWN, vide, etc.) est refusée.
# ======================================================================
import re
_PAT_ID_RE = re.compile(r"^PAT\d+$", re.IGNORECASE)


def is_valid_pat_id(pid) -> bool:
    """Retourne True UNIQUEMENT si pid respecte le format PATxxx."""
    if pid is None:
        return False
    try:
        return bool(_PAT_ID_RE.match(str(pid).strip()))
    except Exception:
        return False


def _query_rasa_patient_id() -> str:
    """
    Interroge l'API Rasa Tracker pour récupérer le slot patient_id
    du dernier tour de conversation.

    Endpoint : GET /conversations/user_voice/tracker
    Slot visé : patient_id  (rempli par ActionIdentifyPatient)

    Retourne un patient_id VALIDE (PATxxx) ou "UNKNOWN".
    Timeout court (1 s) pour ne pas bloquer le pipeline vision.
    """
    try:
        resp = requests.get(RASA_TRACKER_URL, timeout=1)
        if resp.status_code == 200:
            slots = resp.json().get("slots", {})
            pid = slots.get("patient_id")
            if is_valid_pat_id(pid):
                return str(pid).strip().upper()
    except Exception:
        pass  # Rasa pas encore prêt ou coupé — on tente la BD
    return "UNKNOWN"


def _query_db_patient_id(db_path: str) -> str:
    """
    Lit le patient identifié depuis la table current_patient_session
    (écrite par Rasa via set_current_patient dans db_utils.py).

    Retourne le patient_id ou "UNKNOWN".
    Session valide pendant 4 heures max.
    """
    try:
        from datetime import datetime as dt, timedelta
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT patient_id, identified_at FROM current_patient_session WHERE id = 1"
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return "UNKNOWN"
        patient_id, identified_at = row
        try:
            if dt.now() - dt.fromisoformat(str(identified_at)) > timedelta(hours=4):
                return "UNKNOWN"  # Session expirée
        except Exception:
            pass  # En cas de format inattendu, accepter quand même
        if patient_id and str(patient_id).strip().upper() not in ("UNKNOWN", ""):
            return str(patient_id).strip()
    except Exception as e:
        logger.debug(f"[PATIENT CHECK] Erreur lecture DB session : {e}")
    return "UNKNOWN"


def resolve_patient_id(patient_id_hint: str, db_path: str) -> str:
    """
    Résout l'identité du patient de façon exhaustive :
      1. Interroge l'API Rasa Tracker en priorité (source de vérité)
      2. Sinon, lit la table current_patient_session (DB partagée)
      3. Si hint déjà valide PATxxx → fallback accepté
      4. Sinon retourne "UNKNOWN".
    Ne retourne JAMAIS une valeur qui n'est pas de la forme PATxxx ou "UNKNOWN".
    """
    # 1. Rasa = source de vérité (pivot central)
    pid = _query_rasa_patient_id()
    if is_valid_pat_id(pid):
        logger.info(f"[PATIENT CHECK] Patient résolu via Rasa Tracker : {pid}")
        return str(pid).strip().upper()

    # 2. Fallback : DB partagée (session patient active)
    pid = _query_db_patient_id(db_path)
    if is_valid_pat_id(pid):
        logger.info(f"[PATIENT CHECK] Patient résolu via DB session : {pid}")
        return str(pid).strip().upper()

    # 3. Dernier recours : hint de l'appelant (uniquement si déjà valide)
    if is_valid_pat_id(patient_id_hint):
        return str(patient_id_hint).strip().upper()

    return "UNKNOWN"


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
        # Anti-spam : cooldown par (alert_type, reason tronqué)
        self._last_sent = {}       # {(type, reason_key): timestamp}
        self._cooldown = 20.0      # secondes entre deux alertes identiques

    def _is_rate_limited(self, alert_type: str, reason: str) -> bool:
        key = (alert_type, (reason or "")[:40].lower())
        now = datetime.datetime.now().timestamp()
        last = self._last_sent.get(key, 0.0)
        if now - last < self._cooldown:
            return True
        self._last_sent[key] = now
        return False

    def send_alert(self, level, reason, patient_id="UNKNOWN",
                   alert_type="general", severity=None):
        """
        Envoie une alerte selon les niveaux du cahier des charges :
          Niveau 1 : a surveiller
          Niveau 2 : urgence vitale

        Args:
            level (int): 1 ou 2
            reason (str): description de l'alerte
            patient_id (str): identifiant du patient
            alert_type (str): 'emergency' | 'emotion' | 'general'
            severity (str): 'low' | 'medium' | 'high' | 'critical' (auto si None)
        """
        # Normaliser level en entier (defensive cast)
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = 2 if str(level) in ("high", "critical") else 1

        # Determiner la severite automatiquement si non fournie
        if severity is None:
            if level >= 2:
                severity = "critical"
            else:
                severity = "medium"

        timestamp = datetime.datetime.now().isoformat()

        # Anti-spam : ignorer les alertes identiques trop rapprochées
        if self._is_rate_limited(alert_type, reason):
            logger.debug(f"Alerte ignorée (rate limit) : [{alert_type}] {reason[:40]}")
            return False

        # Log console visible
        print(f"--- [ALERTE NIVEAU {level}] [{severity.upper()}] : {reason} ---")

        # 1. Inserer dans la BD SQLite (toujours, meme si Flask tombe)
        alert_id = self._insert_to_db(
            patient_id=patient_id,
            message=reason,
            alert_type=alert_type,
            severity=severity
        )

        # 2. Envoyer au dashboard Flask
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
            print("[MODE DEGRADE] Dashboard injoignable. Alerte sauvegardee en BD locale.")
            logger.warning("Dashboard Flask injoignable, alerte sauvegardee en BD.")
        except Exception as e:
            logger.warning(f"Erreur envoi dashboard: {e}")

        # 3. Notifier les infirmiers si urgence ou severite haute
        if level >= 2 or severity in ("high", "critical"):
            self.notify_nurses(
                alert_id=alert_id,
                patient_id=patient_id,
                reason=reason,
                severity=severity,
                alert_type=alert_type
            )

        return dashboard_ok or (alert_id is not None)

    def send_emergency_alert(self, reason, patient_id="UNKNOWN"):
        """
        Raccourci pour envoyer une alerte d'urgence maximale.
        Etouffement, absence de respiration, etc.
        """
        return self.send_alert(
            level=2,
            reason=reason,
            patient_id=patient_id,
            alert_type="emergency",
            severity="critical"
        )

    def send_emotion_alert(self, emotion, patient_id="UNKNOWN", severity="medium"):
        """
        Raccourci pour envoyer une alerte liee a une emotion detectee.
        """
        reason = f"Emotion de detresse detectee : {emotion} (patient {patient_id})"
        return self.send_alert(
            level=2 if severity == "high" else 1,
            reason=reason,
            patient_id=patient_id,
            alert_type="emotion",
            severity=severity
        )

    def log_emotion(self, patient_id, emotion, severity="low"):
        """
        Enregistre une emotion detectee dans la table emotion_logs.
        Appelee pour CHAQUE emotion stable, meme les positives (happy, neutral).
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO emotion_logs (patient_id, emotion, severity)
                VALUES (?, ?, ?)
            """, (patient_id, emotion, severity))
            conn.commit()
            log_id = cursor.lastrowid
            conn.close()
            logger.info(f"Emotion '{emotion}' enregistree pour {patient_id} (log #{log_id})")
            return log_id
        except Exception as e:
            logger.error(f"Erreur insertion emotion_logs: {e}")
            return None

    # ------------------------------------------------------------------
    # METHODES INTERNES
    # ------------------------------------------------------------------

    def _insert_to_db(self, patient_id, message, alert_type="general",
                      severity="medium"):
        """
        Insere une alerte directement dans la table alerts de SQLite.
        Retourne l'alert_id ou None en cas d'erreur.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alerts (patient_id, message, alert_type, severity)
                VALUES (?, ?, ?, ?)
            """, (patient_id, message, alert_type, severity))
            conn.commit()
            alert_id = cursor.lastrowid
            conn.close()
            logger.info(f"Alerte #{alert_id} inseree en BD [{alert_type}/{severity}]")
            return alert_id
        except Exception as e:
            logger.error(f"Erreur insertion BD alerts: {e}")
            print(f"[ERREUR BD] Impossible d'inserer l'alerte: {e}")
            return None

    def notify_nurses(self, alert_id, patient_id, reason, severity,
                      alert_type="general"):
        """
        Notifie les infirmiers via le service de mail/notification.
        Utilise send_critical_alert pour les urgences, send_alert_notification sinon.
        """
        try:
            # Ajouter le chemin api_server pour importer mail_service
            api_server_path = os.path.join(_PROJECT_ROOT, "api_server")
            if api_server_path not in sys.path:
                sys.path.insert(0, api_server_path)

            from utils.mail_service import send_critical_alert, send_alert_notification

            if alert_type == "emergency" or severity == "critical":
                send_critical_alert(
                    alert_id=alert_id or 0,
                    patient_name=f"Patient {patient_id}",
                    room_number="--",
                    message=reason
                )
                print(f"[NOTIFICATION] Alerte CRITIQUE envoyee aux infirmiers pour {patient_id}")
            else:
                send_alert_notification(
                    alert_id=alert_id or 0,
                    status="new",
                    handled_by=None
                )
                print(f"[NOTIFICATION] Alerte envoyee aux infirmiers pour {patient_id}")

            logger.info(f"Notification infirmiers envoyee (alerte #{alert_id})")

        except ImportError as e:
            logger.warning(f"mail_service non disponible: {e}")
            print(f"[NOTIFICATION] Service mail indisponible, alerte loguee localement.")
        except Exception as e:
            logger.warning(f"Erreur notification infirmiers: {e}")
            print(f"[NOTIFICATION] Erreur envoi notification: {e}")