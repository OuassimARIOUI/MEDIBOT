import sqlite3
from typing import Optional, Tuple, List
import os
from pathlib import Path

# Chemin absolu vers la base de données
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "database" / "medibot.db"))


def get_connection():
    """
    Crée et retourne une connexion SQLite.
    """
    return sqlite3.connect(DB_PATH)


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
