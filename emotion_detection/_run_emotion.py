
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
        print(f"[EMOTION] Session Pepper → {PEPPER_IP}")
    except Exception as e:
        print(f"[EMOTION] Pepper non connecté ({e}), mode webcam PC")

from emotion_detector import EmotionPipeline
from emergency_detector import EmergencyDetector
from video_stream import VideoStream

pipeline = EmotionPipeline(
    patient_id=os.getenv("PATIENT_ID", "PAT001"),
    pepper_session=pep_session
)
emergency = EmergencyDetector()

video_src = "pepper" if pep_session else 0
stream = VideoStream(source=video_src, pepper_session=pep_session)
print(f"[EMOTION] Démarrage (source={video_src})...")

try:
    while True:
        frame = stream.get_frame()
        if frame is None:
            time.sleep(0.2)
            continue
        # 1) Détection émotions
        emotion = pipeline.process_frame(frame)
        # 2) Détection urgences (étouffement, respiration)
        is_emergency, reason = emergency.analyze_frame(frame)
        if is_emergency:
            print(f"[URGENCE] {reason}")
            from alert_system import AlertSystem
            AlertSystem().send_alert(level=2, reason=reason)
        time.sleep(0.2)
except KeyboardInterrupt:
    pass
finally:
    stream.release()
    print("[EMOTION] Arrêt.")
