"""
async_vision_pipeline.py — Pipeline de vision non-bloquant.

OPTIMISATION MAJEURE :
  Sépare la capture vidéo de l'analyse en threads indépendants.
  - Thread 1 (Capture)   : Lit les frames à ~10 FPS, remplit un buffer circulaire
  - Thread 2 (Emotions)  : Analyse DeepFace toutes les N secondes (non-bloquant)
  - Thread 3 (Urgences)  : MediaPipe pour respiration/étouffement (plus fréquent)
  - Thread Principal     : Orchestre et gère les alertes

Architecture :
  ┌─────────────────────────────────────────────────────────────────┐
  │                        PEPPER CAMERA                            │
  └─────────────────────────┬───────────────────────────────────────┘
                            │ frames (10 FPS)
                            ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                   FRAME BUFFER (Thread-safe)                    │
  │                      (1-3 frames max)                           │
  └───────┬─────────────────────────────────────────┬───────────────┘
          │                                         │
          ▼                                         ▼
  ┌───────────────────┐                   ┌───────────────────────┐
  │  EMOTION WORKER   │                   │   EMERGENCY WORKER    │
  │  (DeepFace)       │                   │   (MediaPipe)         │
  │  ~1 frame / 2-3s  │                   │   ~2-3 frames / sec   │
  └─────────┬─────────┘                   └───────────┬───────────┘
            │                                         │
            ▼                                         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                     RESULT QUEUE                                │
  │                (emotions + urgences)                            │
  └─────────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                   ALERT DISPATCHER                              │
  │            (LEDs + TTS + Dashboard HTTP)                        │
  └─────────────────────────────────────────────────────────────────┘

Auteur: MediBot Team - Optimisation Latence
"""

import os
import sys
import time
import logging
import threading
from queue import Queue, Empty, Full
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


# ── Flag partagé : la surveillance \u00e9motionnelle est activ\u00e9e seulement
#    quand Rasa \u00e9crit logs/vision_enabled.flag (apr\u00e8s r\u00e9ponse du patient
#    \u00e0 la question "Est-ce que vous allez bien ?")
#
# Le contenu du flag d\u00e9termine le MODE de surveillance :
#   "emotion"   → uniquement DeepFace (cas "patient dit aller bien" — coh\u00e9rence)
#   "emergency" → uniquement MediaPipe \u00e9touffement/respiration (cas "patient dit ne pas aller bien")
#   "both"      → les deux (compat retro / cas g\u00e9n\u00e9raux)
# Format ligne 1 du fichier : un de ces 3 keywords.  Sinon on consid\u00e8re "both".
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VISION_FLAG_PATH = os.path.join(_PROJECT_ROOT, "logs", "vision_enabled.flag")

_VALID_MODES = ("emotion", "emergency", "both")


def _vision_enabled() -> bool:
    """Retourne True si Rasa a autorisé la surveillance émotionnelle."""
    return os.path.exists(_VISION_FLAG_PATH)


def _vision_mode() -> str:
    """
    Lit le mode de surveillance demandé par Rasa.
    Retourne "emotion", "emergency", "both" ou "" si flag absent.
    """
    if not os.path.exists(_VISION_FLAG_PATH):
        return ""
    try:
        with open(_VISION_FLAG_PATH, "r", encoding="utf-8") as fh:
            first = (fh.readline() or "").strip().lower()
        if first in _VALID_MODES:
            return first
        # Format legacy (timestamp en premi\u00e8re ligne) → mode "both"
        return "both"
    except Exception:
        return "both"


class AnalysisType(Enum):
    """Types d'analyses visuelles."""
    EMOTION = "emotion"
    EMERGENCY = "emergency"


@dataclass
class AnalysisResult:
    """Résultat d'une analyse visuelle."""
    type: AnalysisType
    value: str
    confidence: float = 0.0
    timestamp: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if self.metadata is None:
            self.metadata = {}


