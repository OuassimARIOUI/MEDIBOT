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
    """
    
    def __init__(self, frame_buffer: FrameBuffer, 
                 result_queue: Queue,
                 analysis_interval: float = 2.0,
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
    
    def _analyze_local(self, frame: np.ndarray) -> Optional[str]:
        """Analyse locale avec DeepFace."""
        if self._deepface is None:
            return None
        try:
            results = self._deepface.analyze(
                frame, 
                actions=['emotion'], 
                enforce_detection=False,
                silent=True
            )
            return results[0]['dominant_emotion']
        except Exception as e:
            logger.debug(f"Erreur DeepFace: {e}")
            return None
    
    def _analyze_server(self, frame: np.ndarray) -> Optional[str]:
        """Envoie le frame au serveur Flask pour analyse."""
        try:
            import requests
            import cv2
            import base64
            
            # Encoder le frame en JPEG puis base64
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            response = requests.post(
                self._server_url,
                json={"image": img_base64},
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get("emotion", "unknown")
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
            
            # Récupérer le frame le plus récent
            frame_data = self._buffer.get()
            if frame_data is not None:
                frame, timestamp = frame_data
                
                # Analyser
                if self._use_server:
                    emotion = self._analyze_server(frame)
                else:
                    emotion = self._analyze_local(frame)
                
                if emotion and emotion != "unknown":
                    self._last_emotion = emotion
                    self._analysis_count += 1
                    
                    result = AnalysisResult(
                        type=AnalysisType.EMOTION,
                        value=emotion,
                        timestamp=timestamp,
                    )
                    try:
                        self._results.put_nowait(result)
                    except Full:
                        pass  # Ignorer si queue pleine
            
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
                 emotion_interval: float = 2.0,
                 emergency_interval: float = 0.5):
        
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

        logger.info("AsyncVisionPipeline initialisé")

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
        if self._patient_id != "UNKNOWN":
            return True
        db_id = self._get_db_patient_id()
        if db_id:
            logger.info(f"Patient identifié depuis DB : {db_id}")
            self._patient_id = db_id
            self._emergency_worker._patient_id = db_id   # propager au worker
            return True
        return False

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
            if self._leds:
                try:
                    self._leds.fadeRGB("FaceLeds", 0xFF0000, 0.5)
                except Exception:
                    pass
    
    def start(self):
        """Démarre tous les workers."""
        if self._started:
            return
        
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
        """
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
            # Ne pas écraser une urgence plus ancienne déjà en attente
            if not self._pending_emergency:
                self._pending_emergency = (result.value, time.time())
            self._ask_for_identification()
            return  # Alerte envoyée ultérieurement par _fire_pending_emergency()

        # Patient identifié → envoyer immédiatement
        patient_id = result.metadata.get("patient_id", self._patient_id)
        if patient_id == "UNKNOWN":
            patient_id = self._patient_id

        self._alert_system.send_alert(
            level=2,
            reason=result.value,
            patient_id=patient_id
        )

        # LEDs rouges clignotantes
        if self._leds:
            try:
                self._leds.fadeRGB("FaceLeds", 0xFF0000, 0.5)
            except Exception:
                pass

        # Message vocal d'alerte
        if self._tts:
            try:
                self._tts.say("")
            except Exception:
                pass
    
    def _handle_emotion(self, result: AnalysisResult):
        """Gère une détection d'émotion."""
        emotion = result.value
        self._last_emotion = emotion
        
        # Importer les règles de réaction
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
                # Identification obligatoire avant toute alerte
                if not self._resolve_patient_id():
                    self._ask_for_identification()
                    return  # Pas d'alerte pour un patient inconnu
                sev = reaction.get("severity", "medium")
                self._alert_system.send_alert(
                    level=2 if sev in ("high", "critical") else 1,
                    reason=f"Émotion détectée: {emotion}",
                    patient_id=self._patient_id,
                    alert_type="emotion",
                    severity=sev
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
