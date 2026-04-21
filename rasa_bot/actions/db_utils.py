import sqlite3
from typing import Optional, Tuple, List
import os
from pathlib import Path

# Chemin absolu vers la base de données
BASE_DIR = Path(__file__).resolve().parent.parent.parent
_db_path_env = os.getenv("DB_PATH")
if _db_path_env:
    # Si le chemin est relatif, le résoudre par rapport à BASE_DIR
    _db_path = Path(_db_path_env)
    if not _db_path.is_absolute():
        DB_PATH = str(BASE_DIR / _db_path)
    else:
        DB_PATH = str(_db_path)
else:
    DB_PATH = str(BASE_DIR / "database" / "medibot.db")


def get_connection():
    """
    Crée et retourne une connexion SQLite.
    """
    return sqlite3.connect(DB_PATH)


def get_all_patients() -> List[Tuple[str, str, str, str, str]]:
    """
    Récupère tous les patients de la base de données.
    Retourne une liste de tuples: (patient_id, first_name, last_name, room_number, discharge_date)
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT patient_id, first_name, last_name, room_number, discharge_date
        FROM patients
    """)

    results = cursor.fetchall()
    conn.close()

    return results


def get_patient_by_name(first_name: str, last_name: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Recherche un patient par prénom ET nom.
    Retourne (patient_id, first_name, last_name, discharge_date) ou None.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT patient_id, first_name, last_name, discharge_date
        FROM patients
        WHERE LOWER(first_name) = LOWER(?) AND LOWER(last_name) = LOWER(?)
    """, (first_name, last_name))

    result = cursor.fetchone()
    conn.close()

    return result


def get_patient_medicines(patient_id: str) -> List[Tuple[str, str]]:
    """
    Retourne la liste de tous les médicaments d'un patient.
    Format: [(medicine_name, next_time), ...]
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT medicine_name, next_time
        FROM medications
        WHERE patient_id = ?
        ORDER BY next_time
    """, (patient_id,))

    results = cursor.fetchall()
    conn.close()

    return results


def get_medicine_next_time(patient_id: str, medicine_name: str) -> Optional[str]:
    """
    Retourne l'heure de la prochaine prise d'un médicament pour un patient donné.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT next_time
        FROM medications
        WHERE patient_id = ? AND LOWER(medicine_name) = LOWER(?)
    """, (patient_id, medicine_name))

    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0]
    return None


def get_patient_discharge_date(patient_id: str) -> Optional[str]:
    """
    Retourne la date de sortie prévue pour un patient.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT discharge_date
        FROM patients
        WHERE patient_id = ?
    """, (patient_id,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0]
    return None


def insert_alert(message: str, patient_id: str = "UNKNOWN") -> None:
    """
    Insère une alerte dans la base de données.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO alerts (patient_id, message)
        VALUES (?, ?)
    """, (patient_id, message))

    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────────────
# SESSION PATIENT ACTIF
# Partagée entre Rasa (écriture) et le pipeline vision (lecture).
# Utilise une table singleton (id = 1) dans medibot.db.
# ──────────────────────────────────────────────────────────────────────

def set_current_patient(patient_id: str, first_name: str, last_name: str) -> None:
    """
    Enregistre (ou met à jour) le patient actuellement identifié.
    Opération UPSERT sur la ligne id=1 de current_patient_session.
    """
    conn = get_connection()
    cursor = conn.cursor()
    # Créer la table si elle n'existe pas encore (tolérance migration)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS current_patient_session (
            id         INTEGER PRIMARY KEY DEFAULT 1,
            patient_id TEXT    NOT NULL,
            first_name TEXT,
            last_name  TEXT,
            identified_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO current_patient_session (id, patient_id, first_name, last_name, identified_at)
        VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            patient_id    = excluded.patient_id,
            first_name    = excluded.first_name,
            last_name     = excluded.last_name,
            identified_at = excluded.identified_at
    """, (patient_id, first_name, last_name))
    conn.commit()
    conn.close()


def get_current_patient() -> Optional[dict]:
    """
    Retourne le patient identifié en cours de session, ou None.
    La session est considérée valide pendant 4 heures.
    """
    from datetime import datetime, timedelta
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT patient_id, first_name, last_name, identified_at
            FROM current_patient_session WHERE id = 1
        """)
        row = cursor.fetchone()
    except Exception:
        row = None
    conn.close()

    if not row:
        return None
    patient_id, first_name, last_name, identified_at = row
    try:
        ident_time = datetime.fromisoformat(str(identified_at))
        if datetime.now() - ident_time > timedelta(hours=4):
            return None  # Session expirée
    except Exception:
        pass  # Si le parsing échoue, utiliser quand même
    return {
        "patient_id": patient_id,
        "first_name": first_name,
        "last_name": last_name,
        "identified_at": identified_at,
    }
