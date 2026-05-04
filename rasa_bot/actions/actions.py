from typing import Any, Text, Dict, List
from datetime import datetime
import re
import os
import threading

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
        get_all_patients,
        set_current_patient,
        get_current_patient,
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
        get_all_patients,
        set_current_patient,
        get_current_patient,
    )
    from .alert_service import trigger_emergency_alert, trigger_nurse_call


# ==========================================================
# GATE DE SURVEILLANCE ÉMOTIONNELLE
# La pipeline vision (/emotion_detection) est en sommeil tant que
# Rasa n'a pas décidé que le contexte justifie une surveillance.
# On active via un flag fichier partagé : logs/vision_enabled.flag
#
# Le contenu du flag détermine le MODE de surveillance :
#   "emotion"   → le patient a dit aller bien : on vérifie l'expression faciale
#                  (alerte si incohérence)
#   "emergency" → le patient a dit ne pas aller bien : on cherche les signes
#                  d'étouffement / arrêt respiratoire
#   "both"      → cas généraux (urgence confirmée par dialogue)
# ==========================================================
def _enable_vision_monitoring(mode: str = "both", reason: str = "") -> None:
    """
    Active la surveillance vidéo dans le mode demandé.

    Args:
        mode   : "emotion" | "emergency" | "both"
        reason : libellé pour les logs
    """
    valid = ("emotion", "emergency", "both")
    if mode not in valid:
        mode = "both"
    try:
        import os as _os
        project_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        flag_dir = _os.path.join(project_root, "logs")
        _os.makedirs(flag_dir, exist_ok=True)
        flag_path = _os.path.join(flag_dir, "vision_enabled.flag")
        import time as _time
        with open(flag_path, "w", encoding="utf-8") as fh:
            # Ligne 1 = mode (lue par async_vision_pipeline._vision_mode)
            # Ligne 2 = timestamp
            # Ligne 3 = motif lisible (logs)
            fh.write(f"{mode}\n{_time.time()}\n{reason}")
        print(f"[VISION] ✅ Surveillance ACTIVÉE — mode={mode} — {reason}")
    except Exception as _e:
        print(f"[VISION] ⚠️ Impossible d'écrire le flag : {_e}")


def _disable_vision_monitoring() -> None:
    """Retire le flag. À appeler en fin de conversation / reset."""
    try:
        import os as _os
        project_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        flag_path = _os.path.join(project_root, "logs", "vision_enabled.flag")
        if _os.path.exists(flag_path):
            _os.remove(flag_path)
            print("[VISION] 🛑 Surveillance émotionnelle DÉSACTIVÉE")
    except Exception:
        pass


# ==========================================================
# SINGLETON SESSION PEPPER
# Une seule session NAOqi partagée entre toutes les actions.
# Évite les connexions multiples (conflit NAOqi + timeout Rasa)
# ==========================================================
_pepper_session = None
_pepper_session_lock = threading.Lock()

def _get_or_create_pepper_session(ip: str, port: int):
    """
    Retourne la session NAOqi existante (singleton) ou en crée une nouvelle.
    Thread-safe. Retourne None si la connexion est impossible.
    """
    global _pepper_session
    with _pepper_session_lock:
        try:
            # Tester si la session existante est encore valide
            if _pepper_session is not None:
                try:
                    _pepper_session.service("ALTextToSpeech")  # Ping rapide
                    return _pepper_session
                except Exception:
                    # Session morte → en créer une nouvelle
                    _pepper_session = None

            # Créer une nouvelle session
            import qi
            session = qi.Session()
            session.connect(f"tcp://{ip}:{port}")
            _pepper_session = session
            print(f"[PEPPER SESSION] ✅ Nouvelle session NAOqi créée vers {ip}:{port}")
            return _pepper_session

        except ImportError:
            print("[PEPPER SESSION] Module 'qi' non installé (mode PC simulation).")
            return None
        except Exception as e:
            print(f"[PEPPER SESSION] ❌ Impossible de se connecter : {e}")
            return None


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



# ACTION : Donner la météo actuelle (Avignon, France) via Open-Meteo (API gratuite, sans clé).

