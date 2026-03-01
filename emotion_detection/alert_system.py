import requests
import datetime

class AlertSystem:
    def __init__(self, dashboard_url="http://localhost:5000/alerts"):
        self.dashboard_url = dashboard_url

    def send_alert(self, level, reason, patient_id="Chambre_102"):
        """
        Envoie une alerte selon les niveaux du cahier des charges :
        Niveau 1: à surveiller | Niveau 2: urgence vitale [cite: 112]
        """
        payload = {
            "timestamp": datetime.datetime.now().isoformat(),
            "patient_id": patient_id,
            "priority": level,
            "reason": reason,
            "status": "pending"
        }
        
        print(f"--- [ALERTE NIVEAU {level}] : {reason} ---")
        
        try:
            # Simulation d'envoi au dashboard Flask [cite: 119, 145]
            response = requests.post(self.dashboard_url, json=payload, timeout=2)
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            print("⚠️ Mode dégradé : Dashboard injoignable. Alerte loguée localement.") [cite: 120, 138]
            return False

# Exemple d'usage pour vos tests
# alert = AlertSystem()
# alert.send_alert(level=2, reason="Absence de respiration détectée") [cite: 214]