# Service d'Alertes MediBot 🚨

## Description

Le fichier `alert_service.py` gère le système d'alertes d'urgence du robot MediBot. Il est déclenché automatiquement lorsque le robot détecte l'intent **`emergency`** dans la conversation avec un patient.

## Fonctionnalités

### 1. Détection automatique d'urgence
Quand un patient dit des phrases comme :
- "C'est urgent !"
- "J'ai besoin d'aide tout de suite"
- "Je n'arrive pas à respirer"
- "Aidez-moi"
- "SOS"

Le robot identifie automatiquement l'intent `emergency` et déclenche une alerte.

### 2. Collecte des informations
Le service récupère automatiquement :
- ✅ **Numéro de chambre** du patient
- ✅ **Nom complet** (prénom + nom)
- ✅ **Message d'urgence** (ce que le patient a dit)
- ✅ **Horodatage** (date et heure de l'alerte)

### 3. Double enregistrement
Chaque alerte est :
1. **Sauvegardée** dans la base de données locale SQLite
2. **Envoyée** au dashboard Flask via API REST

## Structure du code

### Fonctions principales

#### `trigger_emergency_alert(patient_id, message, user_message="")`
Fonction principale appelée lors d'une urgence.

**Paramètres :**
- `patient_id` : ID du patient identifié
- `message` : Message d'alerte générique
- `user_message` : Message exact dit par le patient (optionnel)

**Retour :**
```python
{
    "success": True,
    "alert_id": 123,
    "dashboard_sent": True,
    "patient_name": "Jean Dupont",
    "room_number": "203",
    "message": "Urgence détectée - Patient dit: 'J'ai très mal'"
}
```

#### `trigger_nurse_call(patient_id, reason="")`
Fonction pour appeler une infirmière (urgence moindre).

#### `send_alert_to_dashboard(patient_id, room_number, patient_name, message, alert_type)`
Envoie l'alerte au dashboard Flask via HTTP POST.

**Format JSON envoyé :**
```json
{
    "patient_id": "PAT001",
    "patient_name": "Jean Dupont",
    "room_number": "203",
    "message": "Urgence - Patient dit: 'J'ai très mal'",
    "alert_type": "URGENCE",
    "timestamp": "2026-02-02T22:30:45.123456",
    "status": "ACTIVE"
}
```

## Configuration

### Variables d'environnement

Créez un fichier `.env` à la racine du projet :

```bash
DASHBOARD_URL=http://localhost:5000/api/alerts
DB_PATH=database/medibot.db
```

### Endpoint du Dashboard Flask

Le dashboard doit exposer un endpoint POST pour recevoir les alertes :

**URL :** `http://localhost:5000/api/alerts`  
**Méthode :** POST  
**Content-Type :** application/json

**Corps de la requête attendu :**
```json
{
    "patient_id": "string",
    "patient_name": "string",
    "room_number": "string",
    "message": "string",
    "alert_type": "URGENCE" | "APPEL_INFIRMIERE",
    "timestamp": "ISO 8601 datetime",
    "status": "ACTIVE"
}
```

## Utilisation dans Rasa

### Dans `actions.py`

```python
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from .alert_service import trigger_emergency_alert

class ActionTriggerAlert(Action):
    def name(self) -> str:
        return "action_trigger_alert"
    
    def run(self, dispatcher, tracker, domain):
        # Récupérer l'ID du patient depuis les slots
        patient_id = tracker.get_slot("patient_id")
        
        # Récupérer le dernier message du patient
        user_message = tracker.latest_message.get('text', '')
        
        if patient_id:
            # Déclencher l'alerte
            result = trigger_emergency_alert(
                patient_id=patient_id,
                message="Urgence détectée",
                user_message=user_message
            )
            
            if result['success']:
                dispatcher.utter_message(
                    text=f"🚨 Alerte envoyée ! Une équipe médicale va arriver immédiatement dans votre chambre ({result['room_number']})."
                )
            else:
                dispatcher.utter_message(
                    text="Je ne peux pas envoyer l'alerte pour le moment, mais j'appelle du renfort !"
                )
        else:
            dispatcher.utter_message(
                text="Je ne vous ai pas encore identifié. Quel est votre nom ?"
            )
        
        return []
```

## Types d'alertes

| Type d'alerte | Priorité | Déclenchement |
|---------------|----------|---------------|
| `URGENCE` | 🔴 Haute | Intent `emergency` |
| `APPEL_INFIRMIERE` | 🟡 Moyenne | Intent `ask_nurse` + patient mal |

## Gestion des erreurs

Le service gère automatiquement :
- ✅ Dashboard Flask hors ligne (message d'erreur mais sauvegarde en DB)
- ✅ Patient non trouvé
- ✅ Timeouts réseau
- ✅ Erreurs de connexion

## Base de données

Les alertes sont enregistrées dans la table `alerts` :

```sql
CREATE TABLE alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT,
    message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);
```

## Tests

Pour tester le service :

```python
from alert_service import trigger_emergency_alert

# Test avec un patient existant
result = trigger_emergency_alert(
    patient_id="PAT001",
    message="Test d'urgence",
    user_message="J'ai très mal"
)

print(result)
```

## Prochaines étapes

Une fois ce fichier en place, vous devrez :

1. ✅ **Créer le dashboard Flask** avec l'endpoint `/api/alerts`
2. ✅ **Mettre à jour `actions.py`** pour utiliser `trigger_emergency_alert()`
3. ✅ **Ajouter des règles** dans `rules.yml` pour l'intent `emergency`
4. ✅ **Tester** le flux complet

## Notes importantes

⚠️ **Sécurité** : En production, utilisez HTTPS et authentifiez les requêtes  
⚠️ **Performance** : Le timeout HTTP est de 5 secondes pour ne pas bloquer le chatbot  
⚠️ **Fiabilité** : Même si le dashboard est hors ligne, l'alerte est sauvegardée en DB locale