class FrameBuffer:
    """
    Buffer thread-safe pour les frames vidéo.
    
    Utilise une stratégie "drop oldest" pour éviter l'accumulation
    si le traitement est plus lent que la capture.
    """
    
    def __init__(self, max_size: int = 3):
        self._buffer = []
        self._lock = threading.Lock()
        self._max_size = max_size
        self._frame_count = 0
        self._drop_count = 0
    
    def put(self, frame: np.ndarray) -> bool:
        """Ajoute un frame. Retourne False si le buffer était plein (drop)."""
        with self._lock:
            self._frame_count += 1
            if len(self._buffer) >= self._max_size:
                self._buffer.pop(0)  # Drop oldest
                self._drop_count += 1
                dropped = True
            else:
                dropped = False
            self._buffer.append((frame.copy(), time.time()))
            return not dropped
    
    def get(self) -> Optional[tuple]:
        """Récupère le frame le plus récent (None si vide)."""
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer[-1]  # Le plus récent
    
    def get_oldest(self) -> Optional[tuple]:
        """Récupère et retire le frame le plus ancien (FIFO)."""
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer.pop(0)
    
    def clear(self):
        """Vide le buffer."""
        with self._lock:
            self._buffer.clear()
    
    @property
    def stats(self) -> Dict[str, int]:
        """Statistiques du buffer."""
        with self._lock:
            return {
                "total_frames": self._frame_count,
                "dropped_frames": self._drop_count,
                "current_size": len(self._buffer),
            }


class CaptureWorker(threading.Thread):
    """
    Thread de capture vidéo.
    
    Lit les frames depuis la source (Pepper ou webcam) et les
    dépose dans le FrameBuffer. Tourne en continu jusqu'à stop().
    """
    
    def __init__(self, video_stream, frame_buffer: FrameBuffer, 
                 target_fps: int = 10):
        super().__init__(daemon=True, name="CaptureWorker")
        self._stream = video_stream
        self._buffer = frame_buffer
        self._target_fps = target_fps
        self._frame_interval = 1.0 / target_fps
        self._running = False
        self._capture_count = 0
        self._error_count = 0
    
    def run(self):
        """Boucle de capture."""
        self._running = True
        logger.info(f"CaptureWorker démarré (cible: {self._target_fps} FPS)")
        
        while self._running:
            start_time = time.time()
            
            try:
                frame = self._stream.get_frame()
                if frame is not None:
                    self._buffer.put(frame)
                    self._capture_count += 1
                else:
                    self._error_count += 1
                    time.sleep(0.1)  # Pause si erreur
            except Exception as e:
                logger.error(f"Erreur capture: {e}")
                self._error_count += 1
                time.sleep(0.1)
            
            # Régulation FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, self._frame_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        logger.info("CaptureWorker arrêté")
    
    def stop(self):
        """Arrête le thread de capture."""
        self._running = False
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "captured": self._capture_count,
            "errors": self._error_count,
            "running": self._running,
        }


