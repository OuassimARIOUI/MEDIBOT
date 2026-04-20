"""
failover_manager.py — Gestionnaire de mode dégradé.

Implémente le "Failover Mode" décrit dans le cahier des charges :
- Surveille les ressources système (CPU, mémoire)
- Désactive automatiquement les modules lourds si surcharge
- Maintient les fonctions critiques (urgences vitales)
- Réactive progressivement les modules quand la charge diminue

Niveaux de dégradation :
  LEVEL 0 (NORMAL)    : Tout actif (emotions + urgences + audio)
  LEVEL 1 (MODERATE)  : Désactive DeepFace, garde MediaPipe
  LEVEL 2 (CRITICAL)  : Urgences vitales uniquement (respiration/étouffement)
  LEVEL 3 (MINIMAL)   : Arrêt vision, mode audio seul (Whisper/Rasa)

Auteur: MediBot Team - Optimisation Latence
"""

import os
import sys
import time
import logging
import threading
from enum import IntEnum
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
from queue import Queue

logger = logging.getLogger(__name__)


class DegradationLevel(IntEnum):
    """Niveaux de dégradation du système."""
    NORMAL = 0      # Tout actif
    MODERATE = 1    # DeepFace désactivé
    CRITICAL = 2    # Urgences uniquement
    MINIMAL = 3     # Audio seul


