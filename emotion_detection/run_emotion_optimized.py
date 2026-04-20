#!/usr/bin/env python3
"""
run_emotion_optimized.py — Version optimisée de la détection d'émotions.

CHANGEMENTS MAJEURS vs _run_emotion.py :
  1. Pipeline ASYNCHRONE (non-bloquant) via AsyncVisionPipeline
  2. Mode DÉGRADÉ automatique via FailoverManager
  3. Support DÉPORTATION sur serveur Flask (réduit charge CPU Pepper)
  4. Intégration avec voice_bridge (ne bloque plus l'audio)

Architecture :
  - 3 threads indépendants (capture, emotions, urgences)
  - Buffer circulaire pour éviter l'accumulation de frames
  - Détection émotions : ~1 frame / 2-3s (suffisant cliniquement)
  - Détection urgences : ~2-3 frames / sec (critique)
  
Usage :
  python run_emotion_optimized.py [--server] [--local] [--debug]
  
Options :
  --server  : Déporte DeepFace sur le serveur Flask (recommandé pour Pepper)
  --local   : Force le traitement local (défaut si GPU disponible)
  --debug   : Active les logs détaillés

Auteur: MediBot Team - Optimisation Latence
"""

import os
import sys
import time
import argparse
import logging

# --- Setup PYTHONPATH ---
ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
SELF_DIR = os.path.dirname(os.path.abspath(__file__))
if SELF_DIR not in sys.path:
    sys.path.insert(0, SELF_DIR)

# --- Charger .env ---
try:
    from dotenv import load_dotenv
    from pathlib import Path
    _env = Path(__file__).resolve().parent.parent / ".env"
    if _env.exists():
        load_dotenv(dotenv_path=_env)
except ImportError:
    pass

# --- Configuration logging ---
def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )

# --- Configuration ---
PEPPER_IP = os.getenv("PEPPER_IP")
PEPPER_PORT = int(os.getenv("PEPPER_PORT", "9559"))
PATIENT_ID = os.getenv("PATIENT_ID", "PAT001")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:5000/api/alerts")
VISION_SERVER_URL = os.getenv("VISION_SERVER_URL", "http://localhost:5000/api/vision/emotion")

logger = logging.getLogger("EmotionMain")