class EmotionWorker(threading.Thread):
    """
    Thread d'analyse des émotions (DeepFace).
    
    OPTIMISATION : Analyse seulement 1 frame toutes les N secondes
    pour réduire la charge CPU. DeepFace est très lourd (~500ms-2s par frame).

    Améliorations précision (joie/tristesse mieux détectées) :
      - Préprocessing CLAHE (lumière) sur canal L de l'espace LAB
      - Lissage par moyenne mobile exponentielle (EMA) sur les probabilités
        de chaque classe → décision sur le score lissé, pas sur 1 frame
      - Seuil de confiance minimum pour publier un résultat
      - Boost des classes "happy" et "sad" qui sont sous-cotées par DeepFace
        en basse résolution caméra
    """
    
    # Coefficients EMA et de boost (réglés empiriquement pour la cam Pepper)
    EMA_ALPHA = 0.55                # 0=très lissé, 1=pas de lissage
    MIN_CONFIDENCE = 0.32           # seuil pour considérer une émotion stable
    CLASS_BOOST = {                 # multiplicateurs des classes sous-détectées
        "happy": 1.20,
        "sad":   1.20,
        "fear":  1.05,
        "angry": 1.05,
    }
    EMOTION_CLASSES = (
        "angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"
    )
    
    def __init__(self, frame_buffer: FrameBuffer, 
                 result_queue: Queue,
                 analysis_interval: float = 1.2,
                 use_server: bool = False,
                 server_url: str = "http://localhost:5000/api/vision/emotion"):
        super().__init__(daemon=True, name="EmotionWorker")
        self._buffer = frame_buffer
        self._results = result_queue
        self._interval = analysis_interval
        self._use_server = use_server
        self._server_url = server_url
        self._running = False
        self._analysis_count = 0
        self._last_emotion = "neutral"
        # Probabilités lissées par classe (initialisées à 0)
        self._ema = {k: 0.0 for k in self.EMOTION_CLASSES}
        self._last_published = None  # évite spam du même résultat
        
        # Import paresseux de DeepFace (seulement si local)
        self._deepface = None
        if not use_server:
            self._init_deepface()
    
    def _init_deepface(self):
        """Initialise DeepFace (lourd, fait une seule fois)."""
        try:
            from deepface import DeepFace
            self._deepface = DeepFace
            logger.info("DeepFace chargé (mode local)")
        except ImportError:
            logger.warning("DeepFace non disponible - mode serveur forcé")
            self._use_server = True

    # ------------------------------------------------------------------
    @staticmethod
    def _preprocess(frame: np.ndarray) -> np.ndarray:
        """Améliore le contraste (CLAHE sur canal L) pour mieux exposer le visage."""
        try:
            import cv2
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            l = clahe.apply(l)
            return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
        except Exception:
            return frame

    def _normalize_scores(self, raw: Dict[str, float]) -> Dict[str, float]:
        """Convertit les scores DeepFace (0-100 ou 0-1) en distribution 0-1 sommée à 1."""
        if not raw:
            return {}
        scores = {k: float(raw.get(k, 0.0)) for k in self.EMOTION_CLASSES}
        # DeepFace retourne souvent en 0-100
        if max(scores.values()) > 1.5:
            scores = {k: v / 100.0 for k, v in scores.items()}
        # Boost des classes sous-cotées
        scores = {k: v * self.CLASS_BOOST.get(k, 1.0) for k, v in scores.items()}
        # Renormalisation
        total = sum(scores.values()) or 1.0
        return {k: v / total for k, v in scores.items()}

    def _update_ema(self, scores: Dict[str, float]) -> None:
        """Mise à jour exponentielle des scores lissés."""
        a = self.EMA_ALPHA
        for k in self.EMOTION_CLASSES:
            self._ema[k] = a * scores.get(k, 0.0) + (1.0 - a) * self._ema[k]

    def _stable_emotion(self) -> tuple:
        """Renvoie (emotion, confiance) la plus probable selon l'EMA."""
        if not self._ema:
            return ("neutral", 0.0)
        emotion = max(self._ema, key=self._ema.get)
        return (emotion, float(self._ema[emotion]))

    # ------------------------------------------------------------------
    def _analyze_local(self, frame: np.ndarray) -> Optional[Dict[str, float]]:
        """Analyse locale avec DeepFace. Retourne le dict des scores par classe."""
        if self._deepface is None:
            return None
        try:
            results = self._deepface.analyze(
                frame, 
                actions=['emotion'], 
                enforce_detection=False,
                silent=True
            )
            return results[0].get('emotion', {})
        except Exception as e:
            logger.debug(f"Erreur DeepFace: {e}")
            return None
    
    def _analyze_server(self, frame: np.ndarray) -> Optional[Dict[str, float]]:
        """Envoie le frame au serveur Flask et retourne le dict des scores."""
        try:
            import requests
            import cv2
            import base64
            
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            response = requests.post(
                self._server_url,
                json={"image": img_base64},
                timeout=5
            )
            if response.status_code == 200:
                payload = response.json()
                return payload.get("all_emotions") or {payload.get("emotion", "neutral"): 1.0}
        except Exception as e:
            logger.debug(f"Erreur serveur vision: {e}")
        return None
    
    def run(self):
        """Boucle d'analyse des émotions."""
        self._running = True
        logger.info(f"EmotionWorker démarré (intervalle: {self._interval}s, "
                   f"mode: {'serveur' if self._use_server else 'local'})")
        
        while self._running:
            start_time = time.time()

            # Gate : DeepFace inutile si la surveillance est désactivée OU
            #        si le mode courant est "emergency" (camera réservée à
            #        la détection d'étouffement/respiration).
            mode = _vision_mode()
            if not mode or mode == "emergency":
                # purge état entre deux sessions pour éviter les biais
                self._ema = {k: 0.0 for k in self.EMOTION_CLASSES}
                self._last_published = None
                time.sleep(0.5)
                continue

            # Récupérer le frame le plus récent
            frame_data = self._buffer.get()
            if frame_data is not None:
                frame, timestamp = frame_data
                frame = self._preprocess(frame)
                
                # Analyser
                if self._use_server:
                    raw_scores = self._analyze_server(frame)
                else:
                    raw_scores = self._analyze_local(frame)

                if raw_scores:
                    scores = self._normalize_scores(raw_scores)
                    self._update_ema(scores)
                    emotion, confidence = self._stable_emotion()

                    # Publier seulement si la confiance lissée est suffisante
                    # ET si l'émotion change OU dépasse un palier.
                    if (
                        confidence >= self.MIN_CONFIDENCE
                        and (emotion != self._last_published or emotion in ("sad", "angry", "fear"))
                    ):
                        self._last_emotion = emotion
                        self._last_published = emotion
                        self._analysis_count += 1
                        result = AnalysisResult(
                            type=AnalysisType.EMOTION,
                            value=emotion,
                            confidence=confidence,
                            timestamp=timestamp,
                            metadata={"scores": dict(self._ema)},
                        )
                        try:
                            self._results.put_nowait(result)
                        except Full:
                            pass
            
            # Attendre avant prochaine analyse
            elapsed = time.time() - start_time
            sleep_time = max(0.1, self._interval - elapsed)
            
            # Sleep interruptible
            end_wait = time.time() + sleep_time
            while self._running and time.time() < end_wait:
                time.sleep(0.1)
        
        logger.info("EmotionWorker arrêté")
    
    def stop(self):
        self._running = False
    
    @property
    def last_emotion(self) -> str:
        return self._last_emotion
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "analyses": self._analysis_count,
            "last_emotion": self._last_emotion,
            "mode": "server" if self._use_server else "local",
            "running": self._running,
        }


