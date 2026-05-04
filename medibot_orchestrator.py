#!/usr/bin/env python3
"""
medibot_orchestrator.py — Orchestrateur central MediBot.

State Machine (priorité stricte) :
  IDLE         → Robot inactif, aucune détection en cours
  CONVERSATION → Rasa actif, dialogue patient en cours
  ALERT        → Émotion de détresse (sad/angry/fear) détectée, alerte soignant
  EMERGENCY    → Urgence vitale (respiration absente / étouffement)
                 → VERROUILLE le dialogue conversationnel jusqu'à expiration

Architecture :
  ┌─────────────────────────────────────────────────────────────┐
  │                    ORCHESTRATEUR                            │
  │                                                             │
  │  ┌──────────────────────┐    ┌──────────────────────────┐  │
  │  │  Thread VISION       │    │  Thread AUDIO            │  │
  │  │  ─────────────────── │    │  ──────────────────────  │  │
  │  │  AsyncVisionPipeline │    │  Whisper medium (STT)    │  │
  │  │  · DeepFace          │    │  Rasa NLU/dialogue       │  │
  │  │  · MediaPipe         │    │  TTS Pepper / pyttsx3    │  │
  │  │  · EmergencyDetector │    │                          │  │
  │  └──────────┬───────────┘    └────────────┬─────────────┘  │
  │             │                             │                 │
  │             │       SharedContext         │                 │
  │             └─────────────┬───────────────┘                 │
  │                           │                                 │
  │  Règles de priorité :     │                                 │
  │  EMERGENCY → Audio suspendu, annonce vocale urgence         │
  │  ALERT     → Audio continue, alerte soignant envoyée        │
  │  IDLE      → Audio en attente d'écoute patient              │
  └─────────────────────────────────────────────────────────────┘

Usage :
  python medibot_orchestrator.py [--server] [--debug]

Options :
  --server  : Déporte DeepFace sur le serveur Flask (recommandé sur Pepper)
  --debug   : Active les logs détaillés
"""

import os
import sys
import time
import threading
import logging
import argparse
from enum import IntEnum
from pathlib import Path

# ================================================================
# PYTHONPATH — rendre tous les modules accessibles
# ================================================================

ROOT_DIR = Path(__file__).resolve().parent
EMOTION_DIR = ROOT_DIR / "emotion_detection"
STT_DIR = ROOT_DIR / "stt_whisper"

for d in [str(ROOT_DIR), str(EMOTION_DIR), str(STT_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)

# ================================================================
# CONFIGURATION (.env + variables d'environnement)
# ================================================================

try:
    from dotenv import load_dotenv
    _env = ROOT_DIR / ".env"
    if _env.exists():
        load_dotenv(dotenv_path=_env)
except ImportError:
    pass

PEPPER_IP = os.getenv("PEPPER_IP")
PEPPER_PORT = int(os.getenv("PEPPER_PORT", "9559"))
PATIENT_ID = os.getenv("PATIENT_ID", "PAT001")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:5000/api/alerts")
USE_SERVER_VISION = os.getenv("USE_SERVER_VISION", "0") == "1"

# ================================================================
# LOGGING
# ================================================================

LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(
                str(LOG_DIR / "orchestrator.log"), encoding="utf-8"
            ),
            logging.StreamHandler(),
        ],
    )


logger = logging.getLogger("Orchestrator")

# ================================================================
# STATE MACHINE
# ================================================================


class RobotState(IntEnum):
    """
    États du robot, triés par priorité croissante.
    Un état de priorité plus haute ne peut pas être interrompu
    par un état de priorité plus basse.
    """
    IDLE         = 0   # Aucune activité
    CONVERSATION = 1   # Dialogue Rasa actif
    ALERT        = 2   # Émotion de détresse détectée
    EMERGENCY    = 3   # Urgence vitale — verrouille tout


