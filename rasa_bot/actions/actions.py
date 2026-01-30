from typing import Any, Text, Dict, List
from datetime import datetime
import sqlite3

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher


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


# ACTION : Vérifier un médicament (SQLite réel)

class ActionGetMedicine(Action):

    def name(self) -> Text:
        return "action_get_medicine"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # Récupération de l'entité "medicine"
        medicine = next(tracker.get_latest_entity_values("medicine"), None)

        if not medicine:
            dispatcher.utter_message(
                text="Pouvez-vous me dire le nom du médicament, s'il vous plaît ?"
            )
            return []

        try:
            conn = sqlite3.connect("medibot.db")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT next_time
                FROM medications
                WHERE LOWER(medicine_name) = LOWER(?)
            """, (medicine,))

            result = cursor.fetchone()
            conn.close()

            if result:
                dispatcher.utter_message(
                    text=f"Votre prochaine prise de {medicine} est prévue à {result[0]}."
                )
            else:
                dispatcher.utter_message(
                    text=f"Je n'ai pas trouvé d'information pour le médicament {medicine}."
                )

        except Exception as e:
            dispatcher.utter_message(
                text="Une erreur est survenue lors de la consultation des médicaments."
            )
            print(f"[ERREUR DB] {e}")

        return []


# ACTION : Déclencher une alerte (Sprint 01)

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