class EmergencyWorker(threading.Thread):
    """
    Thread de détection d'urgences (MediaPipe).
    
    Plus fréquent que EmotionWorker car les urgences sont critiques.
    MediaPipe est plus léger que DeepFace (~50-100ms).
    """
    
    def __init__(self, frame_buffer: FrameBuffer,
                 result_queue: Queue,
                 analysis_interval: float = 0.5,
                 patient_id: str = "UNKNOWN"):
        super().__init__(daemon=True, name="EmergencyWorker")
        self._buffer = frame_buffer
        self._results = result_queue
        self._interval = analysis_interval
        self._patient_id = patient_id
        self._running = False
        self._detector = None
        self._analysis_count = 0
        self._emergency_count = 0
    
    def _init_detector(self):
        """Initialise le détecteur d'urgences."""
        try:
            from emergency_detector import EmergencyDetector
            self._detector = EmergencyDetector()
            logger.info("EmergencyDetector initialisé")
        except ImportError as e:
            logger.error(f"Impossible de charger EmergencyDetector: {e}")
    
    def run(self):
        """Boucle de détection d'urgences."""
        self._init_detector()
        if self._detector is None:
            logger.error("EmergencyWorker ne peut pas démarrer (detector manquant)")
            return
        
        self._running = True
        logger.info(f"EmergencyWorker démarré (intervalle: {self._interval}s)")
        
        while self._running:
            start_time = time.time()

            # Gate : pas d'analyse d'urgence tant que la surveillance n'est pas activée
            # ET seulement si le mode est "emergency" ou "both" (en mode "emotion" pur,
            # on n'observe que le visage — aucune détection d'étouffement).
            mode = _vision_mode()
            if not mode or mode == "emotion":
                time.sleep(0.5)
                continue

            frame_data = self._buffer.get()
            if frame_data is not None:
                frame, timestamp = frame_data
                
                try:
                    is_emergency, reason = self._detector.analyze_frame(frame)
                    self._analysis_count += 1
                    
                    if is_emergency:
                        self._emergency_count += 1
                        result = AnalysisResult(
                            type=AnalysisType.EMERGENCY,
                            value=reason,
                            confidence=1.0,
                            timestamp=timestamp,
                            metadata={"patient_id": self._patient_id}
                        )
                        try:
                            self._results.put_nowait(result)
                        except Full:
                            # Urgence = prioritaire, forcer l'insertion
                            try:
                                self._results.get_nowait()
                                self._results.put_nowait(result)
                            except Empty:
                                pass
                except Exception as e:
                    logger.debug(f"Erreur analyse urgence: {e}")
            
            # Régulation
            elapsed = time.time() - start_time
            sleep_time = max(0.05, self._interval - elapsed)
            time.sleep(sleep_time)
        
        logger.info("EmergencyWorker arrêté")
    
    def stop(self):
        self._running = False
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "analyses": self._analysis_count,
            "emergencies": self._emergency_count,
            "running": self._running,
        }


