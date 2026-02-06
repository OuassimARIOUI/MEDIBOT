from typing import Any, Text, Dict, List
from datetime import datetime
import re

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from actions.db_utils import (
    get_medicine_next_time,
    insert_alert,
    get_patient_by_name,
    get_patient_medicines,
    get_patient_discharge_date,
    get_all_patients
)



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



# ACTION : Donner la date actuelle.

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




# ACTION : Identifier le patient (DYNAMIQUE DEPUIS LA DB)

class ActionIdentifyPatient(Action):

    def name(self) -> Text:
        return "action_identify_patient"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # Récupérer le message de l'utilisateur
        user_message = tracker.latest_message.get('text', '').lower()
        
        # Nettoyer le message (enlever les phrases d'intro)
        patterns_to_remove = [
            r"^je suis ",
            r"^je m'appelle ",
            r"^mon nom est ",
            r"^c'est ",
            r"^moi c'est ",
            r"^bonjour je suis ",
            r"^bonsoir je suis ",
            r"monsieur ",
            r"madame ",
        ]
        
        cleaned_message = user_message
        for pattern in patterns_to_remove:
            cleaned_message = re.sub(pattern, '', cleaned_message, flags=re.IGNORECASE)
        
        # Extraire les mots (potentiellement prénom et nom)
        words = cleaned_message.strip().split()
        
        if len(words) < 2:
            dispatcher.utter_message(
                text="Je n'ai pas bien compris. Dites-moi votre prénom et nom, s'il vous plaît."
            )
            return []

        try:
            # Récupérer tous les patients de la DB
            all_patients = get_all_patients()
            
            if not all_patients:
                dispatcher.utter_message(
                    text="Désolé, je n'ai pas accès à la liste des patients pour le moment."
                )
                return []
            
            # Chercher une correspondance dans la DB
            found_patient = None
            
            for patient in all_patients:
                patient_id, db_first, db_last, room, discharge = patient
                db_first_lower = db_first.lower()
                db_last_lower = db_last.lower()
                
                # Vérifier si le prénom ET le nom sont dans les mots (dans n'importe quel ordre)
                words_lower = [w.lower() for w in words]
                
                if db_first_lower in words_lower and db_last_lower in words_lower:
                    found_patient = (patient_id, db_first, db_last, discharge)
                    break
            
            if found_patient:
                patient_id, db_first, db_last, discharge_date = found_patient
                full_name = f"{db_first} {db_last}"
                
                dispatcher.utter_message(
                    text=f"Bonjour {full_name}, je vous ai identifié. Comment puis-je vous aider ce soir ?"
                )
                
                # Stocker dans les slots (mémoire du bot)
                return [
                    SlotSet("first_name", db_first),
                    SlotSet("last_name", db_last),
                    SlotSet("patient_id", patient_id),
                    SlotSet("patient_full_name", full_name)
                ]
            else:
                # Aucun patient trouvé
                dispatcher.utter_message(
                    text=f"Désolé, je ne trouve pas de patient correspondant à '{' '.join(words)}' dans mes données."
                )
                return []

        except Exception as e:
            dispatcher.utter_message(
                text="Une erreur est survenue lors de votre identification."
            )
            print(f"[ERREUR DB IDENTIFICATION] {e}")
            return []



# ======================================
# ACTION : Date de sortie (NOUVEAU)
# ======================================

class ActionGetDischarge(Action):

    def name(self) -> Text:
        return "action_get_discharge"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        patient_id = tracker.get_slot("patient_id")
        
        # Vérifier identification
        if not patient_id:
            dispatcher.utter_message(response="utter_not_identified")
            return []

        try:
            discharge_date = get_patient_discharge_date(patient_id)
            
            if discharge_date:
                dispatcher.utter_message(
                    text=f"Votre date de sortie prévue est le {discharge_date}."
                )
            else:
                dispatcher.utter_message(
                    text="Je n'ai pas d'information sur votre date de sortie pour le moment."
                )

        except Exception as e:
            dispatcher.utter_message(
                text="Une erreur est survenue lors de la consultation de votre date de sortie."
            )
            print(f"[ERREUR DB DISCHARGE] {e}")

        return []



# ======================================
# ACTION : Vérifier médicament (OPTIMISÉE)
# ======================================

class ActionGetMedicine(Action):

    def name(self) -> Text:
        return "action_get_medicine"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        patient_id = tracker.get_slot("patient_id")
        medicine = next(tracker.get_latest_entity_values("medicine"), None)

        # Vérifier identification
        if not patient_id:
            dispatcher.utter_message(response="utter_not_identified")
            return []

        # Si médicament spécifique demandé
        if medicine:
            try:
                next_time = get_medicine_next_time(patient_id, medicine)

                if next_time:
                    dispatcher.utter_message(
                        text=f"Votre prochaine prise de {medicine} est prévue à {next_time}."
                    )
                else:
                    dispatcher.utter_message(
                        text=f"Je n'ai pas trouvé le médicament {medicine} dans votre traitement."
                    )

            except Exception as e:
                dispatcher.utter_message(
                    text="Une erreur est survenue lors de la consultation."
                )
                print(f"[ERREUR DB MEDICINE] {e}")
        
        # Sinon, afficher tous les médicaments
        else:
            try:
                medicines = get_patient_medicines(patient_id)
                
                if medicines:
                    msg = "Voici votre traitement :\n"
                    for med_name, next_time in medicines:
                        msg += f"• {med_name} à {next_time}\n"
                    dispatcher.utter_message(text=msg)
                else:
                    dispatcher.utter_message(
                        text="Vous n'avez pas de médicaments enregistrés."
                    )
            except Exception as e:
                dispatcher.utter_message(
                    text="Une erreur est survenue lors de la consultation."
                )
                print(f"[ERREUR DB MEDICINES] {e}")

        return []



# ACTION : Déclencher une alerte 

class ActionTriggerAlert(Action):

    def name(self) -> Text:
        return "action_trigger_alert"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        message = tracker.latest_message.get("text")
        
        # Récupérer le patient_id depuis les slots (si identifié)
        patient_id = tracker.get_slot("patient_id")
        if not patient_id:
            patient_id = "UNKNOWN"

        try:
            insert_alert(message=message, patient_id=patient_id)
        except Exception as e:
            print(f"[ERREUR ALERT DB] {e}")

        # Message personnalisé selon identification
        patient_name = tracker.get_slot("patient_full_name")
        if patient_name:
            dispatcher.utter_message(
                text=f"{patient_name}, une alerte a été envoyée. Une infirmière va arriver immédiatement."
            )
        else:
            dispatcher.utter_message(
                text="Une alerte a été envoyée. Une infirmière va arriver."
            )

        return []
