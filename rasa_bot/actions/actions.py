from typing import Any, Text, Dict, List
from datetime import datetime
import re

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

# Import absolu pour compatibilité avec Rasa SDK
try:
    from db_utils import (
        get_medicine_next_time,
        insert_alert,
        get_patient_by_name,
        get_patient_medicines,
        get_patient_discharge_date,
        get_all_patients
    )
    from alert_service import trigger_emergency_alert, trigger_nurse_call
except ImportError:
    # Fallback pour imports relatifs
    from .db_utils import (
        get_medicine_next_time,
        insert_alert,
        get_patient_by_name,
        get_patient_medicines,
        get_patient_discharge_date,
        get_all_patients
    )
    from .alert_service import trigger_emergency_alert, trigger_nurse_call


# =================================================
# DICTIONNAIRE DE NORMALISATION DES PRÉNOMS
# =================================================
# Gère les différentes transcriptions Whisper
# Toutes les variantes sont mappées vers le prénom officiel
# =================================================

PRENOM_SYNONYMS = {
    # Variantes de Ouassim
    "wasim": "ouassim",
    "wassim": "ouassim",
    "ouassim": "ouassim",
    "ouaassim": "ouassim",
    
    # Variantes de Asmaa
    "asma": "asmaa",
    "assma": "asmaa",
    "asmaa": "asmaa",
}

