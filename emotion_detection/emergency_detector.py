"""
emergency_detector.py -- Detection d'urgences medicales.

Detecte :
  - Signe d'etouffement (mains a la gorge) via MediaPipe Pose
  - Absence de respiration (pas de mouvement thoracique pendant 10s)

Quand une urgence est detectee :
  1. Alerte CRITIQUE inseree dans la BD SQLite (severity='critical')
  2. Dashboard Flask mis a jour en temps reel
  3. Infirmiers notifies immediatement via mail_service
  4. Robot Pepper alerte vocalement l'entourage (si connecte)
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import logging

logger = logging.getLogger(__name__)

# Cooldown entre deux alertes identiques (eviter le spam)
EMERGENCY_COOLDOWN = 30  # secondes


class EmergencyDetector:
    """
    Detecteur d'urgences medicales par analyse video.

    Args:
        patient_id (str): ID du patient surveille
        dashboard_url (str): URL du dashboard Flask
        pepper_session: session qi.Session() si Pepper connecte, sinon None
    """

    def __init__(self, patient_id="UNKNOWN",
                 dashboard_url="http://localhost:5000/api/alerts",
                 pepper_session=None):
        # Initialisation MediaPipe pour les mains et la posture
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )

        # Configuration
        self.patient_id = patient_id
        self.pepper_session = pepper_session

        # AlertSystem enrichi
        from alert_system import AlertSystem
        self._alert_system = AlertSystem(dashboard_url=dashboard_url)

        # TTS Pepper (optionnel)
        self._tts = None
        if pepper_session is not None:
            try:
                self._tts = pepper_session.service("ALTextToSpeech")
                self._tts.setLanguage("French")
            except Exception as e:
                logger.warning(f"TTS Pepper indisponible: {e}")

        # Parametres Respiration
        self.prev_roi_gray = None
        self.motion_history = []
        self.last_check_time = time.time()

        # Cooldown pour eviter les alertes repetees
        self._last_alert_time = {}  # reason_type -> timestamp

    def analyze_frame(self, frame):
        """
        Analyse complete : Respiration + Etouffement.

        Quand une urgence est detectee, declenche automatiquement :
          - Insertion BD (severity='critical')
          - Notification infirmiers
          - Alerte vocale Pepper

        Returns:
            tuple: (emergency_detected: bool, reason: str)
        """
        emergency_detected = False
        reason = ""

        # Conversion pour MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)

        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark

            # 1. Test Etouffement (MediaPipe)
            if self.detect_choking_sign(landmarks):
                emergency_detected = True
                reason = "Signe d'etouffement detecte (mains a la gorge)"
                self._handle_emergency(reason, "choking")
                return emergency_detected, reason

            # 2. Test Respiration Precis (Base sur les epaules detectees)
            if not self.detect_breathing(frame, landmarks):
                # Le cahier des charges impose 10s d'observation
                if time.time() - self.last_check_time > 10:
                    emergency_detected = True
                    reason = "Absence de respiration detectee (10s sans mouvement thoracique)"
                    self._handle_emergency(reason, "no_breathing")
            else:
                self.last_check_time = time.time()  # Reset si mouvement detecte

        return emergency_detected, reason

    def detect_breathing(self, frame, landmarks=None):
        """Calcule le mouvement moyen dans la zone du buste identifiee par l'IA."""
        h, w, _ = frame.shape

        try:
            # Identification dynamique du thorax via les epaules (points 11 et 12)
            shoulder_left = landmarks[11]
            shoulder_right = landmarks[12]

            # Definition de la zone de calcul (ROI) sur le haut du buste
            y1 = int(shoulder_left.y * h)
            y2 = int((shoulder_left.y + 0.15) * h)  # On descend de 15% sous les epaules
            x1 = int(min(shoulder_left.x, shoulder_right.x) * w)
            x2 = int(max(shoulder_left.x, shoulder_right.x) * w)

            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                return True  # On ne declare pas d'urgence si on perd la zone

            # Pretraitement pour la precision : Gris + Flou pour ignorer le bruit
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray_roi = cv2.GaussianBlur(gray_roi, (21, 21), 0)

            if self.prev_roi_gray is None or self.prev_roi_gray.shape != gray_roi.shape:
                self.prev_roi_gray = gray_roi
                return True

            # Calcul du flux optique entre l'image precedente et l'actuelle
            flow = cv2.calcOpticalFlowFarneback(
                self.prev_roi_gray, gray_roi, None,
                0.5, 3, 15, 3, 5, 1.2, 0
            )
            magnitude = np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2))

            self.motion_history.append(magnitude)
            if len(self.motion_history) > 30:
                self.motion_history.pop(0)
            self.prev_roi_gray = gray_roi

            # Seuil de mouvement affine : doit etre > 0.02 pour etre considere comme vivant
            return np.mean(self.motion_history) > 0.02
        except Exception:
            return True

    def detect_choking_sign(self, landmarks):
        """Verifie si une ou deux mains serrent la gorge."""
        nose = landmarks[0]
        l_shoulder = landmarks[11]
        r_shoulder = landmarks[12]
        l_wrist = landmarks[15]
        r_wrist = landmarks[16]

        neck_top = nose.y
        neck_bottom = (l_shoulder.y + r_shoulder.y) / 2
        neck_left = min(l_shoulder.x, r_shoulder.x)
        neck_right = max(l_shoulder.x, r_shoulder.x)

        # Une main est dans la zone "cou"
        choking_left = (neck_top < l_wrist.y < neck_bottom) and \
                       (neck_left < l_wrist.x < neck_right)
        choking_right = (neck_top < r_wrist.y < neck_bottom) and \
                        (neck_left < r_wrist.x < neck_right)

        return choking_left or choking_right

    # ------------------------------------------------------------------
    # GESTION D'URGENCE
    # ------------------------------------------------------------------

    def _handle_emergency(self, reason, reason_type):
        """
        Traitement complet d'une urgence detectee :
          1. Cooldown (eviter le spam)
          2. Insertion alerte CRITIQUE dans la BD
          3. Envoi au dashboard Flask
          4. Notification des infirmiers
          5. Alerte vocale sur Pepper
        """
        # Cooldown : ne pas envoyer la meme alerte trop souvent
        now = time.time()
        if now - self._last_alert_time.get(reason_type, 0) < EMERGENCY_COOLDOWN:
            return
        self._last_alert_time[reason_type] = now

        logger.critical(f"URGENCE DETECTEE: {reason} (patient {self.patient_id})")

        # 1 + 2 + 3. Alerte critique -> BD + Dashboard + Notification
        self._alert_system.send_emergency_alert(
            reason=reason,
            patient_id=self.patient_id
        )

        # 4. Alerte vocale sur Pepper
        self._emergency_voice_alert(reason)

    def _emergency_voice_alert(self, reason):
        """Fait parler Pepper pour alerter l'entourage en cas d'urgence."""
        emergency_msg = "Je vais chercher quelqu'un tout de suite."

        # Note: Allumage des LEDs rouges comme demande dans le CDC 2.10
        # est gere via le comportement specifique ou devrait etre declenche ici
        if self._tts is not None:
            try:
                self._tts.say(emergency_msg)
                logger.info("Alerte vocale Pepper diffusee")
            except Exception as e:
                logger.warning(f"Erreur TTS urgence: {e}")
        else:
            # Mode simulation PC
            print(f"  [SIM TTS URGENCE] (Allumage LEDs rouges)")
            print(f"  [SIM TTS URGENCE] {emergency_msg}")