class ActionGetWeather(Action):

    def name(self) -> Text:
        return "action_get_weather"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # Avignon, France
        lat, lon = 43.9493, 4.8055
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weather_code,wind_speed_10m"
            "&timezone=Europe%2FParis"
        )

        # Description française des codes WMO les plus courants
        wmo = {
            0: "ciel dégagé",
            1: "plutôt dégagé",
            2: "partiellement nuageux",
            3: "couvert",
            45: "brouillard",
            48: "brouillard givrant",
            51: "bruine légère",
            53: "bruine",
            55: "bruine forte",
            61: "pluie légère",
            63: "pluie",
            65: "pluie forte",
            71: "neige légère",
            73: "neige",
            75: "neige forte",
            80: "averses",
            81: "averses fortes",
            82: "averses violentes",
            95: "orage",
            96: "orage avec grêle",
            99: "orage violent avec grêle",
        }

        try:
            import urllib.request as _urlreq
            import json as _json
            req = _urlreq.Request(url, headers={"User-Agent": "MediBot/1.0"})
            with _urlreq.urlopen(req, timeout=4) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            current = data.get("current", {})
            temp = current.get("temperature_2m")
            code = current.get("weather_code")
            wind = current.get("wind_speed_10m")
            desc = wmo.get(code, "temps variable")
            if temp is None:
                raise ValueError("temperature manquante")
            temp_round = round(float(temp))
            msg = (
                f"À Avignon, il fait {temp_round} degrés, {desc}."
            )
            if wind is not None:
                msg += f" Le vent souffle à {round(float(wind))} kilomètres heure."
            print(f"[METEO] ✅ {msg}")
            dispatcher.utter_message(text=msg)
        except Exception as e:
            print(f"[METEO] ⚠️ Echec API météo : {e}")
            dispatcher.utter_message(
                text="Désolé, je n'arrive pas à récupérer la météo pour l'instant."
            )
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

                # Persister l'identification en DB (partagée avec le pipeline vision)
                try:
                    set_current_patient(patient_id, db_first, db_last)
                    print(f"[IDENTIFICATION] ✅ Session patient enregistrée en DB : {patient_id}")
                except Exception as e_db:
                    print(f"[IDENTIFICATION] ⚠️ Erreur DB session : {e_db}")

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

        # Le patient a déclaré aller bien → surveillance émotionnelle uniquement
        # (caméra vérifie la cohérence parole/visage, pas d'analyse d'urgence)
        _enable_vision_monitoring("emotion", "patient dit aller bien - vérification cohérence")

        dispatcher.utter_message(
            text="Parfait. Souhaitez-vous que je vous chante une chanson (je connais des chansons françaises traditionnelles) ou préférez-vous discuter ?"
        )
        # Marquer qu'on a posé la question activité
        return [
            SlotSet("asked_activity", True),
            SlotSet("asked_emergency", False),
            SlotSet("asked_wellness", False),
        ]



# ======================================
# ACTION : Demander comment va le patient (wellness)
# ======================================

