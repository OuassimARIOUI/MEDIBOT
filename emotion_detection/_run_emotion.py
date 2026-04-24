
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Charger .env
try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

PEPPER_IP = os.getenv("PEPPER_IP")
PEPPER_PORT = int(os.getenv("PEPPER_PORT", "9559"))

pep_session = None
if PEPPER_IP:
    try:
        import qi
        pep_session = qi.Session()
        pep_session.connect(f"tcp://{PEPPER_IP}:{PEPPER_PORT}")
        print(f"[EMOTION] Session Pepper -> {PEPPER_IP}")
    except Exception as e:
        print(f"[EMOTION] Pepper non connecte ({e}), mode webcam PC")

from emotion_detector import EmotionPipeline
from emergency_detector import EmergencyDetector
from video_stream import VideoStream
from alert_system import AlertSystem

PATIENT_ID = os.getenv("PATIENT_ID", "PAT001")

pipeline = EmotionPipeline(
    patient_id=PATIENT_ID,
    pepper_session=pep_session
)
emergency = EmergencyDetector(patient_id=PATIENT_ID)

# Singleton AlertSystem (conserve le rate-limiting entre les appels)
alert_sys = AlertSystem()

video_src = "pepper" if pep_session else 0
stream = VideoStream(source=video_src, pepper_session=pep_session)

# Chemins des fichiers flag (communication inter-processus)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMERGENCY_FLAG = os.path.join(PROJECT_ROOT, "logs", "emergency.flag")
VISION_FLAG = os.path.join(PROJECT_ROOT, "logs", "vision_enabled.flag")
os.makedirs(os.path.join(PROJECT_ROOT, "logs"), exist_ok=True)

def is_vision_enabled():
    """Rasa active la surveillance via ce flag."""
    return os.path.exists(VISION_FLAG)

def write_emergency_flag(reason):
    """Signale une urgence a voice_bridge pour suspendre le dialogue."""
    try:
        with open(EMERGENCY_FLAG, "w", encoding="utf-8") as f:
            f.write(f"{time.time()}\n{reason}")
    except Exception:
        pass

print(f"[EMOTION] Demarrage (source={video_src})...")
print("[EMOTION] En attente du flag vision_enabled.flag (active par Rasa)...")

try:
    while True:
        # Gate : pas d analyse tant que Rasa n a pas active la surveillance
        if not is_vision_enabled():
            time.sleep(0.5)
            continue

        frame = stream.get_frame()
        if frame is None:
            time.sleep(0.2)
            continue

        # 1) Detection emotions (avec stabilisation interne)
        emotion = pipeline.process_frame(frame)

        # 2) Detection urgences (etouffement, respiration)
        #    EmergencyDetector gere sa propre stabilisation (3 frames)
        is_emerg, reason = emergency.analyze_frame(frame)
        if is_emerg:
            print(f"[URGENCE] {reason}")
            # Ecrire le flag pour que voice_bridge suspende le dialogue
            write_emergency_flag(reason)
            # Envoyer l alerte (rate-limited par AlertSystem)
            alert_sys.send_alert(
                level=2, reason=reason,
                patient_id=PATIENT_ID,
                alert_type="emergency", severity="critical"
            )

        time.sleep(0.2)
except KeyboardInterrupt:
    pass
finally:
    stream.release()
    print("[EMOTION] Arret.")
