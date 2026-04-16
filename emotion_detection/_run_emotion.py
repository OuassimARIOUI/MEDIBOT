"""
_run_emotion.py -- Lanceur autonome de la detection d'emotions + urgences.

Utilise par run.py pour lancer la detection en sous-processus.
Integre EmotionPipeline + EmergencyDetector avec :
  - Enregistrement emotions en BD (emotion_logs)
  - Alertes critiques pour urgences (BD + Dashboard + Infirmiers)
"""

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
PATIENT_ID = os.getenv("PATIENT_ID", "PAT001")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:5000/api/alerts")

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

# EmotionPipeline gere : emotions -> BD + alertes + LEDs + TTS
pipeline = EmotionPipeline(
    patient_id=PATIENT_ID,
    pepper_session=pep_session,
    alert_url=DASHBOARD_URL
)

# EmergencyDetector gere : urgences -> BD + Dashboard + Infirmiers + TTS
emergency = EmergencyDetector(
    patient_id=PATIENT_ID,
    dashboard_url=DASHBOARD_URL,
    pepper_session=pep_session
)

video_src = "pepper" if pep_session else 0
stream = VideoStream(source=video_src, pepper_session=pep_session)
print(f"[EMOTION] Demarrage (source={video_src})...")
print(f"[EMOTION] Patient: {PATIENT_ID} | Dashboard: {DASHBOARD_URL}")

try:
    while True:
        frame = stream.get_frame()
        if frame is None:
            time.sleep(0.2)
            continue
        # 1) Detection emotions -> BD + alertes automatiques
        emotion = pipeline.process_frame(frame)
        # 2) Detection urgences -> BD + Dashboard + Infirmiers (automatique)
        is_emergency, reason = emergency.analyze_frame(frame)
        if is_emergency:
            print(f"[URGENCE] {reason}")
            # Note: EmergencyDetector.analyze_frame() gere deja tout
            # (BD + dashboard + notification + TTS) via _handle_emergency()
        time.sleep(0.2)
except KeyboardInterrupt:
    pass
finally:
    stream.release()
    print("[EMOTION] Arret.")