@dataclass
class SystemMetrics:
    """Métriques système."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    analysis_latency: float = 0.0  # Temps moyen d'analyse (secondes)
    frame_drop_rate: float = 0.0   # Taux de frames perdues
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class FailoverConfig:
    """Configuration des seuils de dégradation."""
    
    # Seuils CPU (%)
    CPU_MODERATE = 70.0     # Passer en MODERATE
    CPU_CRITICAL = 85.0     # Passer en CRITICAL
    CPU_MINIMAL = 95.0      # Passer en MINIMAL
    CPU_RECOVER = 60.0      # Seuil de récupération
    
    # Seuils mémoire (%)
    MEM_CRITICAL = 85.0
    MEM_MINIMAL = 95.0
    
    # Seuils latence analyse (secondes)
    LATENCY_MODERATE = 1.0   # DeepFace > 1s = dégradé
    LATENCY_CRITICAL = 2.0   # > 2s = critique
    
    # Seuils frame drop (%)
    DROP_MODERATE = 20.0
    DROP_CRITICAL = 50.0
    
    # Temps minimum entre changements de niveau (évite oscillation)
    STABILIZATION_TIME = 10.0  # secondes
    
    # Intervalle de monitoring
    MONITOR_INTERVAL = 2.0  # secondes


class FailoverManager:
    """
    Gestionnaire de mode dégradé automatique.
    
    Surveille les métriques système et ajuste dynamiquement
    les modules actifs pour maintenir la réactivité.
    
    Usage:
        manager = FailoverManager()
        manager.register_callback('on_level_change', my_callback)
        manager.start()
        
        # Dans la boucle principale :
        level = manager.current_level
        if level >= DegradationLevel.MODERATE:
            # Désactiver DeepFace
            
        manager.stop()
    """
    
    def __init__(self, config: FailoverConfig = None):
        self._config = config or FailoverConfig()
        self._current_level = DegradationLevel.NORMAL
        self._metrics_history: List[SystemMetrics] = []
        self._max_history = 30  # 1 minute à 2s d'intervalle
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'on_level_change': [],
            'on_metrics_update': [],
        }
        
        # Thread de monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._last_level_change = 0.0
        
        # Latence tracking (alimenté de l'extérieur)
        self._last_analysis_latency = 0.0
        self._frame_drop_rate = 0.0
        
        logger.info("FailoverManager initialisé")
    
    def register_callback(self, event: str, callback: Callable):
        """Enregistre un callback pour un événement."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _notify(self, event: str, *args, **kwargs):
        """Notifie les callbacks enregistrés."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Erreur callback {event}: {e}")
    
    def start(self):
        """Démarre le monitoring."""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="FailoverMonitor"
        )
        self._monitor_thread.start()
        logger.info("FailoverManager démarré")
    
    def stop(self):
        """Arrête le monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=3.0)
        logger.info("FailoverManager arrêté")
    
    def _get_system_metrics(self) -> SystemMetrics:
        """Récupère les métriques système actuelles."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
        except ImportError:
            # psutil non disponible, utiliser des valeurs par défaut
            cpu = 50.0
            mem = 50.0
            logger.debug("psutil non disponible, métriques simulées")
        
        return SystemMetrics(
            cpu_percent=cpu,
            memory_percent=mem,
            analysis_latency=self._last_analysis_latency,
            frame_drop_rate=self._frame_drop_rate,
        )
    
    def update_latency(self, latency: float):
        """Met à jour la latence d'analyse (appelé par le pipeline)."""
        self._last_analysis_latency = latency
    
    def update_drop_rate(self, rate: float):
        """Met à jour le taux de frame drop (appelé par le pipeline)."""
        self._frame_drop_rate = rate
    
    def _calculate_level(self, metrics: SystemMetrics) -> DegradationLevel:
        """Calcule le niveau de dégradation basé sur les métriques."""
        cfg = self._config
        
        # Critères MINIMAL (urgence)
        if metrics.cpu_percent >= cfg.CPU_MINIMAL or \
           metrics.memory_percent >= cfg.MEM_MINIMAL:
            return DegradationLevel.MINIMAL
        
        # Critères CRITICAL
        if metrics.cpu_percent >= cfg.CPU_CRITICAL or \
           metrics.memory_percent >= cfg.MEM_CRITICAL or \
           metrics.analysis_latency >= cfg.LATENCY_CRITICAL or \
           metrics.frame_drop_rate >= cfg.DROP_CRITICAL:
            return DegradationLevel.CRITICAL
        
        # Critères MODERATE
        if metrics.cpu_percent >= cfg.CPU_MODERATE or \
           metrics.analysis_latency >= cfg.LATENCY_MODERATE or \
           metrics.frame_drop_rate >= cfg.DROP_MODERATE:
            return DegradationLevel.MODERATE
        
        # Récupération : on ne revient à NORMAL que si tout est bas
        if self._current_level > DegradationLevel.NORMAL:
            if metrics.cpu_percent < cfg.CPU_RECOVER and \
               metrics.analysis_latency < cfg.LATENCY_MODERATE * 0.5:
                return DegradationLevel.NORMAL
            # Sinon garder le niveau actuel
            return self._current_level
        
        return DegradationLevel.NORMAL
    
    def _monitor_loop(self):
        """Boucle de monitoring."""
        while self._running:
            try:
                # Collecter métriques
                metrics = self._get_system_metrics()
                self._metrics_history.append(metrics)
                if len(self._metrics_history) > self._max_history:
                    self._metrics_history.pop(0)
                
                self._notify('on_metrics_update', metrics)
                
                # Calculer nouveau niveau
                new_level = self._calculate_level(metrics)
                
                # Stabilisation : éviter oscillations
                now = time.time()
                if new_level != self._current_level:
                    if now - self._last_level_change >= self._config.STABILIZATION_TIME:
                        old_level = self._current_level
                        self._current_level = new_level
                        self._last_level_change = now
                        
                        logger.warning(
                            f"FAILOVER: {old_level.name} → {new_level.name} "
                            f"(CPU={metrics.cpu_percent:.1f}%, "
                            f"latency={metrics.analysis_latency:.2f}s)"
                        )
                        self._notify('on_level_change', old_level, new_level, metrics)
                
            except Exception as e:
                logger.error(f"Erreur monitoring: {e}")
            
            time.sleep(self._config.MONITOR_INTERVAL)
    
    @property
    def current_level(self) -> DegradationLevel:
        """Niveau de dégradation actuel."""
        return self._current_level
    
    @property
    def is_degraded(self) -> bool:
        """True si le système est en mode dégradé."""
        return self._current_level > DegradationLevel.NORMAL
    
    @property
    def emotion_enabled(self) -> bool:
        """True si la détection d'émotions doit être active."""
        return self._current_level == DegradationLevel.NORMAL
    
    @property
    def emergency_enabled(self) -> bool:
        """True si la détection d'urgences doit être active."""
        return self._current_level <= DegradationLevel.CRITICAL
    
    @property
    def vision_enabled(self) -> bool:
        """True si la vision doit être active."""
        return self._current_level < DegradationLevel.MINIMAL
    
    @property
    def latest_metrics(self) -> Optional[SystemMetrics]:
        """Dernières métriques collectées."""
        return self._metrics_history[-1] if self._metrics_history else None
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut complet du failover."""
        metrics = self.latest_metrics
        return {
            "level": self._current_level.name,
            "level_value": int(self._current_level),
            "is_degraded": self.is_degraded,
            "emotion_enabled": self.emotion_enabled,
            "emergency_enabled": self.emergency_enabled,
            "vision_enabled": self.vision_enabled,
            "metrics": {
                "cpu_percent": metrics.cpu_percent if metrics else 0,
                "memory_percent": metrics.memory_percent if metrics else 0,
                "analysis_latency": metrics.analysis_latency if metrics else 0,
                "frame_drop_rate": metrics.frame_drop_rate if metrics else 0,
            } if metrics else None,
            "history_size": len(self._metrics_history),
        }
    
    def force_level(self, level: DegradationLevel):
        """Force un niveau de dégradation (pour tests ou contrôle manuel)."""
        old_level = self._current_level
        self._current_level = level
        self._last_level_change = time.time()
        logger.info(f"FAILOVER forcé: {old_level.name} → {level.name}")
        self._notify('on_level_change', old_level, level, self.latest_metrics)


# Singleton global pour accès facile
_failover_instance: Optional[FailoverManager] = None

def get_failover_manager() -> FailoverManager:
    """Retourne l'instance singleton du FailoverManager."""
    global _failover_instance
    if _failover_instance is None:
        _failover_instance = FailoverManager()
    return _failover_instance


def is_emotion_enabled() -> bool:
    """Raccourci pour vérifier si la détection d'émotions est active."""
    return get_failover_manager().emotion_enabled


def is_emergency_enabled() -> bool:
    """Raccourci pour vérifier si la détection d'urgences est active."""
    return get_failover_manager().emergency_enabled