def normalize_name(name: str) -> str:
    """
    Normalise un prénom en convertissant les variantes vers le nom officiel.
    
    Args:
        name: Le prénom à normaliser (peut être une variante)
    
    Returns:
        Le prénom normalisé (ou le nom original si pas de correspondance)
    """
    name_lower = name.lower().strip()
    return PRENOM_SYNONYMS.get(name_lower, name_lower)


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
        
        # Nettoyer le message (enlever les phrases d'intro et mots courants)
        patterns_to_remove = [
            r"^bonjour\s*,?\s*",      # "bonjour" ou "bonjour,"
            r"^bonsoir\s*,?\s*",      # "bonsoir" ou "bonsoir,"
            r"^salut\s*,?\s*",        # "salut" ou "salut,"
            r"^je suis\s+",
            r"^je m'appelle\s+",
            r"^mon nom est\s+",
            r"^c'est\s+",
            r"^moi c'est\s+",
            r"\s*monsieur\s*",
            r"\s*madame\s*",
            r"\.$",                    # Point final
            r"\s+$",                   # Espaces de fin
        ]
        
        cleaned_message = user_message
        for pattern in patterns_to_remove:
            cleaned_message = re.sub(pattern, '', cleaned_message, flags=re.IGNORECASE)
        
        cleaned_message = cleaned_message.strip()
        
        # Extraire les mots
        words = [w.strip() for w in cleaned_message.split() if w.strip()]
        
        if len(words) < 1:
            dispatcher.utter_message(
                text="Je n'ai pas bien compris. Dites-moi votre prénom, s'il vous plaît."
            )
            return []
        
        print(f"[IDENTIFICATION] Message nettoyé: '{cleaned_message}'")
        print(f"[IDENTIFICATION] Mots extraits: {words}")

        try:
            # Récupérer tous les patients de la DB
            all_patients = get_all_patients()
            
            if not all_patients:
                dispatcher.utter_message(
                    text="Désolé, je n'ai pas accès à la liste des patients pour le moment."
                )
                return []
            
            # Chercher une correspondance dans la DB (RECHERCHE PAR PRÉNOM)
            found_patient = None
            
            for patient in all_patients:
                patient_id, db_first, db_last, room, discharge = patient
                
                # Normaliser le prénom de la DB
                db_first_normalized = normalize_name(db_first.lower())
                
                print(f"[IDENTIFICATION] Test patient: {db_first} (normalisé: {db_first_normalized})")
                
                # Normaliser et tester chaque mot du message
                for word in words:
                    word_normalized = normalize_name(word.lower())
                    
                    print(f"[IDENTIFICATION]   Comparaison: '{word}' (normalisé: '{word_normalized}') == '{db_first_normalized}' ?")
                    
                    # Si un mot correspond au prénom normalisé → TROUVÉ !
                    if word_normalized == db_first_normalized:
                        found_patient = (patient_id, db_first, db_last, discharge)
                        print(f"[IDENTIFICATION] ✅ TROUVÉ: {db_first} {db_last} (ID: {patient_id})")
                        break
                
                if found_patient:
                    break
            
            if found_patient:
                patient_id, db_first, db_last, discharge_date = found_patient
                full_name = f"{db_first} {db_last}"
                
                dispatcher.utter_message(
                    text=f"Parfait ! Je vous ai bien identifié, {full_name}."
                )
                
                # Stocker dans les slots (mémoire du bot)
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
            SlotSet("asked_activity", False),
            SlotSet("emergency_handled", False)
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

        # Vérifier si on a déjà posé la question
        already_asked = tracker.get_slot("asked_activity")
        if already_asked:
            return []

        dispatcher.utter_message(
            text="Parfait. Souhaitez-vous que je vous chante une chanson (je connais des chansons françaises traditionnelles) ou préférez-vous discuter ?"
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

        # Vérifier si l'urgence a déjà été gérée
        emergency_handled = tracker.get_slot("emergency_handled")
        if emergency_handled:
            # Ne pas redemander, juste écouter
            return []
        
        # Vérifier si on a déjà posé la question
        already_asked = tracker.get_slot("asked_emergency")
        if already_asked:
            # Ne pas redemander
            return []

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
        asked_activity = tracker.get_slot("asked_activity")
        patient_id = tracker.get_slot("patient_id")
        patient_name = tracker.get_slot("patient_full_name")
        
        if asked_emergency:
            # Déclencher l'alerte niveau 2
            try:
                from .db_utils import insert_alert
                insert_alert(message="Urgence vitale potentielle - patient confirme", patient_id=patient_id or "UNKNOWN")
            except Exception as e:
                print(f"[ERREUR ALERT DB] {e}")
            
            if patient_name:
                dispatcher.utter_message(
                    text=f"{patient_name}, je vais chercher quelqu'un tout de suite. Restez calme, je reste près de vous."
                )
            else:
                dispatcher.utter_message(
                    text="Je vais chercher quelqu'un tout de suite. Restez calme, je reste près de vous."
                )
            
            # Marquer la conversation comme terminée
            return [
                SlotSet("asked_emergency", False),
                SlotSet("asked_activity", False),
                SlotSet("emergency_handled", True)
            ]
        
        elif asked_activity:
            # Le patient dit oui à activité (chanson/discuter) mais on a besoin de plus de précision
            dispatcher.utter_message(
                text="Préférez-vous une chanson ou discuter ?"
            )
            return []
        
        else:
            # Contexte inconnu - demander clarification
            dispatcher.utter_message(
                text="D'accord. Que puis-je faire pour vous ?"
            )
            return []



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
# ACTION : Chanter une chanson (voix Pepper + gestes)
# ======================================

class ActionPlaySong(Action):

    def name(self) -> Text:
        return "action_play_song"

    # ------------------------------------------------------------------
    # Chansons que Pepper chantera avec sa voix ALTextToSpeech.
    # "lyrics" = ce que Pepper prononce à voix haute (TTS).
    # "intro"  = phrase dite AVANT de chanter.
    # "outro"  = phrase dite APRÈS avoir chanté.
    # "emotion"= couleur LEDs pendant la chanson.
    # "gesture"= geste Pepper avant de chanter.
    # ------------------------------------------------------------------
    SONGS = [
        {
            "title": "Au Clair de la Lune",
            "artist": "Chanson traditionnelle française",
            "intro": "Je vais vous chanter Au clair de la lune.",
            "lyrics": (
                "Au clair de la lune, mon ami Pierrot, "
                "prête-moi ta plume pour écrire un mot. "
                "Ma chandelle est morte, je n'ai plus de feu. "
                "Ouvre-moi ta porte, pour l'amour de Dieu."
            ),
            "outro": "J'espère que cette berceuse vous apporte un peu de sérénité.",
            "emotion": "calm",
            "gesture": "animations/Stand/Emotions/Neutral/Calm_1",
        },
        {
            "title": "Frère Jacques",
            "artist": "Chanson traditionnelle française",
            "intro": "Voici Frère Jacques, une chanson qui réchauffe le cœur.",
            "lyrics": (
                "Frère Jacques, Frère Jacques, "
                "dormez-vous ? dormez-vous ? "
                "Sonnez les matines ! Sonnez les matines ! "
                "Din din don, din din don."
            ),
            "outro": "Voilà, je vous souhaite une bonne nuit comme Frère Jacques !",
            "emotion": "happy",
            "gesture": "animations/Stand/Gestures/Yes_1",
        },
        {
            "title": "La Vie en Rose",
            "artist": "Édith Piaf",
            "intro": "Je vais interpréter un extrait de La Vie en Rose, d'Édith Piaf.",
            "lyrics": (
                "Des yeux qui font baisser les miens, "
                "un rire qui se perd sur sa bouche, "
                "voilà le portrait sans retouches "
                "de l'homme auquel j'appartiens. "
                "Quand il me prend dans ses bras, "
                "il me parle tout bas, "
                "je vois la vie en rose."
            ),
            "outro": "Édith Piaf avait une voix magnifique. J'espère avoir rendu hommage à cette belle chanson.",
            "emotion": "happy",
            "gesture": "animations/Stand/Emotions/Positive/Happy_4",
        },
        {
            "title": "Douce France",
            "artist": "Charles Trenet",
            "intro": "Je vais vous chanter Douce France de Charles Trenet.",
            "lyrics": (
                "Douce France, cher pays de mon enfance, "
                "bercée de tendre insouciance, "
                "je t'ai gardée dans mon cœur. "
                "Mon village au clocher, aux maisons fleuries, "
                "ô douce France."
            ),
            "outro": "Une belle chanson pour penser à des souvenirs doux.",
            "emotion": "calm",
            "gesture": "animations/Stand/Emotions/Neutral/Calm_1",
        },
        {
            "title": "Promenons-nous dans les bois",
            "artist": "Chanson traditionnelle française",
            "intro": "Je vais vous chanter Promenons-nous dans les bois.",
            "lyrics": (
                "Promenons-nous dans les bois, "
                "pendant que le loup n'y est pas. "
                "Si le loup y était, "
                "il nous mangerait. "
                "Mais comme il n'y est pas, "
                "il nous mangera pas !"
            ),
            "outro": "Voilà ! Une chanson pleine de vivacité pour vous redonner le sourire.",
            "emotion": "happy",
            "gesture": "animations/Stand/Gestures/Hey_1",
        },
    ]

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        import random
        import os
        import sys

        patient_name = tracker.get_slot("patient_full_name")
        song = random.choice(self.SONGS)

        # ------------------------------------------------------------------
        # 1. Message texte au dashboard / frontend (toujours visible)
        # ------------------------------------------------------------------
        first_name = patient_name.split()[0] if patient_name else None

        if first_name:
            dispatcher.utter_message(
                text=(
                    f"🎵 Très bien {first_name}, je vais vous chanter "
                    f"\"{song['title']}\" de {song['artist']}. "
                    f"Installez-vous confortablement..."
                )
            )
        else:
            dispatcher.utter_message(
                text=(
                    f"🎵 Je vais vous chanter \"{song['title']}\" "
                    f"de {song['artist']}. "
                    f"Installez-vous confortablement..."
                )
            )

        # ------------------------------------------------------------------
        # 2. Commandes Pepper (TTS + gestes + LEDs)
        # ------------------------------------------------------------------
        try:
            # Récupérer la session Pepper si disponible
            pepper_ip = os.getenv("PEPPER_IP")
            pepper_port = int(os.getenv("PEPPER_PORT", "9559"))

            if pepper_ip:
                import qi

                session = qi.Session()
                session.connect(f"tcp://{pepper_ip}:{pepper_port}")

                # === GESTE : mouvement avant de chanter ===
                try:
                    behavior_service = session.service("ALBehaviorManager")
                    if behavior_service.isBehaviorInstalled(song["gesture"]):
                        behavior_service.runBehavior(song["gesture"])
                except Exception as e:
                    print(f"[CHANSON] Geste non disponible ({e}), poursuite...")

                # === LEDs : couleur selon l'émotion ===
                try:
                    leds = session.service("ALLeds")
                    emotion_colors = {
                        "calm":  (0.0, 0.4, 1.0),   # Bleu
                        "happy": (0.0, 0.9, 0.3),   # Vert
                    }
                    r, g, b = emotion_colors.get(song["emotion"], (1.0, 1.0, 1.0))
                    leds.fadeRGB("FaceLeds", r, g, b, 1.0)
                except Exception as e:
                    print(f"[CHANSON] LEDs non disponibles ({e}), poursuite...")

                # === TTS : Pepper parle (intro + paroles + outro) ===
                tts = session.service("ALTextToSpeech")
                tts.setLanguage("French")
                tts.setParameter("speed", 80)   # Légèrement plus lent pour chanter
                tts.setParameter("volume", 0.85)

                # Intro
                tts.say(song["intro"])

                # Geste de balancement pendant la chanson (idle_motion)
                try:
                    motion = session.service("ALMotion")
                    # Optioannel : léger mouvement de tête pendnat les paroles
                    motion.setStiffnesses("Head", 1.0)
                except Exception:
                    pass

                # Paroles chantées (Pepper les dit d'une voix douce)
                tts.say(song["lyrics"])

                # Outro
                tts.say(song["outro"])

                # LEDs : retour à neutral blanc
                try:
                    leds.fadeRGB("FaceLeds", 1.0, 1.0, 1.0, 2.0)
                except Exception:
                    pass

                print(f"[CHANSON] ✅ Pepper a chanté : {song['title']}")
            else:
                print(f"[CHANSON] Mode simulation – PEPPER_IP non défini.")
                print(f"[CHANSON] Chanson sélectionnée : {song['title']} ({song['artist']})")
                print(f"[CHANSON] Paroles : {song['lyrics']}")

        except ImportError:
            print("[CHANSON] Module 'qi' non disponible – mode simulation PC.")
            print(f"[CHANSON] Chanson : {song['title']} | Paroles : {song['lyrics']}")

        except Exception as e:
            print(f"[CHANSON] Erreur Pepper : {e}")

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

        user_message = tracker.latest_message.get("text")
        
        # Récupérer le patient_id depuis les slots (si identifié)
        patient_id = tracker.get_slot("patient_id")
        patient_name = tracker.get_slot("patient_full_name")
        
        if not patient_id:
            # Patient non identifié, utiliser l'ancienne méthode
            print("[ALERTE] Patient non identifié, alerte basique envoyée")
            try:
                insert_alert(message=user_message, patient_id="UNKNOWN")
                dispatcher.utter_message(
                    text="Une alerte a été envoyée. Une infirmière va arriver."
                )
            except Exception as e:
                print(f"[ERREUR ALERT DB] {e}")
                dispatcher.utter_message(
                    text="Désolé, je n'ai pas pu envoyer l'alerte. Appelez directement l'infirmière."
                )
            return []

        # Patient identifié, utiliser le service complet avec notification dashboard
        try:
            result = trigger_emergency_alert(
                patient_id=patient_id,
                message="ALERTE URGENCE",
                user_message=user_message
            )
            
            if result["success"]:
                print(f"[ALERTE] ✅ Envoyée pour {result['patient_name']} - Chambre {result['room_number']}")
                print(f"[ALERTE] Dashboard: {'✅ Envoyé' if result['dashboard_sent'] else '❌ Échec'}")
                
                dispatcher.utter_message(
                    text=f"{patient_name}, une alerte d'urgence a été envoyée au personnel médical. Une infirmière va arriver immédiatement. Restez calme."
                )
            else:
                print(f"[ALERTE] ❌ Échec: {result.get('error')}")
                dispatcher.utter_message(
                    text="Une erreur s'est produite. Je vais quand même alerter le personnel."
                )
                # Fallback sur insert_alert
                insert_alert(message=user_message, patient_id=patient_id)
                
        except Exception as e:
            print(f"[ERREUR ALERT SYSTÈME] {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback : au moins enregistrer dans la DB
            try:
                insert_alert(message=user_message, patient_id=patient_id)
                dispatcher.utter_message(
                    text="Une alerte a été enregistrée. Le personnel médical va arriver."
                )
            except:
                dispatcher.utter_message(
                    text="Problème technique. Appelez directement l'infirmière."
                )

        return []


# ACTION : Appeler une infirmière (non urgent)

class ActionCallNurse(Action):
    """
    Action pour appeler une infirmière de manière non urgente.
    Déclenche une alerte de niveau BAS (severity: low) avec bordure bleue.
    """

    def name(self) -> Text:
        return "action_call_nurse"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get("text")
        
        # Récupérer le patient_id depuis les slots (si identifié)
        patient_id = tracker.get_slot("patient_id")
        patient_name = tracker.get_slot("patient_full_name")
        
        if not patient_id:
            # Patient non identifié, utiliser l'ancienne méthode
            print("[APPEL] Patient non identifié, alerte basique envoyée")
            try:
                insert_alert(message=user_message, patient_id="UNKNOWN")
                dispatcher.utter_message(
                    text="J'ai prévenu l'infirmière. Quelqu'un viendra vous voir bientôt."
                )
            except Exception as e:
                print(f"[ERREUR APPEL DB] {e}")
                dispatcher.utter_message(
                    text="Désolé, je n'ai pas pu enregistrer l'appel. Appuyez sur le bouton d'appel dans votre chambre."
                )
            return []

        # Patient identifié, utiliser le service complet
        try:
            result = trigger_nurse_call(
                patient_id=patient_id,
                reason=f"Demande d'assistance - {user_message}"
            )
            
            if result["success"]:
                print(f"[APPEL] ✅ Envoyé pour {result['patient_name']} - Chambre {result['room_number']}")
                print(f"[APPEL] Dashboard: {'✅ Envoyé' if result['dashboard_sent'] else '❌ Échec'}")
                
                dispatcher.utter_message(
                    text=f"Très bien {patient_name.split()[0]}, j'ai prévenu l'infirmière. Quelqu'un passera vous voir dès que possible."
                )
            else:
                print(f"[APPEL] ❌ Échec: {result.get('error')}")
                dispatcher.utter_message(
                    text="Une erreur s'est produite, mais j'ai enregistré votre demande."
                )
                # Fallback sur insert_alert
                insert_alert(message=user_message, patient_id=patient_id)
                
        except Exception as e:
            print(f"[ERREUR APPEL SYSTÈME] {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback : au moins enregistrer dans la DB
            try:
                insert_alert(message=user_message, patient_id=patient_id)
                dispatcher.utter_message(
                    text="J'ai enregistré votre demande. Quelqu'un viendra vous voir."
                )
            except:
                dispatcher.utter_message(
                    text="Problème technique. Utilisez le bouton d'appel dans votre chambre."
                )

        return []
