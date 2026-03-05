"""
emotion_detector.py — Détection d'émotions et pipeline intégrée.

BUG CORRIGE 8 :
  La version précédente analysait les émotions mais ne faisait RIEN
  avec les résultats : ni alerte, ni LEDs Pepper, ni message vocal.
  Désormais :
    - Les émotions de détresse (angry/fear/sad) déclenchent AlertSystem
    - Les LEDs Pepper sont contrôlées via les hex NAOqi de emotion_rules.py
    - Le robot parle via ALTextToSpeech si Pepper est connecté
    - VideoStream est utilisé pour la capture caméra
"""

import os
import time
import logging

logger = logging.getLogger(__name__)

# Import paresseux de DeepFace : évite de casser les autres modules
# (Rasa, Whisper, etc.) si deepface n'est pas installé dans cet env.
_deepface = None

def _get_deepface():
    global _deepface
    if _deepface is None:
        try:
            from deepface import DeepFace as _df
            _deepface = _df
        except ImportError:
            raise ImportError(
                "deepface n'est pas installé. "
                "Installez-le séparément : pip install deepface==0.0.79\n"
                "Ou lancez la détection d'émotions dans un venv dédié "
                "(voir README emotion_detection)."
            )
    return _deepface

# Interval minimum entre deux réactions pour la même émotion (secondes)
REACTION_COOLDOWN = 30
# Nombre de frames consécutives d'une même émotion avant réaction
STABILITY_THRESHOLD = 3


class EmotionDetector:
    """Analyse l'émotion dominante sur un frame OpenCV (BGR numpy array)."""

    def __init__(self):
        self.target_emotions = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']

    def analyze_emotion(self, frame):
        """Retourne l'émotion dominante ('happy', 'sad', ...) ou 'unknown'."""
        try:
            df = _get_deepface()
            results = df.analyze(frame, actions=['emotion'], enforce_detection=False)
            return results[0]['dominant_emotion']
        except ImportError:
            raise  # Remonter l'erreur d'import
        except Exception as e:
            logger.debug(f"EmotionDetector: erreur analyse ({e})")
            return "unknown"


class EmotionPipeline:
    """
    Pipeline complète : VideoStream → EmotionDetector → Réactions (LEDs + TTS + Alertes).

    Paramètres :
      patient_id     : ID du patient observé (pour les alertes)
      pepper_session : session qi.Session() si Pepper connecté, sinon None
      alert_url      : URL du dashboard Flask pour les alertes
    """

    def __init__(self, patient_id: str = "UNKNOWN",
                 pepper_session=None,
                 alert_url: str = "http://localhost:5000/api/alerts"):

        self.patient_id = patient_id
        self.pepper_session = pepper_session
        self.detector = EmotionDetector()

        # Services Pepper (optionnels)
        self._tts = None
        self._leds = None
        if pepper_session is not None:
            try:
                self._tts = pepper_session.service("ALTextToSpeech")
                self._tts.setLanguage("French")
                self._leds = pepper_session.service("ALLeds")
                logger.info("EmotionPipeline: services Pepper TTS + LEDs OK")
            except Exception as e:
                logger.warning(f"EmotionPipeline: services Pepper indisponibles ({e})")

        # AlertSystem
        from alert_system import AlertSystem
        self._alert_system = AlertSystem(dashboard_url=alert_url)

        # État interne
        self._last_reaction_time: dict = {}  # emotion → timestamp
        self._emotion_buffer: list = []       # tampon de stabilité

    # ------------------------------------------------------------------
    # API PUBLIQUE
    # ------------------------------------------------------------------

    def process_frame(self, frame) -> str:
        """
        Analyse un frame et déclenche les réactions si nécessaire.
        Retourne l'émotion détectée.
        """
        emotion = self.detector.analyze_emotion(frame)
        if emotion == "unknown":
            return emotion

        # Stabilité : attendre STABILITY_THRESHOLD détections consécutives
        self._emotion_buffer.append(emotion)
        if len(self._emotion_buffer) > STABILITY_THRESHOLD:
            self._emotion_buffer.pop(0)

        if len(self._emotion_buffer) == STABILITY_THRESHOLD and \
                all(e == emotion for e in self._emotion_buffer):
            self._react(emotion)

        return emotion

    def run_loop(self, video_source=0):
        """
        Boucle principale d'analyse.
          - video_source=0         : webcam PC (test)
          - video_source="pepper"  : caméra Pepper NAOqi
        """
        from video_stream import VideoStream
        stream = VideoStream(
            source=video_source,
            pepper_session=self.pepper_session
        )
        logger.info("EmotionPipeline: démarrage de la boucle d'analyse")
        print("\n[EmotionPipeline] Surveillance des émotions démarrée (CTRL+C pour arrêter)")

        try:
            while True:
                frame = stream.get_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue

                emotion = self.process_frame(frame)
                if emotion != "unknown":
                    print(f"  Émotion détectée : {emotion}")

                time.sleep(0.2)   # ~5 fps pour économiser les ressources
        except KeyboardInterrupt:
            pass
        finally:
            stream.release()
            logger.info("EmotionPipeline: arrêt.")

    # ------------------------------------------------------------------
    # RÉACTIONS INTERNES
    # ------------------------------------------------------------------

    def _react(self, emotion: str) -> None:
        """Déclenche les réactions (LEDs, TTS, alerte) pour une émotion stable."""
        from emotion_rules import get_medibot_reaction
        reaction = get_medibot_reaction(emotion)

        # Cooldown : ne pas répéter la même réaction trop vite
        now = time.time()
        if now - self._last_reaction_time.get(emotion, 0) < REACTION_COOLDOWN:
            return
        self._last_reaction_time[emotion] = now

        # 1. LEDs Pepper
        self._set_leds(reaction["led_hex"])

        # 2. Message vocal
        if reaction["msg"]:
            self._say(reaction["msg"])
            print(f"  [Réaction] {reaction['gesture']} | {reaction['leds']}")

        # 3. Alerte soignant si nécessaire
        if reaction.get("alert"):
            self._send_alert(emotion, reaction["severity"])

    def _set_leds(self, hex_color: int) -> None:
        """Contrôle les LEDs du visage de Pepper (ALLeds.fadeRGB)."""
        if self._leds is not None:
            try:
                self._leds.fadeRGB("FaceLeds", hex_color, 1.0)
            except Exception as e:
                logger.warning(f"LED error: {e}")
        else:
            # Simulation PC : affichage hexadécimal
            logger.debug(f"[SIM LED] #{hex_color:06X}")

    def _say(self, text: str) -> None:
        """Fait parler Pepper (ALTextToSpeech) ou logge en mode PC."""
        if self._tts is not None:
            try:
                self._tts.say(text)
            except Exception as e:
                logger.warning(f"TTS error: {e}")
        else:
            print(f"  [SIM TTS] {text}")

    def _send_alert(self, emotion: str, severity: str) -> None:
        """Envoie une alerte au dashboard Flask via AlertSystem."""
        level = 2 if severity == "high" else 1
        reason = f"Émotion de détresse détectée : {emotion} (patient {self.patient_id})"
        logger.warning(f"ALERTE niveau {level} : {reason}")
        self._alert_system.send_alert(
            level=level,
            reason=reason,
            patient_id=self.patient_id
        )