class SharedContext:
    """
    État partagé thread-safe entre le thread vision et le thread audio.

    Règle de priorité :
      - EMERGENCY verrouille le state jusqu'à expiration du cooldown.
      - Un état de priorité inférieure ne peut pas rétrograder un état supérieur.
    """

    # Durée de verrouillage en état EMERGENCY avant retour automatique à IDLE
    EMERGENCY_LOCK_SECONDS = 30

    def __init__(self):
        self._lock = threading.Lock()
        self._state = RobotState.IDLE
        self._emergency_since = 0.0
        self.emergency_reason = ""
        self.last_emotion = "neutral"
        # Event déclenché lors d'une urgence (utile pour réveiller des threads en attente)
        self.emergency_event = threading.Event()

    # ------------------------------------------------------------------
    # LECTURE D'ÉTAT (avec auto-expiration des urgences)
    # ------------------------------------------------------------------

    @property
    def state(self) -> RobotState:
        with self._lock:
            # Auto-retour à IDLE après expiration du cooldown urgence
            if (
                self._state == RobotState.EMERGENCY
                and self._emergency_since > 0
                and time.time() - self._emergency_since > self.EMERGENCY_LOCK_SECONDS
            ):
                logger.info("[STATE] EMERGENCY expirée → retour à IDLE")
                self._state = RobotState.IDLE
                self.emergency_reason = ""
                self.emergency_event.clear()
            return self._state

    # ------------------------------------------------------------------
    # TRANSITIONS D'ÉTAT
    # ------------------------------------------------------------------

    def set_emergency(self, reason: str) -> None:
        """Déclenche l'état d'urgence vitale (priorité maximale)."""
        with self._lock:
            if self._state == RobotState.EMERGENCY:
                # Déjà en urgence : rafraîchir le cooldown mais ne pas répéter
                self._emergency_since = time.time()
                return
            old = self._state
            self._state = RobotState.EMERGENCY
            self.emergency_reason = reason
            self._emergency_since = time.time()
            self.emergency_event.set()
        logger.critical(f"[STATE] {old.name} → EMERGENCY | {reason}")

    def set_alert(self, emotion: str) -> None:
        """Passe en état d'alerte (émotion de détresse détectée)."""
        with self._lock:
            if self._state >= RobotState.EMERGENCY:
                return  # Urgence verrouillée — ALERT ne peut pas interrompre
            old = self._state
            self._state = RobotState.ALERT
            self.last_emotion = emotion
        if old != RobotState.ALERT:
            logger.warning(f"[STATE] {old.name} → ALERT | émotion: {emotion}")

    def set_conversation(self) -> None:
        """Passe en état conversationnel (Rasa actif)."""
        with self._lock:
            if self._state >= RobotState.ALERT:
                return
            self._state = RobotState.CONVERSATION
        logger.debug("[STATE] → CONVERSATION")

    def set_idle(self) -> None:
        """Retour à l'état inactif."""
        with self._lock:
            if self._state >= RobotState.EMERGENCY:
                return
            self._state = RobotState.IDLE
        logger.debug("[STATE] → IDLE")

    # ------------------------------------------------------------------
    # INTERROGATION
    # ------------------------------------------------------------------

    def is_audio_blocked(self) -> bool:
        """
        Retourne True si le thread audio doit suspendre son cycle.
        Seul EMERGENCY bloque l'audio — ALERT laisse passer le dialogue
        (le soignant est déjà notifié par le thread vision).
        """
        return self.state == RobotState.EMERGENCY


# ================================================================
# THREAD VISION
# ================================================================


def vision_thread_fn(
    ctx: SharedContext,
    pepper_session,
    stop_event: threading.Event,
    use_server: bool = False,
):
    """
    Thread vision : exécute AsyncVisionPipeline et met à jour SharedContext.

    - Urgence   → ctx.set_emergency()  : verrouille le dialogue audio
    - Détresse  → ctx.set_alert()      : alerte soignant, dialogue continue
    - Neutre    → ctx.set_idle()       : remet à IDLE si on était en ALERT
    """
    try:
        from video_stream import VideoStream
        from async_vision_pipeline import AsyncVisionPipeline, AnalysisType
    except ImportError as e:
        logger.error(f"Thread vision : import échoué ({e}) — vision désactivée")
        return

    video_src = "pepper" if pepper_session else 0
    stream = VideoStream(source=video_src, pepper_session=pepper_session)

    pipeline = AsyncVisionPipeline(
        video_stream=stream,
        pepper_session=pepper_session,
        patient_id=PATIENT_ID,
        alert_url=DASHBOARD_URL,
        use_server_vision=use_server,
        emotion_interval=1.2,      # DeepFace ~1 analyse / 1.2s + lissage EMA
        emergency_interval=0.4,    # MediaPipe ~2.5 FPS (urgences critiques)
    )

    pipeline.start()
    logger.info("Thread vision démarré")

    try:
        while not stop_event.is_set():
            results = pipeline.process_results()

            for result in results:
                if result.type == AnalysisType.EMERGENCY:
                    # Urgence vitale : verrouiller immédiatement le dialogue
                    ctx.set_emergency(result.value)

                elif result.type == AnalysisType.EMOTION:
                    ctx.last_emotion = result.value
                    if result.value in ("angry", "fear", "sad", "disgust"):
                        # Détresse émotionnelle : alerter sans bloquer le dialogue
                        ctx.set_alert(result.value)
                    elif ctx.state == RobotState.ALERT:
                        # Retour à une émotion neutre : lever l'état d'alerte
                        ctx.set_idle()

            time.sleep(0.1)

    except Exception as e:
        if not stop_event.is_set():
            logger.error(f"Thread vision erreur inattendue: {e}", exc_info=True)
    finally:
        pipeline.stop()
        logger.info("Thread vision arrêté")


# ================================================================
# THREAD AUDIO
# ================================================================