def check_gpu_available() -> bool:
    """Vérifie si un GPU CUDA est disponible."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def connect_to_pepper():
    """Connecte à Pepper si configuré."""
    if not PEPPER_IP:
        logger.info("PEPPER_IP non défini → mode webcam PC")
        return None
    
    try:
        import qi
        session = qi.Session()
        session.connect(f"tcp://{PEPPER_IP}:{PEPPER_PORT}")
        logger.info(f"Connecté à Pepper → {PEPPER_IP}:{PEPPER_PORT}")
        return session
    except ImportError:
        logger.warning("Module 'qi' non disponible → mode webcam PC")
    except Exception as e:
        logger.warning(f"Connexion Pepper échouée ({e}) → mode webcam PC")
    return None


def run_optimized_pipeline(use_server: bool = False, debug: bool = False):
    """
    Exécute le pipeline de vision optimisé.
    
    Args:
        use_server: Si True, déporte DeepFace sur le serveur Flask
        debug: Si True, active les logs détaillés
    """
    setup_logging(debug)
    
    # Déterminer le mode de traitement
    has_gpu = check_gpu_available()
    if use_server:
        logger.info("Mode: SERVEUR (DeepFace déporté sur Flask)")
    elif has_gpu:
        logger.info("Mode: LOCAL avec GPU CUDA")
        use_server = False
    else:
        logger.info("Mode: LOCAL sur CPU (peut être lent)")
        # Suggérer le mode serveur si pas de GPU
        logger.warning("⚠️  Conseil: Utilisez --server pour déporter DeepFace")
    
    # Connexion Pepper
    pepper_session = connect_to_pepper()
    
    # Source vidéo
    from video_stream import VideoStream
    video_src = "pepper" if pepper_session else 0
    stream = VideoStream(source=video_src, pepper_session=pepper_session)
    logger.info(f"Source vidéo: {'Pepper camera' if pepper_session else 'Webcam PC'}")
    
    # Importer et initialiser les composants optimisés
    from async_vision_pipeline import AsyncVisionPipeline, AnalysisType
    from failover_manager import FailoverManager, DegradationLevel, get_failover_manager
    
    # Pipeline asynchrone
    pipeline = AsyncVisionPipeline(
        video_stream=stream,
        pepper_session=pepper_session,
        patient_id=PATIENT_ID,
        alert_url=DASHBOARD_URL,
        use_server_vision=use_server,
        emotion_interval=2.5,      # DeepFace toutes les 2.5s
        emergency_interval=0.4,    # MediaPipe ~2.5 FPS
    )
    
    # Failover manager
    failover = get_failover_manager()
    
    def on_level_change(old_level, new_level, metrics):
        """Callback quand le niveau de dégradation change."""
        if new_level >= DegradationLevel.MODERATE:
            logger.warning(f"⚠️  MODE DÉGRADÉ activé: {new_level.name}")
            if new_level >= DegradationLevel.CRITICAL:
                logger.warning("   → Détection émotions DÉSACTIVÉE")
            if new_level >= DegradationLevel.MINIMAL:
                logger.error("   → Vision DÉSACTIVÉE (mode audio seul)")
    
    failover.register_callback('on_level_change', on_level_change)
    
    # Démarrer
    print("\n" + "=" * 60)
    print("  MEDIBOT - Détection Visuelle Optimisée")
    print("=" * 60)
    print(f"  Patient    : {PATIENT_ID}")
    print(f"  Source     : {'Pepper' if pepper_session else 'Webcam'}")
    print(f"  DeepFace   : {'Serveur' if use_server else 'Local'}")
    print(f"  Dashboard  : {DASHBOARD_URL}")
    print("=" * 60)
    print("  CTRL+C pour arrêter")
    print("=" * 60 + "\n")
    
    pipeline.start()
    failover.start()
    
    last_status_time = 0
    STATUS_INTERVAL = 10  # Afficher stats toutes les 10s
    
    try:
        while True:
            # Traiter les résultats (non-bloquant)
            results = pipeline.process_results()
            
            for result in results:
                if result.type == AnalysisType.EMERGENCY:
                    print(f"  🚨 URGENCE: {result.value}")
                elif result.type == AnalysisType.EMOTION:
                    print(f"  😊 Émotion: {result.value}")
            
            # Mise à jour failover avec latence du pipeline
            stats = pipeline.stats
            if stats.get('emotion', {}).get('analyses', 0) > 0:
                # Estimer la latence basée sur le drop rate
                buffer_stats = stats.get('buffer', {})
                drop_rate = buffer_stats.get('dropped_frames', 0) / max(
                    buffer_stats.get('total_frames', 1), 1) * 100
                failover.update_drop_rate(drop_rate)
            
            # Vérifier le niveau de dégradation
            if failover.current_level >= DegradationLevel.MINIMAL:
                # Mode minimal : pause la vision
                logger.warning("Vision en pause (surcharge système)")
                time.sleep(5)
                continue
            
            # Affichage périodique des stats
            now = time.time()
            if now - last_status_time > STATUS_INTERVAL:
                last_status_time = now
                stats = pipeline.stats
                failover_status = failover.get_status()
                
                print(f"\n  [STATS] Captures: {stats['capture']['captured']} | "
                      f"Emotions: {stats['emotion']['analyses']} | "
                      f"Urgences: {stats['emergency']['emergencies']} | "
                      f"Mode: {failover_status['level']}")
            
            # Petite pause pour ne pas surcharger (la vraie boucle est dans les threads)
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\n\n[INFO] Arrêt demandé...")
    
    finally:
        pipeline.stop()
        failover.stop()
        print("[INFO] Pipeline arrêté proprement.")


def run_legacy_mode():
    """
    Mode de compatibilité : exécute l'ancien code synchrone.
    Utilisé si les modules optimisés ne sont pas disponibles.
    """
    logger.warning("Exécution en mode LEGACY (synchrone)")
    logger.warning("⚠️  Ce mode peut causer des latences importantes")
    
    # Importer et exécuter l'ancien code
    pepper_session = connect_to_pepper()
    
    from emotion_detector import EmotionPipeline
    from emergency_detector import EmergencyDetector
    from video_stream import VideoStream
    from alert_system import AlertSystem
    
    pipeline = EmotionPipeline(
        patient_id=PATIENT_ID,
        pepper_session=pepper_session,
        alert_url=DASHBOARD_URL,
    )
    emergency = EmergencyDetector()
    alert_sys = AlertSystem(dashboard_url=DASHBOARD_URL)
    
    video_src = "pepper" if pepper_session else 0
    stream = VideoStream(source=video_src, pepper_session=pepper_session)
    
    print(f"[LEGACY] Démarrage (source={'Pepper' if pepper_session else 'webcam'})...")
    
    try:
        while True:
            frame = stream.get_frame()
            if frame is None:
                time.sleep(0.2)
                continue
            
            # Analyse synchrone (BLOQUANT)
            emotion = pipeline.process_frame(frame)
            is_emergency, reason = emergency.analyze_frame(frame)
            
            if is_emergency:
                print(f"[URGENCE] {reason}")
                alert_sys.send_alert(level=2, reason=reason, patient_id=PATIENT_ID)
            
            time.sleep(0.2)
    
    except KeyboardInterrupt:
        print("\n[LEGACY] Arrêt.")
    finally:
        stream.release()


def main():
    parser = argparse.ArgumentParser(
        description="MediBot - Détection visuelle optimisée"
    )
    parser.add_argument(
        '--server', action='store_true',
        help="Déporter DeepFace sur le serveur Flask (recommandé pour Pepper)"
    )
    parser.add_argument(
        '--local', action='store_true',
        help="Forcer le traitement local (même sans GPU)"
    )
    parser.add_argument(
        '--legacy', action='store_true',
        help="Utiliser le mode synchrone legacy (non recommandé)"
    )
    parser.add_argument(
        '--debug', action='store_true',
        help="Activer les logs détaillés"
    )
    
    args = parser.parse_args()
    
    if args.legacy:
        run_legacy_mode()
    else:
        # Déterminer si on utilise le serveur
        use_server = args.server and not args.local
        
        try:
            run_optimized_pipeline(use_server=use_server, debug=args.debug)
        except ImportError as e:
            logger.error(f"Module manquant: {e}")
            logger.warning("Basculement vers le mode legacy...")
            run_legacy_mode()


if __name__ == "__main__":
    main()
