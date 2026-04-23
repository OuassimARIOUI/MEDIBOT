"""
emergency_detector.py -- Detection d'urgences medicales.

Detecte :
  - Signe d'etouffement (mains a la gorge) via MediaPipe Pose
  - Absence de respiration (pas de mouvement thoracique pendant 15s)

ARCHITECTURE :
  EmergencyDetector est un detecteur PURE : il retourne (bool, str)
  sans envoyer d'alertes lui-meme. La gestion des alertes (BD, dashboard,
  notifications, TTS) est deleguee au pipeline appelant (AsyncVisionPipeline).

  Stabilisation : chaque urgence doit etre confirmee sur
  EMERGENCY_CONFIRM_THRESHOLD frames consecutives pour eviter
  les faux positifs.
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import logging

logger = logging.getLogger(__name__)

# Cooldown entre deux alertes identiques (eviter le spam)
EMERGENCY_COOLDOWN = 30  # secondes

# Nombre de frames consécutives requises avant de confirmer une urgence
# (évite les faux positifs sur un seul frame MediaPipe)
EMERGENCY_CONFIRM_THRESHOLD = 3


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

        # NOTE : Les alertes sont désormais envoyées UNIQUEMENT par le pipeline
        # (AsyncVisionPipeline._handle_emergency). EmergencyDetector se contente
        # de DÉTECTER et de RETOURNER le résultat.

        # Parametres Respiration
        self.prev_roi_gray = None
        self.motion_history = []
        self.last_check_time = time.time()

        # Stabilisation : compteurs de confirmations consécutives
        self._choking_count = 0     # frames consécutives avec signe d'étouffement
        self._no_breath_count = 0   # secondes sans mouvement thoracique

        # Cooldown pour eviter les alertes repetees
        self._last_alert_time = {}  # reason_type -> timestamp

    def analyze_frame(self, frame):
        """
        Analyse complete : Respiration + Etouffement.

        Retourne un tuple (urgence_détectée, raison) sans envoyer d'alerte.
        Les alertes sont gérées par le pipeline appelant (AsyncVisionPipeline).

        La détection utilise une stabilisation : un événement doit être
        confirmé sur EMERGENCY_CONFIRM_THRESHOLD frames consécutives
        avant d'être remonté.

        Returns:
            tuple: (emergency_detected: bool, reason: str)
        """
        emergency_detected = False
        reason = ""

        # Conversion pour MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)

        if not results.pose_landmarks:
            # Pas de pose détectée : remettre les compteurs à zéro
            # (on ne déclare PAS d'urgence si on perd la personne)
            self._choking_count = 0
            return emergency_detected, reason

        landmarks = results.pose_landmarks.landmark

        # 1. Test Etouffement (MediaPipe) avec stabilisation
        if self.detect_choking_sign(landmarks):
            self._choking_count += 1
            if self._choking_count >= EMERGENCY_CONFIRM_THRESHOLD:
                # Cooldown anti-spam
                now = time.time()
                if now - self._last_alert_time.get("choking", 0) >= EMERGENCY_COOLDOWN:
                    emergency_detected = True
                    reason = "Signe d'etouffement detecte (mains a la gorge)"
                    self._last_alert_time["choking"] = now
                    logger.critical(f"URGENCE CONFIRMEE: {reason} (patient {self.patient_id})")
                    return emergency_detected, reason
        else:
            self._choking_count = 0

        # 2. Test Respiration Precis (Base sur les epaules detectees)
        if not self.detect_breathing(frame, landmarks):
            # Observation prolongée : 15s sans mouvement thoracique
            if time.time() - self.last_check_time > 15:
                now = time.time()
                if now - self._last_alert_time.get("no_breathing", 0) >= EMERGENCY_COOLDOWN:
                    emergency_detected = True
                    reason = "Absence de respiration detectee (15s sans mouvement thoracique)"
                    self._last_alert_time["no_breathing"] = now
                    logger.critical(f"URGENCE CONFIRMEE: {reason} (patient {self.patient_id})")
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
    # NOTE : La gestion des alertes (BD, dashboard, notifications, TTS)
    # est ENTIÈREMENT déléguée au pipeline appelant (AsyncVisionPipeline).
    # EmergencyDetector se limite à la DÉTECTION pure.
    # Les anciens _handle_emergency / _emergency_voice_alert ont été
    # retirés pour éviter les alertes en double.