import cv2
import numpy as np
import mediapipe as mp
import time

class EmergencyDetector:
    # --- Paramètres de détection de respiration ---
    # Nombre de frames conservées dans l'historique de mouvement
    MOTION_HISTORY_SIZE = 30
    # Seuil adaptatif : mouvement = médiane + ADAPTIVE_K * écart-type
    # Un mouvement en-dessous de ce seuil dynamique est considéré nul.
    ADAPTIVE_K = 1.5
    # Seuil plancher absolu (évite les faux positifs en cas de bruit pur)
    MIN_MOTION_THRESHOLD = 0.008
    # Ratio minimum de frames "en mouvement" dans l'historique
    # pour considérer que le patient respire.
    BREATHING_RATIO = 0.2
    # Paramètres CLAHE pour l'égalisation en basse lumière
    CLAHE_CLIP_LIMIT = 3.0
    CLAHE_TILE_SIZE = (8, 8)
    # Marge verticale sous les épaules pour la ROI thorax (fraction de la hauteur)
    CHEST_DEPTH_RATIO = 0.18
    # Marge horizontale ajoutée de chaque côté des épaules (fraction de la largeur)
    CHEST_PAD_X_RATIO = 0.03

    def __init__(self):
        # Initialisation MediaPipe pour les mains et la posture
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.7, min_tracking_confidence=0.7)
        
        # Paramètres Respiration
        self.prev_roi_gray = None
        self.motion_history = []
        self.last_check_time = time.time()
        # CLAHE créé paresseusement au premier appel de detect_breathing
        self._clahe = None

    def _get_clahe(self):
        """Crée l'objet CLAHE au premier appel (évite crash si cv2 incomplet)."""
        if self._clahe is None:
            self._clahe = cv2.createCLAHE(
                clipLimit=self.CLAHE_CLIP_LIMIT,
                tileGridSize=self.CLAHE_TILE_SIZE,
            )
        return self._clahe

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
                # Fenêtre d'observation : 6s (compromis sécurité / réactivité).
                # 10s était trop tardif d'après les tests terrain.
                if time.time() - self.last_check_time > 6:
                    emergency_detected = True
                    reason = "Absence de respiration détectée (6s sans mouvement thoracique)"
            else:
                self.last_check_time = time.time() # Reset si mouvement détecté

        return emergency_detected, reason

    def detect_breathing(self, frame, landmarks=None):
        """
        Détection de respiration robuste pour caméra Pepper en basse lumière.

        Améliorations par rapport à la version initiale :
        1. CLAHE : égalisation adaptative du contraste (résout le bruit en basse lumière).
        2. ROI élargie + padding : réduit l'impact des vêtements en intégrant
           une zone de peau (cou/épaules) dans le calcul.
        3. Seuillage adaptatif : le seuil de mouvement est calculé dynamiquement
           à partir de la médiane + K * écart-type de l'historique, au lieu d'un
           seuil arbitraire fixe.  Cela s'adapte au bruit propre de la caméra.
        4. Ratio de frames actives : au lieu de comparer la moyenne au seuil, on
           compte le pourcentage de frames « en mouvement » dans la fenêtre.
           Plus résilient aux pics de bruit isolés.
        """
        h, w, _ = frame.shape
        
        try:
            # Identification dynamique du thorax via les épaules (points 11 et 12)
            shoulder_left = landmarks[11]
            shoulder_right = landmarks[12]
            
            # --- ROI élargie : épaules → bas du thorax, avec marge latérale ---
            y1 = int(shoulder_left.y * h)
            y2 = int((shoulder_left.y + self.CHEST_DEPTH_RATIO) * h)
            pad_x = int(self.CHEST_PAD_X_RATIO * w)
            x1 = max(0, int(min(shoulder_left.x, shoulder_right.x) * w) - pad_x)
            x2 = min(w, int(max(shoulder_left.x, shoulder_right.x) * w) + pad_x)
            
            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                return True  # On ne déclare pas d'urgence si on perd la zone
            
            # --- Prétraitement basse lumière ---
            # 1. Conversion en niveaux de gris
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            # 2. CLAHE : rehausse le contraste local (compense l'obscurité)
            gray_roi = self._get_clahe().apply(gray_roi)
            # 3. Flou gaussien : supprime le bruit haute fréquence (capteur + vêtements)
            gray_roi = cv2.GaussianBlur(gray_roi, (21, 21), 0)
            
            if self.prev_roi_gray is None or self.prev_roi_gray.shape != gray_roi.shape:
                self.prev_roi_gray = gray_roi
                return True
                
            # --- Flux optique dense (Farneback) ---
            flow = cv2.calcOpticalFlowFarneback(
                self.prev_roi_gray, gray_roi, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
            )
            magnitude = np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2))
            
            # --- Historique glissant ---
            self.motion_history.append(magnitude)
            if len(self.motion_history) > self.MOTION_HISTORY_SIZE:
                self.motion_history.pop(0)
            self.prev_roi_gray = gray_roi
            
            # --- Seuillage adaptatif ---
            hist = np.array(self.motion_history)
            adaptive_threshold = max(
                np.median(hist) + self.ADAPTIVE_K * np.std(hist),
                self.MIN_MOTION_THRESHOLD,
            )
            
            # Ratio de frames « en mouvement » dans la fenêtre
            active_frames = np.sum(hist > adaptive_threshold)
            ratio = active_frames / len(hist)
            
            return ratio >= self.BREATHING_RATIO
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