class ActionAskWellbeing(Action):

    def name(self) -> Text:
        return "action_ask_wellbeing"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="Parfait ! Est-ce que vous allez bien ?")
        # Marquer le contexte wellness pour router correctement un simple "oui"/"non"
        return [
            SlotSet("asked_wellness", True),
            SlotSet("asked_emergency", False),
            SlotSet("asked_activity", False),
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

        # Le patient a dit ne pas aller bien → activer la caméra en mode EMERGENCY
        # (détection d'étouffement / d'absence de respiration uniquement,
        # pas d'analyse émotionnelle). Si signe d'étouffement détecté, une
        # alerte sera émise avec le nom du patient.
        _enable_vision_monitoring("emergency", "patient dit ne pas aller bien - surveillance vitale")

        dispatcher.utter_message(
            text="Je suis désolé de l'entendre. Souhaitez-vous que j'appelle l'équipe d'urgence ?"
        )
        # Marquer qu'on a posé la question urgence
        return [
            SlotSet("asked_emergency", True),
            SlotSet("asked_activity", False),
            SlotSet("asked_wellness", False),
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
        asked_wellness = tracker.get_slot("asked_wellness")
        patient_id = tracker.get_slot("patient_id")
        patient_name = tracker.get_slot("patient_full_name")

        # ---- Contexte WELLNESS : "Est-ce que vous allez bien ?" → "Oui" ----
        if asked_wellness:
            # Le patient dit qu'il va bien → surveillance ÉMOTIONNELLE pure
            # (vérification silencieuse de cohérence parole/visage)
            _enable_vision_monitoring("emotion", "patient dit aller bien - vérification cohérence")
            dispatcher.utter_message(
                text="Parfait. Souhaitez-vous que je vous chante une chanson ou préférez-vous discuter ?"
            )
            return [
                SlotSet("asked_wellness", False),
                SlotSet("asked_activity", True),
                SlotSet("asked_emergency", False),
            ]

        if asked_emergency:
            # Déclencher l'alerte niveau 2 + activer la surveillance complète
            # (le patient a confirmé vouloir de l'aide → on observe tout)
            _enable_vision_monitoring("both", "patient a confirmé vouloir de l'aide")

            # Résoudre le patient depuis la session DB si le slot est vide
            _eff_patient_id = patient_id
            if not _eff_patient_id or _eff_patient_id.upper().strip() in ("UNKNOWN", ""):
                try:
                    _session = get_current_patient()
                    if _session:
                        _eff_patient_id = _session.get("patient_id", "")
                except Exception:
                    pass
            if not _eff_patient_id or _eff_patient_id.upper().strip() in ("UNKNOWN", ""):
                print("[URGENCE BLOQUÉE] Patient non identifié — alerte non insérée.")
            else:
                try:
                    insert_alert(message="Urgence vitale potentielle - patient confirme", patient_id=_eff_patient_id)
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
        asked_wellness = tracker.get_slot("asked_wellness")

        # ---- Contexte WELLNESS : "Est-ce que vous allez bien ?" → "Non" ----
        if asked_wellness:
            # Le patient dit qu'il ne va pas bien → caméra en mode EMERGENCY
            # (détection d'étouffement / arrêt respiratoire ; aucune analyse
            # d'émotion). Alerte automatique avec le nom du patient si signe vital.
            _enable_vision_monitoring("emergency", "patient dit ne pas aller bien - surveillance vitale")
            dispatcher.utter_message(
                text="Je suis désolé de l'entendre. Souhaitez-vous que j'appelle l'équipe d'urgence ?"
            )
            return [
                SlotSet("asked_wellness", False),
                SlotSet("asked_emergency", True),
                SlotSet("asked_activity", False),
            ]

        if asked_emergency:
            # Patient refuse d'appeler mais a dit ne pas aller bien →
            # surveillance EMERGENCY (on cherche les signes vitaux : étouffement,
            # arrêt respiratoire). On n'analyse pas les émotions ici.
            _enable_vision_monitoring("emergency", "patient refuse aide après avoir dit ne pas aller bien")
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
# ACTION : Jouer une chanson instrumentale (WAV) + gestes Pepper
# ======================================

class ActionPlaySong(Action):

    def name(self) -> Text:
        return "action_play_song"

    # ------------------------------------------------------------------
    # Chansons avec fichiers WAV instrumentaux pré-générés.
    # "wav"     = nom du fichier dans rasa_bot/actions/songs/
    # "intro"   = phrase TTS dite AVANT la musique.
    # "outro"   = phrase TTS dite APRÈS la musique.
    # "emotion" = couleur LEDs pendant la musique.
    # "gesture" = geste Pepper avant de jouer.
    # ------------------------------------------------------------------
    SONGS = [
        {
            "title": "Au Clair de la Lune",
            "artist": "Chanson traditionnelle française",
            "wav": "au_clair_de_la_lune.wav",
            "intro": "Je vais vous jouer Au Clair de la Lune. Écoutez bien !",
            "outro": "J'espère que cette mélodie vous apporte un peu de sérénité.",
            "emotion": "calm",
            "gesture": "animations/Stand/Emotions/Neutral/Calm_1",
        },
        {
            "title": "Frère Jacques",
            "artist": "Chanson traditionnelle française",
            "wav": "frere_jacques.wav",
            "intro": "Voici Frère Jacques, une mélodie qui réchauffe le cœur !",
            "outro": "Voilà ! J'espère que cette musique vous a plu.",
            "emotion": "happy",
            "gesture": "animations/Stand/Gestures/Yes_1",
        },
        {
            "title": "La Vie en Rose",
            "artist": "Édith Piaf",
            "wav": "la_vie_en_rose.wav",
            "intro": "Je vais vous jouer La Vie en Rose d'Édith Piaf.",
            "outro": "Quelle belle mélodie, n'est-ce pas ?",
            "emotion": "happy",
            "gesture": "animations/Stand/Emotions/Positive/Happy_4",
        },
        {
            "title": "Douce France",
            "artist": "Charles Trenet",
            "wav": "douce_france.wav",
            "intro": "Voici Douce France de Charles Trenet.",
            "outro": "Une belle mélodie pour penser à des souvenirs doux.",
            "emotion": "calm",
            "gesture": "animations/Stand/Emotions/Neutral/Calm_1",
        },
        {
            "title": "Promenons-nous dans les bois",
            "artist": "Chanson traditionnelle française",
            "wav": "promenons_nous.wav",
            "intro": "Je vais vous jouer Promenons-nous dans les bois !",
            "outro": "Voilà ! Une mélodie pleine de vivacité pour vous redonner le sourire.",
            "emotion": "happy",
            "gesture": "animations/Stand/Gestures/Hey_1",
        },
    ]

    # Chemin vers le dossier des fichiers WAV
    SONGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "songs")

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        import random
        import os

        patient_name = tracker.get_slot("patient_full_name")
        song = random.choice(self.SONGS)
        wav_path = os.path.join(self.SONGS_DIR, song["wav"])

        # ------------------------------------------------------------------
        # 1. Message texte + intro parlée
        # ------------------------------------------------------------------
        first_name = patient_name.split()[0] if patient_name else None

        if first_name:
            dispatcher.utter_message(
                text=(
                    f"🎵 Très bien {first_name}, je vais vous jouer "
                    f"\"{song['title']}\" de {song['artist']}. "
                    f"Installez-vous confortablement..."
                )
            )
        else:
            dispatcher.utter_message(
                text=(
                    f"🎵 Je vais vous jouer \"{song['title']}\" "
                    f"de {song['artist']}. "
                    f"Installez-vous confortablement..."
                )
            )

        # Intro parlée (voice_bridge la prononcera via TTS)
        dispatcher.utter_message(text=song["intro"])

        # ------------------------------------------------------------------
        # 2. Lecture du fichier WAV instrumental
        #    On envoie un message JSON spécial que voice_bridge intercepte
        #    pour jouer le fichier audio au lieu de le lire en TTS.
        # ------------------------------------------------------------------
        if os.path.exists(wav_path):
            dispatcher.utter_message(
                json_message={"play_audio": wav_path}
            )
            print(f"[CHANSON] 🎵 Lecture audio : {wav_path}")
        else:
            # Fallback : si le WAV n'existe pas, on prévient
            dispatcher.utter_message(
                text=f"(Le fichier instrumental n'a pas été trouvé : {song['wav']}. "
                     f"Lancez 'python scripts/generate_melodies.py' pour le générer.)"
            )
            print(f"[CHANSON] ⚠️ Fichier WAV manquant : {wav_path}")

        # Outro parlée
        dispatcher.utter_message(text=song["outro"])

        # ------------------------------------------------------------------
        # 3. Commandes Pepper (gestes + LEDs) dans un thread daemon
        # ------------------------------------------------------------------
        import threading

        def _play_on_pepper(song_data: dict, audio_path: str) -> None:
            """Gestes + LEDs Pepper en arrière-plan (non bloquant)."""
            try:
                pepper_ip = os.getenv("PEPPER_IP")
                pepper_port = int(os.getenv("PEPPER_PORT", "9559"))

                if not pepper_ip:
                    print(f"[CHANSON] Mode simulation – PEPPER_IP non défini.")
                    print(f"[CHANSON] Chanson : {song_data['title']} ({song_data['artist']})")
                    return

                import qi

                session = _get_or_create_pepper_session(pepper_ip, pepper_port)
                if session is None:
                    print("[CHANSON] Impossible d'obtenir une session Pepper.")
                    return

                # === GESTE avant la musique ===
                try:
                    behavior_service = session.service("ALBehaviorManager")
                    if behavior_service.isBehaviorInstalled(song_data["gesture"]):
                        behavior_service.runBehavior(song_data["gesture"])
                except Exception as e:
                    print(f"[CHANSON] Geste non disponible ({e}), poursuite...")

                # === LEDs pendant la musique ===
                emotion_hex = {
                    "calm":  0x0066CC,
                    "happy": 0x00CC66,
                }
                hex_color = emotion_hex.get(song_data["emotion"], 0xFFFFFF)
                try:
                    leds = session.service("ALLeds")
                    leds.fadeRGB("FaceLeds", hex_color, 1.0)
                except Exception as e:
                    print(f"[CHANSON] LEDs non disponibles ({e}), poursuite...")

                # NOTE : la lecture audio WAV est gérée par voice_bridge
                # (via le json_message play_audio). Ici on fait seulement
                # les gestes + LEDs. On attend ~20s pour la durée de la musique.
                import time as _t
                _t.sleep(20)

                # LEDs : retour blanc neutre
                try:
                    leds.fadeRGB("FaceLeds", 0xFFFFFF, 2.0)
                except Exception:
                    pass

                print(f"[CHANSON] ✅ Musique terminée : {song_data['title']}")

            except ImportError:
                print("[CHANSON] Module 'qi' non disponible – mode simulation PC.")
            except Exception as e:
                import traceback
                print(f"[CHANSON] Erreur Pepper : {e}")
                traceback.print_exc()

        t = threading.Thread(
            target=_play_on_pepper, args=(song, wav_path), daemon=True
        )
        t.start()

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



# ======================================
# ACTION : Patient ne répond pas (silence prolongé)
# Déclenchée par l'intent silence_timeout envoyé par le pont vocal
# après 5 s sans réponse suite à une question du robot.
# ======================================
class ActionHandleSilenceTimeout(Action):

    def name(self) -> Text:
        return "action_handle_silence_timeout"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        asked_emergency = tracker.get_slot("asked_emergency")
        patient_id = tracker.get_slot("patient_id")

        if not asked_emergency:
            # Silence hors contexte critique → simple relance
            dispatcher.utter_message(
                text="Je n'ai pas entendu votre réponse. Tout va bien ?"
            )
            return []

        # Patient a dit ne pas aller bien, puis silence → alerte + surveillance
        _enable_vision_monitoring("patient silencieux après déclaration de mal-être")

        _eff_patient_id = patient_id
        if not _eff_patient_id or _eff_patient_id.upper().strip() in ("UNKNOWN", ""):
            try:
                _session = get_current_patient()
                if _session:
                    _eff_patient_id = _session.get("patient_id", "")
            except Exception:
                pass

        if _eff_patient_id and _eff_patient_id.upper().strip() not in ("UNKNOWN", ""):
            try:
                insert_alert(
                    message="Patient silencieux après avoir signalé ne pas aller bien",
                    patient_id=_eff_patient_id
                )
            except Exception as e:
                print(f"[ERREUR ALERT DB] {e}")
        else:
            print("[URGENCE BLOQUÉE] Patient non identifié — alerte silence non insérée.")

        dispatcher.utter_message(
            text="Je ne vous entends pas. Je préviens l'équipe médicale par précaution. Restez calme, je suis là."
        )
        return [
            SlotSet("asked_emergency", False),
            SlotSet("emergency_handled", True),
        ]



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

        # >>> Activation caméra : URGENCE déclarée par le patient
        # Mode 'both' : surveillance vitale (étouffement/respiration) + cohérence émotionnelle
        _enable_vision_monitoring(
            "both",
            f"URGENCE déclarée par le patient : {user_message}",
        )

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

        # >>> Activation caméra : demande d'aide humaine ("cherche moi quelqu'un" / appel infirmière)
        # Mode 'both' : on surveille étouffement + émotions en attendant le personnel
        _enable_vision_monitoring(
            "both",
            f"Demande d'aide / infirmière : {user_message}",
        )

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


