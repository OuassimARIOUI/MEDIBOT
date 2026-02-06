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
                    text=f"Bonjour {full_name}, je vous ai bien identifié."
                )
                
                # Stocker dans les slots (mémoire du bot)
                # Note: utter_ask_wellbeing sera appelé automatiquement après
                return [
                    SlotSet("first_name", db_first),
                    SlotSet("last_name", db_last),
                    SlotSet("patient_id", patient_id),
                    SlotSet("patient_full_name", full_name),
                    SlotSet("patient_identified", True)
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
# ACTION : Début de session - Robot parle en premier
# ======================================

class ActionSessionStart(Action):

    def name(self) -> Text:
        return "action_session_start"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # Le robot initie la conversation
        dispatcher.utter_message(
            text="Bonsoir, c'est Pepper, je viens prendre soin de vous. Quel est votre nom ?"
        )
        # Reset les slots de contexte
        return [
            SlotSet("asked_emergency", False),
            SlotSet("asked_activity", False)
        ]



# ======================================
# ACTION : Proposer activité (chanson/discuter)
# ======================================

class ActionProposeActivity(Action):

    def name(self) -> Text:
        return "action_propose_activity"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(
            text="Parfait. Souhaitez-vous que je vous chante quelque chose ou préférez-vous discuter ?"
        )
        # Marquer qu'on a posé la question activité
        return [
            SlotSet("asked_activity", True),
            SlotSet("asked_emergency", False)
        ]



# ======================================
# ACTION : Demander si besoin d'aide urgente
# ======================================

class ActionAskHelp(Action):

    def name(self) -> Text:
        return "action_ask_help"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(
            text="Je suis désolé de l'entendre. Souhaitez-vous que j'appelle l'équipe d'urgence ?"
        )
        # Marquer qu'on a posé la question urgence
        return [
            SlotSet("asked_emergency", True),
            SlotSet("asked_activity", False)
        ]



# ======================================
# ACTION : Gérer la réponse OUI
# ======================================

class ActionHandleAffirm(Action):

    def name(self) -> Text:
        return "action_handle_affirm"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        asked_emergency = tracker.get_slot("asked_emergency")
        patient_id = tracker.get_slot("patient_id")
        
        if asked_emergency:
            # Déclencher l'alerte niveau 2
            try:
                from actions.db_utils import insert_alert
                insert_alert(message="Urgence vitale potentielle - patient confirme", patient_id=patient_id or "UNKNOWN")
            except Exception as e:
                print(f"[ERREUR ALERT DB] {e}")
            
            dispatcher.utter_message(
                text="Je vais chercher quelqu'un tout de suite. Restez calme, je suis là."
            )
            # LED rouges sur Pepper (simulation)
            # ALLeds.fadeRGB("FaceLeds", 255, 0, 0, 1.0)
        
        return [
            SlotSet("asked_emergency", False),
            SlotSet("asked_activity", False)
        ]



# ======================================
# ACTION : Gérer la réponse NON
# ======================================

class ActionHandleDeny(Action):

    def name(self) -> Text:
        return "action_handle_deny"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        asked_emergency = tracker.get_slot("asked_emergency")
        asked_activity = tracker.get_slot("asked_activity")
        
        if asked_emergency:
            # Patient refuse l'urgence → proposer confort
            dispatcher.utter_message(
                text="Souhaitez-vous que je vous raconte une blague ou que je vous mette une musique apaisante ?"
            )
            return [
                SlotSet("asked_emergency", False),
                SlotSet("asked_activity", True)  # Réutilise pour blague/musique
            ]
        elif asked_activity:
            # Patient refuse l'activité → bonne nuit
            dispatcher.utter_message(
                text="Très bien, je vous laisse vous reposer. Bonne nuit !"
            )
            return [
                SlotSet("asked_emergency", False),
                SlotSet("asked_activity", False)
            ]
        else:
            # Contexte inconnu
            dispatcher.utter_message(
                text="D'accord. Puis-je faire autre chose pour vous ?"
            )
            return []



# ======================================
# ACTION : Jouer une chanson / musique
# ======================================

class ActionPlaySong(Action):

    def name(self) -> Text:
        return "action_play_song"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        import random
        
        patient_name = tracker.get_slot("patient_full_name")
        
        # Liste de musiques apaisantes connues
        songs = [
            {"title": "Clair de Lune", "artist": "Claude Debussy", "type": "classique"},
            {"title": "Gymnopédie No.1", "artist": "Erik Satie", "type": "classique"},
            {"title": "La Vie en Rose", "artist": "Édith Piaf", "type": "française"},
            {"title": "Imagine", "artist": "John Lennon", "type": "pop"},
            {"title": "What a Wonderful World", "artist": "Louis Armstrong", "type": "jazz"},
            {"title": "Hallelujah", "artist": "Leonard Cohen", "type": "pop"},
            {"title": "Ne me quitte pas", "artist": "Jacques Brel", "type": "française"},
            {"title": "Canon in D", "artist": "Johann Pachelbel", "type": "classique"},
            {"title": "Somewhere Over the Rainbow", "artist": "Israel Kamakawiwo'ole", "type": "relaxante"},
            {"title": "The Sound of Silence", "artist": "Simon & Garfunkel", "type": "folk"},
        ]
        
        song = random.choice(songs)
        
        # LED bleues activées (simulation)
        # Dans un vrai déploiement Pepper: ALLeds.fadeRGB("FaceLeds", 0, 0, 255, 1.0)
        
        if patient_name:
            dispatcher.utter_message(
                text=f"🎵 Je mets une musique pour vous, {patient_name}. "
                     f"Voici \"{song['title']}\" de {song['artist']}. "
                     f"Fermez les yeux et détendez-vous..."
            )
        else:
            dispatcher.utter_message(
                text=f"🎵 Voici \"{song['title']}\" de {song['artist']}. "
                     f"Fermez les yeux et détendez-vous..."
            )
        
        # Ici on déclencherait le behavior musique sur Pepper via NAOqi:
        # audio_player.playFile("/home/nao/musiques/" + song['file'])
        
        return []



# ======================================
# ACTION : Raconter une blague
# ======================================

class ActionTellJoke(Action):

    def name(self) -> Text:
        return "action_tell_joke"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        import random
        
        jokes = [
            # Blagues classiques
            "Pourquoi les plongeurs plongent-ils toujours en arrière ? Parce que sinon, ils tomberaient dans le bateau !",
            "Qu'est-ce qu'un canif ? Un petit fien !",
            "Qu'est-ce qui est jaune et qui attend ? Jonathan !",
            "Pourquoi les robots ne sont jamais fatigués ? Parce qu'ils font des siestes de recharge !",
            "Que dit un informaticien quand il s'ennuie ? Je m'octet !",
            
            # Blagues médicales (adaptées au contexte hospitalier)
            "Savez-vous pourquoi les infirmières sont toujours calmes ? Parce qu'elles ont des patients !",
            "Un docteur dit à son patient : 'J'ai une bonne et une mauvaise nouvelle.' Le patient : 'La bonne ?' Le docteur : 'Vous allez avoir une maladie qui porte votre nom.'",
            "Pourquoi les médecins portent-ils des masques ? Pour cacher qu'ils rigolent de vos blagues !",
            
            # Blagues sur les robots
            "Savez-vous ce que j'ai dit à mon chargeur ce matin ? Tu es le courant de ma vie !",
            "Pourquoi je ne raconte jamais de blagues sur les batteries ? Parce qu'elles sont toujours à plat !",
            "Un robot demande à un autre : 'Tu crois en l'après-recharge ?' L'autre répond : 'Oui, c'est électrisant !'",
            
            # Blagues générales
            "Deux escargots se battent. L'un dit à l'autre : 'Attention, je suis ceinture marron !'",
            "Qu'est-ce qu'un crocodile qui surveille un parking ? Un lézard garant !",
            "Pourquoi le chat n'aime pas l'eau ? Parce qu'il préfère être un chat sec !",
        ]
        
        joke = random.choice(jokes)
        
        patient_name = tracker.get_slot("patient_full_name")
        if patient_name:
            dispatcher.utter_message(
                text=f"Voici une blague pour vous, {patient_name} : {joke}"
            )
        else:
            dispatcher.utter_message(
                text=f"Voici une blague : {joke}"
            )
        
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
