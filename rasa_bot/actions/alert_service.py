
import requests
import json
from datetime import datetime
from typing import Optional, Dict
import os

# Import absolu pour compatibilité avec Rasa SDK
try:
    from db_utils import get_connection
except ImportError:
    from .db_utils import get_connection


# URL du dashboard Flask (à configurer)
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:5000/api/alerts")


def get_patient_info(patient_id: str) -> Optional[Dict[str, str]]:
    """
    Récupère les informations complètes d'un patient depuis la base de données.
    
    Args:
        patient_id: L'identifiant du patient
        
    Returns:
        Dictionnaire contenant les informations du patient ou None
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT patient_id, first_name, last_name, room_number
        FROM patients
        WHERE patient_id = ?
    """, (patient_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            "patient_id": result[0],
            "first_name": result[1],
            "last_name": result[2],
            "room_number": result[3] or "Non spécifié"
        }
    return None


def save_alert_to_db(patient_id: str, room_number: str, patient_name: str, message: str) -> int:
    """
    Enregistre l'alerte dans la base de données locale.
    
    Args:
        patient_id: ID du patient
        room_number: Numéro de chambre
        patient_name: Nom complet du patient
        message: Message d'urgence
        
    Returns:
        L'ID de l'alerte créée
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    alert_message = f"URGENCE - Chambre {room_number} - {patient_name}: {message}"
    
    cursor.execute("""
        INSERT INTO alerts (patient_id, message)
        VALUES (?, ?)
    """, (patient_id, alert_message))
    
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return alert_id


def send_alert_to_dashboard(
    patient_id: str,
    room_number: str,
    patient_name: str,
    message: str,
    alert_type: str = "URGENCE"
) -> bool:
    """
    Envoie une alerte d'urgence au dashboard Flask.
    
    Args:
        patient_id: L'identifiant du patient
        room_number: Le numéro de chambre
        patient_name: Le nom complet du patient
        message: Le message ou motif de l'alerte
        alert_type: Type d'alerte (par défaut "URGENCE")
        
    Returns:
        True si l'envoi a réussi, False sinon
    """
    alert_data = {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "room_number": room_number,
        "message": message,
        "alert_type": alert_type,
        "timestamp": datetime.now().isoformat(),
        "status": "ACTIVE"
    }
    
    try:
        # Envoyer l'alerte au dashboard Flask
        response = requests.post(
            DASHBOARD_URL,
            json=alert_data,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            print(f"✓ Alerte envoyée avec succès au dashboard pour {patient_name} (Chambre {room_number})")
            return True
        else:
            print(f"✗ Erreur lors de l'envoi de l'alerte: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"✗ Impossible de se connecter au dashboard à {DASHBOARD_URL}")
        print("  Le dashboard Flask n'est peut-être pas démarré.")
        return False
        
    except requests.exceptions.Timeout:
        print(f"✗ Timeout lors de l'envoi de l'alerte au dashboard")
        return False
        
    except Exception as e:
        print(f"✗ Erreur inattendue lors de l'envoi de l'alerte: {str(e)}")
        return False


def trigger_emergency_alert(
    patient_id: str,
    message: str,
    user_message: str = ""
) -> Dict[str, any]:
    """
    Fonction principale pour déclencher une alerte d'urgence.
    Cette fonction est appelée depuis actions.py quand l'intent 'emergency' est détecté.
    
    Args:
        patient_id: L'identifiant du patient
        message: Le message d'alerte à envoyer
        user_message: Le message original du patient (optionnel)
        
    Returns:
        Dictionnaire avec le statut de l'alerte et les détails
    """
    # Récupérer les informations du patient
    patient_info = get_patient_info(patient_id)
    
    if not patient_info:
        return {
            "success": False,
            "error": "Patient non trouvé",
            "alert_id": None
        }
    
    patient_name = f"{patient_info['first_name']} {patient_info['last_name']}"
    room_number = patient_info['room_number']
    
    # Construire le message complet
    full_message = message
    if user_message:
        full_message = f"{message} - Patient dit: '{user_message}'"
    
    # 1. Sauvegarder l'alerte dans la base de données locale
    alert_id = save_alert_to_db(patient_id, room_number, patient_name, full_message)
    
    # 2. Envoyer l'alerte au dashboard Flask
    dashboard_success = send_alert_to_dashboard(
        patient_id=patient_id,
        room_number=room_number,
        patient_name=patient_name,
        message=full_message,
        alert_type="URGENCE"
    )
    
    return {
        "success": True,
        "alert_id": alert_id,
        "dashboard_sent": dashboard_success,
        "patient_name": patient_name,
        "room_number": room_number,
        "message": full_message
    }


def trigger_nurse_call(patient_id: str, reason: str = "Demande d'assistance") -> Dict[str, any]:
    """
    Fonction pour appeler une infirmière (niveau d'urgence moindre).
    
    Args:
        patient_id: L'identifiant du patient
        reason: La raison de l'appel
        
    Returns:
        Dictionnaire avec le statut de l'appel
    """
    patient_info = get_patient_info(patient_id)
    
    if not patient_info:
        return {
            "success": False,
            "error": "Patient non trouvé"
        }
    
    patient_name = f"{patient_info['first_name']} {patient_info['last_name']}"
    room_number = patient_info['room_number']
    
    # Sauvegarder dans la DB
    alert_id = save_alert_to_db(patient_id, room_number, patient_name, reason)
    
    # Envoyer au dashboard avec type "APPEL_INFIRMIERE"
    dashboard_success = send_alert_to_dashboard(
        patient_id=patient_id,
        room_number=room_number,
        patient_name=patient_name,
        message=reason,
        alert_type="APPEL_INFIRMIERE"
    )
    
    return {
        "success": True,
        "alert_id": alert_id,
        "dashboard_sent": dashboard_success,
        "patient_name": patient_name,
        "room_number": room_number
    }