def audio_thread_fn(ctx: SharedContext, stop_event: threading.Event):
    """
    Thread audio : Whisper medium → Rasa, suspendu pendant EMERGENCY.

    Passe `is_emergency_fn` à run_voice_loop() pour que le dialogue
    soit automatiquement suspendu quand une urgence est détectée.
    """
    try:
        import voice_bridge
    except ImportError as e:
        logger.error(f"Thread audio : import échoué ({e}) — audio désactivé")
        return

    def is_emergency() -> bool:
        return ctx.is_audio_blocked()

    logger.info("Thread audio démarré (Whisper medium)")
    try:
        voice_bridge.run_voice_loop(is_emergency_fn=is_emergency)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        if not stop_event.is_set():
            logger.error(f"Thread audio erreur: {e}", exc_info=True)
    finally:
        logger.info("Thread audio arrêté")


# ================================================================
# CONNEXION PEPPER
# ================================================================


def connect_pepper():
    """Tente une connexion NAOqi à Pepper. Retourne la session ou None."""
    if not PEPPER_IP:
        logger.info("PEPPER_IP non défini → mode PC (webcam + micro PC)")
        return None
    try:
        import qi
        session = qi.Session()
        session.connect(f"tcp://{PEPPER_IP}:{PEPPER_PORT}")
        logger.info(f"Pepper connecté → {PEPPER_IP}:{PEPPER_PORT}")
        return session
    except ImportError:
        logger.warning("Module 'qi' non disponible → mode PC")
    except Exception as e:
        logger.warning(f"Connexion Pepper échouée ({e}) → mode PC")
    return None


# ================================================================
# BOUCLE DE SUPERVISION (thread principal)
# ================================================================


def supervision_loop(ctx: SharedContext, t_vision: threading.Thread, t_audio: threading.Thread):
    """
    Affiche un résumé d'état toutes les 10 secondes.
    Alertes en rouge si EMERGENCY, jaune si ALERT.
    """
    STATUS_INTERVAL = 10
    ANSI_RED    = "\033[91m"
    ANSI_YELLOW = "\033[93m"
    ANSI_GREEN  = "\033[92m"
    ANSI_RESET  = "\033[0m"

    while True:
        time.sleep(STATUS_INTERVAL)
        s = ctx.state
        color = (
            ANSI_RED    if s == RobotState.EMERGENCY else
            ANSI_YELLOW if s == RobotState.ALERT     else
            ANSI_GREEN
        )
        vision_status = "OK" if t_vision.is_alive() else "MORT"
        audio_status  = "OK" if t_audio.is_alive()  else "MORT"

        print(
            f"\n[STATUS] État: {color}{s.name}{ANSI_RESET} | "
            f"Émotion: {ctx.last_emotion} | "
            f"Vision: {vision_status} | "
            f"Audio: {audio_status}"
        )
        if s == RobotState.EMERGENCY:
            print(f"         Urgence: {ctx.emergency_reason}")


# ================================================================
# POINT D'ENTRÉE PRINCIPAL
# ================================================================


def main():
    parser = argparse.ArgumentParser(
        description="MediBot — Orchestrateur central (vision + audio)"
    )
    parser.add_argument(
        "--server", action="store_true",
        help="Déporter DeepFace sur le serveur Flask (recommandé sur Pepper)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Activer les logs détaillés"
    )
    args = parser.parse_args()

    setup_logging(args.debug)

    use_server = args.server or USE_SERVER_VISION

    print("\n" + "=" * 62)
    print("  MEDIBOT — Orchestrateur Central")
    print("=" * 62)
    print(f"  Patient    : {PATIENT_ID}")
    print(f"  Dashboard  : {DASHBOARD_URL}")
    print(f"  Vision     : {'Serveur Flask' if use_server else 'Local'}")
    print(f"  STT        : Whisper medium")
    print(f"  Pepper     : {PEPPER_IP or 'Non configuré (mode PC)'}")
    print("=" * 62)
    print("  CTRL+C pour arrêter")
    print("=" * 62 + "\n")

    # --- Connexion Pepper (session partagée entre les deux threads) ---
    pepper_session = connect_pepper()

    # --- Contexte partagé (state machine thread-safe) ---
    ctx = SharedContext()
    stop_event = threading.Event()

    # --- Thread vision ---
    t_vision = threading.Thread(
        target=vision_thread_fn,
        args=(ctx, pepper_session, stop_event, use_server),
        name="Vision",
        daemon=True,
    )

    # --- Thread audio ---
    t_audio = threading.Thread(
        target=audio_thread_fn,
        args=(ctx, stop_event),
        name="Audio",
        daemon=True,
    )

    t_vision.start()
    t_audio.start()

    logger.info("Orchestrateur démarré — threads vision + audio actifs")

    try:
        supervision_loop(ctx, t_vision, t_audio)
    except KeyboardInterrupt:
        print("\n\n[Orchestrateur] Arrêt demandé (CTRL+C)...")
    finally:
        stop_event.set()
        t_vision.join(timeout=5)
        t_audio.join(timeout=5)
        print("[Orchestrateur] Arrêt propre.")


if __name__ == "__main__":
    main()
