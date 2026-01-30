from typing import Any, Text, Dict, List
from datetime import datetime
import sqlite3

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


# ACTION : Donner l'heure actuelle

class ActionGetTime(Action):

    def name(self) -> Text:
        return "action_get_time"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        now = datetime.now().strftime("%H:%M")
        dispatcher.utter_message(text=f"Il est actuellement {now}.")
        return []


# ACTION : Donner la date actuelle

class ActionGetDate(Action):

    def name(self) -> Text:
        return "action_get_date"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        today = datetime.now().strftime("%d/%m/%Y")
        dispatcher.utter_message(text=f"Nous sommes le {today}.")
        return []


# ACTION : Vérifier le médicament (SQLite factice)

class ActionGetMedicine(Action):

    def name(self) -> Text:
        return "action_get_medicine"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # Récupération de l'entité medicine
        medicine = next(tracker.get_latest_entity_values("medicine"), None)

        if not medicine:
            dispatcher.utter_message(
                text="Pouvez-vous me dire le nom du médicament, s'il vous plaît ?"
            )
            return []

        # Connexion SQLite factice
        conn = sqlite3.connect("medibot_medicines.db")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                name TEXT,
                next_time TEXT
            )
        """)

        # Données factices si base vide
        cursor.execute("SELECT COUNT(*) FROM medicines")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO medicines VALUES (?, ?)",
                ("doliprane", "22:00")
            )
            cursor.execute(
                "INSERT INTO medicines VALUES (?, ?)",
                ("insuline", "23:30")
            )
            conn.commit()

        cursor.execute(
            "SELECT next_time FROM medicines WHERE name = ?",
            (medicine.lower(),)
        )
        result = cursor.fetchone()

        if result:
            dispatcher.utter_message(
                text=f"Votre prochaine prise de {medicine} est prévue à {result[0]}."
            )
        else:
            dispatcher.utter_message(
                text=f"Je n'ai pas trouvé d'information pour le médicament {medicine}."
            )

        conn.close()
        return []


# ACTION : Déclencher une alerte (Sprint 01 : log)

class ActionTriggerAlert(Action):

    def name(self) -> Text:
        return "action_trigger_alert"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        print("🚨 ALERTE MEDIBOT 🚨")
        print(f"Heure : {datetime.now()}")
        print(f"Message patient : {tracker.latest_message.get('text')}")

        dispatcher.utter_message(
            text="Une alerte a été envoyée. Une infirmière va arriver."
        )

        return []
