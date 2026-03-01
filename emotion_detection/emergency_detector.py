import cv2
import numpy as np
import mediapipe as mp
import time

class EmergencyDetector:
    def __init__(self):
        # Initialisation MediaPipe pour les mains et la posture
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.7, min_tracking_confidence=0.7)
        
        # Paramètres Respiration
        self.prev_roi_gray = None
        self.motion_history = []
        self.last_check_time = time.time()

    def analyze_frame(self, frame):
        """Analyse complète : Respiration + Étouffement."""
        emergency_detected = False
        reason = ""
        
        # Conversion pour MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)
        
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # 1. Test Étouffement (MediaPipe)
            if self.detect_choking_sign(landmarks):
                emergency_detected = True
                reason = "Signe d'étouffement détecté (mains à la gorge)"
                return emergency_detected, reason

            # 2. Test Respiration Précis (Basé sur les épaules détectées)
            if not self.detect_breathing(frame, landmarks):
                # Le cahier des charges impose 10s d'observation 
                if time.time() - self.last_check_time > 10:
                    emergency_detected = True
                    reason = "Absence de respiration détectée (10s sans mouvement thoracique)" 
            else:
                self.last_check_time = time.time() # Reset si mouvement détecté

        return emergency_detected, reason

    def detect_breathing(self, frame, landmarks=None):
        """Calcule le mouvement moyen dans la zone du buste identifiée par l'IA."""
        h, w, _ = frame.shape
        
        try:
            # Identification dynamique du thorax via les épaules (points 11 et 12)
            shoulder_left = landmarks[11]
            shoulder_right = landmarks[12]
            
            # Définition de la zone de calcul (ROI) sur le haut du buste
            y1 = int(shoulder_left.y * h)
            y2 = int((shoulder_left.y + 0.15) * h) # On descend de 15% sous les épaules
            x1 = int(min(shoulder_left.x, shoulder_right.x) * w)
            x2 = int(max(shoulder_left.x, shoulder_right.x) * w)
            
            roi = frame[y1:y2, x1:x2]
            if roi.size == 0: return True # On ne déclare pas d'urgence si on perd la zone
            
            # Prétraitement pour la précision : Gris + Flou pour ignorer le bruit
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray_roi = cv2.GaussianBlur(gray_roi, (21, 21), 0)
            
            if self.prev_roi_gray is None or self.prev_roi_gray.shape != gray_roi.shape:
                self.prev_roi_gray = gray_roi
                return True
                
            # Calcul du flux optique entre l'image précédente et l'actuelle
            flow = cv2.calcOpticalFlowFarneback(self.prev_roi_gray, gray_roi, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            magnitude = np.mean(np.sqrt(flow[...,0]**2 + flow[...,1]**2))
            
            self.motion_history.append(magnitude)
            if len(self.motion_history) > 30: self.motion_history.pop(0)
            self.prev_roi_gray = gray_roi
            
            # Seuil de mouvement affiné : doit être > 0.02 pour être considéré comme vivant
            return np.mean(self.motion_history) > 0.02
        except Exception:
            return True

    def detect_choking_sign(self, landmarks):
        """Vérifie si une ou deux mains serrent la gorge[cite: 82, 189]."""
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
        choking_left = (neck_top < l_wrist.y < neck_bottom) and (neck_left < l_wrist.x < neck_right)
        choking_right = (neck_top < r_wrist.y < neck_bottom) and (neck_left < r_wrist.x < neck_right)

        return choking_left or choking_right