class AsyncVisionPipeline:
    """
    Pipeline de vision asynchrone non-bloquant.
    
    Coordonne les workers et gère les résultats.
    
    Usage:
        pipeline = AsyncVisionPipeline(video_stream, pepper_session)
        pipeline.start()
        
        # Dans la boucle principale (non-bloquante) :
        results = pipeline.get_results()  # Retourne immédiatement
        for result in results:
            handle_result(result)
        
        pipeline.stop()
    """
    
    def __init__(self, 
                 video_stream,
                 pepper_session=None,
                 patient_id: str = "UNKNOWN",
                 alert_url: str = "http://localhost:5000/api/alerts",
                 use_server_vision: bool = False,
                 emotion_interval: float = 1.2,
                 emergency_interval: float = 0.4):
        
        self._stream = video_stream
        self._pepper_session = pepper_session
        self._patient_id = patient_id
        self._alert_url = alert_url
        
        # Composants internes
        self._frame_buffer = FrameBuffer(max_size=3)
        self._result_queue = Queue(maxsize=20)
        
        # Workers
        self._capture_worker = CaptureWorker(
            video_stream=video_stream,
            frame_buffer=self._frame_buffer,
            target_fps=10
        )
        self._emotion_worker = EmotionWorker(
            frame_buffer=self._frame_buffer,
            result_queue=self._result_queue,
            analysis_interval=emotion_interval,
            use_server=use_server_vision,
        )
        self._emergency_worker = EmergencyWorker(
            frame_buffer=self._frame_buffer,
            result_queue=self._result_queue,
            analysis_interval=emergency_interval,
            patient_id=patient_id,
        )
        
        # Services Pepper (optionnels)
        self._leds = None
        self._tts = None
        if pepper_session:
            try:
                self._leds = pepper_session.service("ALLeds")
                self._tts = pepper_session.service("ALTextToSpeech")
            except Exception:
                pass
        
        # Alert system
        from alert_system import AlertSystem
        self._alert_system = AlertSystem(dashboard_url=alert_url)
        
        # État
        self._started = False
        self._last_emotion = "neutral"

        # ── Identification patient (obligatoire avant alerte) ──────────────
        # Alerte d'urgence différée si le patient est inconnu au moment de
        # la détection. Elle est envoyée dès que l'identification est confirmée.
        self._pending_emergency = None   # (reason: str, queued_at: float) | None
        self._last_id_request_time = 0.0
        self._id_request_cooldown  = 30.0  # secondes entre deux demandes

        # ── Gate d'activation de la surveillance émotionnelle ───────────────
        # Rasa écrit le flag logs/vision_enabled.flag quand la conversation
        # justifie une surveillance (patient dit qu'il ne va pas bien, etc.).
        # Tant que le flag n'existe pas, aucune alerte n'est générée.
        self._vision_flag_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "logs", "vision_enabled.flag"
        )

        logger.info("AsyncVisionPipeline initialisé (surveillance émotionnelle en attente d'activation par Rasa)")

    def _is_vision_monitoring_enabled(self) -> bool:
        """Retourne True si Rasa a activé la surveillance (flag fichier présent)."""
        return os.path.exists(self._vision_flag_path)

    # ── Helpers identification ─────────────────────────────────────────────

    def _get_db_path(self) -> str:
        """Retourne le chemin absolu vers medibot.db."""
        from pathlib import Path
        db_env = os.getenv("DB_PATH", "")
        if db_env:
            p = Path(db_env)
            return str(p) if p.is_absolute() else str(Path(__file__).resolve().parent.parent / p)
        return str(Path(__file__).resolve().parent.parent / "database" / "medibot.db")

    def _get_db_patient_id(self) -> Optional[str]:
        """
        Lit le patient identifié dans current_patient_session (DB partagée avec Rasa).
        Retourne None si inconnu ou session expirée (> 4 h).
        """
        try:
            import sqlite3
            from datetime import datetime, timedelta
            conn = sqlite3.connect(self._get_db_path())
            cursor = conn.cursor()
            cursor.execute(
                "SELECT patient_id, identified_at FROM current_patient_session WHERE id = 1"
            )
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            patient_id, identified_at = row
            try:
                if datetime.now() - datetime.fromisoformat(str(identified_at)) > timedelta(hours=4):
                    return None
            except Exception:
                pass
            return patient_id
        except Exception as e:
            logger.debug(f"Erreur lecture current_patient_session: {e}")
            return None

    def _resolve_patient_id(self) -> bool:
        """
        Tente de résoudre l'identité du patient :
        1. self._patient_id déjà connu
        2. DB remplie par Rasa via ActionIdentifyPatient
        Retourne True si identifié, met à jour self._patient_id en cache.
        """
        if self._patient_id and self._patient_id.upper() not in ("UNKNOWN", "INCONNU", "NONE", "NULL", ""):
            return True
        db_id = self._get_db_patient_id()
        if db_id:
            logger.info(f"Patient identifié depuis DB : {db_id}")
            self._patient_id = db_id
            self._emergency_worker._patient_id = db_id   # propager au worker
            return True
        return False

    def _write_emergency_flag(self, reason: str) -> None:
        """Écrit un fichier flag pour signaler une urgence active au pont vocal."""
        try:
            flag = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "logs", "emergency.flag"
            )
            with open(flag, "w", encoding="utf-8") as fh:
                fh.write(f"{time.time()}\n{reason}")
        except Exception as e:
            logger.debug(f"Impossible d'écrire le flag d'urgence: {e}")

    def _ask_for_identification(self) -> None:
        """
        Demande vocalement au patient de se présenter.
        Respecte un cooldown de _id_request_cooldown secondes.
        """
        now = time.time()
        if now - self._last_id_request_time < self._id_request_cooldown:
            return
        self._last_id_request_time = now
        msg = "Je ne vous reconnais pas. Pouvez-vous me dire votre nom ?"
        logger.warning(f"[IDENT] Demande identification : {msg}")
        if self._tts:
            try:
                self._tts.say(msg)
            except Exception as e:
                logger.debug(f"TTS erreur ident: {e}")
        else:
            print(f"[MediBot] {msg}")

    def _fire_pending_emergency(self) -> None:
        """
        Envoie l'alerte d'urgence différée si le patient est maintenant identifié.
        Abandonne l'alerte si elle est en attente depuis plus de 3 minutes.
        """
        if not self._pending_emergency:
            return
        reason, queued_at = self._pending_emergency
        if time.time() - queued_at > 180:   # 3 min max
            logger.warning(f"[IDENT] Alerte urgence expirée (patient non identifié) : {reason}")
            self._pending_emergency = None
            return
        if self._resolve_patient_id():
            logger.warning(f"[IDENT] ✅ Patient identifié ({self._patient_id}) — envoi alerte différée : {reason}")
            self._pending_emergency = None
            self._alert_system.send_alert(
                level=2,
                reason=reason,
                patient_id=self._patient_id,
            )
            # Signaler au pont vocal que le dialogue doit être suspendu
            self._write_emergency_flag(reason)
            if self._leds:
                try:
                    self._leds.fadeRGB("FaceLeds", 0xFF0000, 0.5)
                except Exception:
                    pass
    
    def start(self):
        """Démarre tous les workers."""
        if self._started:
            return
        
        # État initial propre : surveillance désactivée jusqu'à autorisation Rasa
        try:
            if os.path.exists(_VISION_FLAG_PATH):
                os.remove(_VISION_FLAG_PATH)
                logger.info("Flag vision_enabled.flag nettoyé au démarrage")
        except Exception:
            pass

        logger.info("Démarrage AsyncVisionPipeline...")
        self._capture_worker.start()
        self._emotion_worker.start()
        self._emergency_worker.start()
        self._started = True
        logger.info("AsyncVisionPipeline démarré (3 workers actifs)")
    
    def stop(self):
        """Arrête tous les workers."""
        if not self._started:
            return
        
        logger.info("Arrêt AsyncVisionPipeline...")
        self._capture_worker.stop()
        self._emotion_worker.stop()
        self._emergency_worker.stop()
        
        # Attendre la fin des threads
        self._capture_worker.join(timeout=2.0)
        self._emotion_worker.join(timeout=2.0)
        self._emergency_worker.join(timeout=2.0)
        
        # Libérer la caméra
        if hasattr(self._stream, 'release'):
            self._stream.release()
        
        self._started = False
        logger.info("AsyncVisionPipeline arrêté")
    
    def get_results(self, max_results: int = 10) -> list:
        """
        Récupère les résultats disponibles (NON-BLOQUANT).
        
        Returns:
            Liste de AnalysisResult (peut être vide)
        """
        results = []
        for _ in range(max_results):
            try:
                result = self._result_queue.get_nowait()
                results.append(result)
            except Empty:
                break
        return results
    
    def process_results(self) -> list:
        """
        Récupère ET traite les résultats (alertes, LEDs, etc.).

        Cette méthode gère automatiquement les réactions aux émotions
        et l'envoi des alertes d'urgence.

        Returns:
            Liste des résultats traités
        """        # ── Gate : Rasa doit avoir activé la surveillance ───────────────────
        # Tant que le flag n'existe pas, on purge la queue sans rien traiter.
        # Le dialogue social reste donc parfaitement neutre au démarrage.
        if not self._is_vision_monitoring_enabled():
            # Vider la queue pour éviter l'accumulation
            while True:
                try:
                    self._result_queue.get_nowait()
                except Empty:
                    break
            return []
        # Tenter d'envoyer une alerte d'urgence différée si le patient est
        # maintenant identifié (identificationvocale traitée par Rasa)
        self._fire_pending_emergency()

        results = self.get_results()
        
        for result in results:
            if result.type == AnalysisType.EMERGENCY:
                # Urgence = priorité maximale
                self._handle_emergency(result)
            elif result.type == AnalysisType.EMOTION:
                self._handle_emotion(result)
        
        return results
    
    def _get_patient_full_name(self) -> str:
        """Lit le nom complet du patient depuis current_patient_session (DB)."""
        try:
            import sqlite3
            conn = sqlite3.connect(self._get_db_path())
            cur = conn.cursor()
            cur.execute(
                "SELECT first_name, last_name FROM current_patient_session WHERE id = 1"
            )
            row = cur.fetchone()
            conn.close()
            if row:
                fn, ln = row
                return f"{fn} {ln}".strip()
        except Exception:
            pass
        return ""

    def _handle_emergency(self, result: AnalysisResult):
        """Gère une alerte d'urgence.

        Règle stricte : le patient DOIT être identifié avant l'envoi de l'alerte.
        Si inconnu, le robot demande le nom et diffère l'alerte jusqu'à confirmation.
        """
        logger.warning(f"URGENCE: {result.value}")

        # ── Identification obligatoire ──────────────────────────────────────
        if not self._resolve_patient_id():
            logger.warning(
                f"[IDENT] Urgence détectée mais patient inconnu — alerte différée : {result.value}"
            )
            if not self._pending_emergency:
                self._pending_emergency = (result.value, time.time())
            self._ask_for_identification()
            return

        # Patient identifié → envoyer immédiatement
        patient_id = result.metadata.get("patient_id", self._patient_id)
        if patient_id == "UNKNOWN":
            patient_id = self._patient_id

        # Enrichir le motif avec le nom du patient si dispo
        full_name = self._get_patient_full_name()
        reason_with_name = (
            f"{result.value} — patient : {full_name} ({patient_id})"
            if full_name else f"{result.value} — patient : {patient_id}"
        )

        self._alert_system.send_alert(
            level=2,
            reason=reason_with_name,
            patient_id=patient_id,
            alert_type="emergency",
            severity="critical",
        )

        # Signaler au pont vocal que le dialogue doit être suspendu
        self._write_emergency_flag(reason_with_name)

        # LEDs rouges clignotantes
        if self._leds:
            try:
                self._leds.fadeRGB("FaceLeds", 0xFF0000, 0.5)
            except Exception:
                pass

        # Message vocal d'alerte (avec nom du patient)
        if self._tts:
            try:
                msg = (
                    f"Urgence détectée pour {full_name}. L'équipe médicale a été alertée."
                    if full_name else "Urgence détectée. L'équipe médicale a été alertée."
                )
                self._tts.say(msg)
            except Exception:
                pass

    def _handle_emotion(self, result: AnalysisResult):
        """Gère une détection d'émotion.

        Si le mode courant est "emotion" (le patient a dit aller bien) et qu'une
        émotion de détresse est détectée → alerte "incohérence" : la parole et
        l'expression faciale ne concordent pas.
        """
        emotion = result.value
        self._last_emotion = emotion
        mode = _vision_mode()

        try:
            from emotion_rules import get_medibot_reaction
            reaction = get_medibot_reaction(emotion)

            # LEDs selon l'émotion
            if self._leds and reaction.get("led_hex"):
                try:
                    self._leds.fadeRGB("FaceLeds", reaction["led_hex"], 1.0)
                except Exception:
                    pass

            # Alerte si émotion critique
            if reaction.get("alert"):
                if not self._resolve_patient_id():
                    self._ask_for_identification()
                    return
                full_name = self._get_patient_full_name()
                sev = reaction.get("severity", "medium")
                conf = getattr(result, "confidence", 0.0)

                if mode == "emotion":
                    # Coh\u00e9rence : le patient a affirm\u00e9 aller bien
                    reason = (
                        f"Incohérence détectée — patient {full_name or self._patient_id} "
                        f"a dit aller bien mais l'émotion observée est '{emotion}' "
                        f"(confiance {conf:.0%})"
                    )
                else:
                    reason = (
                        f"Émotion '{emotion}' détectée pour {full_name or self._patient_id} "
                        f"(confiance {conf:.0%})"
                    )

                self._alert_system.send_alert(
                    level=2 if sev in ("high", "critical") else 1,
                    reason=reason,
                    patient_id=self._patient_id,
                    alert_type="emotion",
                    severity=sev,
                )
        except ImportError:
            pass
    
    @property
    def last_emotion(self) -> str:
        """Dernière émotion détectée."""
        return self._emotion_worker.last_emotion
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Statistiques du pipeline."""
        return {
            "started": self._started,
            "buffer": self._frame_buffer.stats,
            "capture": self._capture_worker.stats,
            "emotion": self._emotion_worker.stats,
            "emergency": self._emergency_worker.stats,
        }
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()
