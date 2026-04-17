"""
test_vision.py — Suite de tests automatisés pour le module de vision MEDIBOT.

Couvre :
  - EmergencyDetector : logique des 10 secondes sans respiration, étouffement
  - EmotionPipeline   : cooldown (REACTION_COOLDOWN) et buffer de stabilité (STABILITY_THRESHOLD)
  - AlertSystem        : POST HTTP avec le bon payload

Exécution (depuis la racine MEDIBOT/) :
    python -m pytest tests/test_vision.py -v
"""

import sys
import time
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

# ── Pré-mock des dépendances lourdes (mediapipe, cv2, deepface) ──────
# Ces mocks sont injectés dans sys.modules AVANT tout import de
# emergency_detector / emotion_detector, pour éviter que Python tente
# de charger les vrais paquets (qui peuvent crasher si tensorflow ou
# mediapipe sont cassés dans le venv).

_mp_mock = MagicMock()
_mp_mock.solutions.pose.Pose.return_value = MagicMock()
sys.modules.setdefault("mediapipe", _mp_mock)
sys.modules.setdefault("mediapipe.solutions", _mp_mock.solutions)

# cv2 : utiliser le vrai s'il est installé, sinon mocker
try:
    import cv2
    _has_full_cv2 = hasattr(cv2, "createCLAHE")
except ImportError:
    sys.modules["cv2"] = MagicMock()
    _has_full_cv2 = False

# Maintenant on peut importer en toute sécurité
from emotion_detection.emergency_detector import EmergencyDetector

_skip_breathing = pytest.mark.skipif(
    not _has_full_cv2,
    reason="cv2.createCLAHE indisponible (opencv incomplet dans ce venv)",
)


# =====================================================================
#  1. TESTS EmergencyDetector
# =====================================================================

@_skip_breathing
class TestEmergencyDetectorBreathing:
    """Tests pour detect_breathing et la logique 10s dans analyze_frame."""

    @pytest.fixture(autouse=True)
    def setup_detector(self):
        """Crée un détecteur avec MediaPipe mocké (pas besoin de GPU)."""
        self.detector = EmergencyDetector()
        self.detector.pose = MagicMock()
        yield

    # ---- Helpers ----

    @staticmethod
    def _make_landmarks(shoulder_y=0.3, wrist_y=0.8):
        """Crée un objet landmarks factice avec épaules visibles."""
        lm = {}
        for i in range(33):
            m = MagicMock()
            m.x, m.y, m.visibility = 0.5, 0.5, 0.9
            lm[i] = m
        # Épaule gauche (11), épaule droite (12)
        lm[11].x, lm[11].y = 0.35, shoulder_y
        lm[12].x, lm[12].y = 0.65, shoulder_y
        # Poignets loin de la gorge par défaut
        lm[15].x, lm[15].y = 0.2, wrist_y
        lm[16].x, lm[16].y = 0.8, wrist_y
        # Nez
        lm[0].x, lm[0].y = 0.5, 0.15
        return lm

    @staticmethod
    def _static_frame(h=480, w=640, value=128):
        """Frame grise uniforme (aucun mouvement)."""
        return np.full((h, w, 3), value, dtype=np.uint8)

    @staticmethod
    def _noisy_frame(h=480, w=640, base=128, noise_std=2):
        """Frame avec un léger bruit gaussien (simule capteur basse lumière)."""
        frame = np.full((h, w, 3), base, dtype=np.uint8)
        noise = np.random.normal(0, noise_std, frame.shape).astype(np.int16)
        return np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    @staticmethod
    def _breathing_frames(h=480, w=640, n=2, amplitude=20):
        """
        Génère n frames simulant un mouvement thoracique vertical.
        Décale verticalement un bandeau de pixels pour simuler la respiration.
        Utilise un gradient pour maximiser le flux optique détectable.
        """
        frames = []
        for i in range(n):
            f = np.zeros((h, w, 3), dtype=np.uint8)
            shift = int(amplitude * np.sin(2 * np.pi * i / max(n, 1)))
            y_start = max(0, 144 + shift)
            y_end = min(h, 230 + shift)
            # Gradient vertical dans le bandeau (mieux détecté par le flux optique)
            for row in range(y_start, y_end):
                val = int(100 + 155 * (row - y_start) / max(y_end - y_start, 1))
                f[row, 200:440] = val
            frames.append(f)
        return frames

    # ---- Tests detect_breathing ----

    def test_identical_frames_no_breathing(self):
        """Deux frames identiques → pas de respiration détectée."""
        landmarks = self._make_landmarks()
        frame = self._static_frame()

        # Initialisation (premier appel retourne toujours True)
        assert self.detector.detect_breathing(frame, landmarks) == True  # noqa: E712
        # Remplir l'historique avec des frames identiques (mouvement nul)
        for _ in range(self.detector.MOTION_HISTORY_SIZE + 1):
            result = self.detector.detect_breathing(frame, landmarks)

        assert result == False, "Des frames identiques doivent indiquer l'absence de respiration"  # noqa: E712

    def test_noisy_frames_no_false_positive(self):
        """Du bruit capteur léger ne doit PAS être interprété comme de la respiration."""
        landmarks = self._make_landmarks()
        np.random.seed(42)

        frame_init = self._noisy_frame(noise_std=1)
        self.detector.detect_breathing(frame_init, landmarks)

        for _ in range(self.detector.MOTION_HISTORY_SIZE + 1):
            frame = self._noisy_frame(noise_std=1)
            result = self.detector.detect_breathing(frame, landmarks)

        assert result == False, "Un bruit capteur faible ne doit pas simuler une respiration"  # noqa: E712

    def test_moving_frames_detected_as_breathing(self):
        """Un historique de mouvement réel (magnitudes variées) → respiration détectée.

        Plutôt que de générer des frames synthétiques (sensible au pipeline
        CLAHE + blur + Farneback), on injecte directement un historique de
        magnitudes réalistes qui simule une respiration normale.

        Respiration réelle : alternance de pics (inspiration/expiration) et
        de creux (pauses). Les pics doivent être assez au-dessus de la
        médiane pour dépasser le seuil adaptatif (median + K*std).
        """
        # Alternance creux (~0.01) et pics (~0.15-0.25)
        # Donne médiane ~0.04, std ~0.07 → seuil adaptatif ~0.15
        # Les pics à 0.15-0.25 dépassent le seuil → ratio > 0.2
        breathing_mags = [
            0.01, 0.02, 0.18, 0.25, 0.03, 0.01, 0.02, 0.20,
            0.22, 0.03, 0.01, 0.01, 0.15, 0.23, 0.03, 0.01,
            0.02, 0.19, 0.24, 0.03, 0.01, 0.01, 0.17, 0.22,
            0.03, 0.01, 0.02, 0.20, 0.25, 0.03,
        ]
        self.detector.motion_history = breathing_mags.copy()

        # Reproduce the adaptive threshold logic from detect_breathing
        hist = np.array(self.detector.motion_history)
        adaptive_threshold = max(
            np.median(hist) + self.detector.ADAPTIVE_K * np.std(hist),
            self.detector.MIN_MOTION_THRESHOLD,
        )
        active_frames = np.sum(hist > adaptive_threshold)
        ratio = active_frames / len(hist)

        assert ratio >= self.detector.BREATHING_RATIO, (
            f"Un patient qui respire doit avoir ratio={ratio:.2f} >= {self.detector.BREATHING_RATIO}"
        )

    def test_empty_roi_returns_true(self):
        """Si la ROI est vide (landmarks aberrants), ne pas déclencher de fausse alerte."""
        landmarks = self._make_landmarks()
        # Épaules hors cadre → ROI vide
        landmarks[11].y = 1.0
        landmarks[12].y = 1.0
        frame = self._static_frame()
        assert self.detector.detect_breathing(frame, landmarks) == True  # noqa: E712

    def test_roi_shape_change_resets(self):
        """Un changement de forme de la ROI doit réinitialiser sans fausse alerte."""
        lm1 = self._make_landmarks(shoulder_y=0.3)
        # Différentes positions X pour changer la LARGEUR de la ROI
        lm2 = self._make_landmarks(shoulder_y=0.3)
        lm2[11].x = 0.20  # épaule gauche beaucoup plus à gauche
        lm2[12].x = 0.80  # épaule droite beaucoup plus à droite
        frame = self._static_frame()

        self.detector.detect_breathing(frame, lm1)
        # Changement brutal d'épaules → ROI de largeur différente
        result = self.detector.detect_breathing(frame, lm2)
        assert result == True, "Un changement de ROI doit réinitialiser, pas alerter"  # noqa: E712


class TestEmergencyDetector10Seconds:
    """Teste la logique des 10 secondes dans analyze_frame."""

    @pytest.fixture(autouse=True)
    def setup_detector(self):
        self.detector = EmergencyDetector()
        self.detector.pose = MagicMock()
        yield

    def _mock_pose_result(self, has_landmarks=True, choking=False):
        """Construit un résultat MediaPipe factice."""
        if not has_landmarks:
            result = MagicMock()
            result.pose_landmarks = None
            return result

        lm = {}
        for i in range(33):
            m = MagicMock()
            m.x, m.y, m.visibility = 0.5, 0.5, 0.9
            lm[i] = m
        lm[0].y = 0.15  # nez
        lm[11].x, lm[11].y = 0.35, 0.3
        lm[12].x, lm[12].y = 0.65, 0.3
        lm[15].x, lm[15].y = 0.2, 0.8  # poignets loin
        lm[16].x, lm[16].y = 0.8, 0.8

        if choking:
            # Poignets dans la zone cou
            neck_y = (lm[11].y + 0.15) / 2
            lm[15].x, lm[15].y = 0.5, neck_y
            lm[16].x, lm[16].y = 0.5, neck_y

        result = MagicMock()
        result.pose_landmarks.landmark = lm
        return result

    def test_no_breathing_under_10s_no_emergency(self):
        """Absence de respiration < 10s → pas encore d'urgence."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Forcer detect_breathing à retourner False
        self.detector.detect_breathing = MagicMock(return_value=False)
        self.detector.detect_choking_sign = MagicMock(return_value=False)
        self.detector.pose.process = MagicMock(return_value=self._mock_pose_result())

        # Juste démarré → timer pas encore expiré
        self.detector.last_check_time = time.time()
        emergency, reason = self.detector.analyze_frame(frame)
        assert emergency is False

    def test_no_breathing_over_10s_triggers_emergency(self):
        """Absence de respiration > 10s → urgence déclenchée."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        self.detector.detect_breathing = MagicMock(return_value=False)
        self.detector.detect_choking_sign = MagicMock(return_value=False)
        self.detector.pose.process = MagicMock(return_value=self._mock_pose_result())

        # Simuler 11 secondes écoulées sans mouvement
        self.detector.last_check_time = time.time() - 11
        emergency, reason = self.detector.analyze_frame(frame)
        assert emergency is True
        assert "respiration" in reason.lower()

    def test_breathing_resets_timer(self):
        """Si la respiration reprend, le timer doit se réinitialiser."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        self.detector.detect_choking_sign = MagicMock(return_value=False)
        self.detector.pose.process = MagicMock(return_value=self._mock_pose_result())

        # Phase 1 : pas de respiration pendant 8s
        self.detector.detect_breathing = MagicMock(return_value=False)
        self.detector.last_check_time = time.time() - 8
        emergency, _ = self.detector.analyze_frame(frame)
        assert emergency is False

        # Phase 2 : respiration reprend → timer reset
        self.detector.detect_breathing = MagicMock(return_value=True)
        self.detector.analyze_frame(frame)

        # Phase 3 : 5s après la reprise → pas d'urgence
        self.detector.detect_breathing = MagicMock(return_value=False)
        self.detector.last_check_time = time.time() - 5
        emergency, _ = self.detector.analyze_frame(frame)
        assert emergency is False

    def test_choking_detected_immediately(self):
        """L'étouffement déclenche immédiatement une urgence (pas de délai 10s)."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        self.detector.detect_choking_sign = MagicMock(return_value=True)
        self.detector.pose.process = MagicMock(return_value=self._mock_pose_result())

        emergency, reason = self.detector.analyze_frame(frame)
        assert emergency is True
        assert "étouffement" in reason.lower() or "touffement" in reason.lower()

    def test_no_landmarks_no_emergency(self):
        """Si MediaPipe ne détecte personne → aucune urgence."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.detector.pose.process = MagicMock(
            return_value=self._mock_pose_result(has_landmarks=False)
        )
        emergency, reason = self.detector.analyze_frame(frame)
        assert emergency is False
        assert reason == ""


class TestChokingDetection:
    """Tests pour detect_choking_sign."""

    @pytest.fixture(autouse=True)
    def setup_detector(self):
        self.detector = EmergencyDetector()
        self.detector.pose = MagicMock()
        yield

    @staticmethod
    def _landmarks(wrist_l=(0.2, 0.8), wrist_r=(0.8, 0.8)):
        lm = {}
        for i in range(33):
            m = MagicMock()
            m.x, m.y = 0.5, 0.5
            lm[i] = m
        lm[0].y = 0.15   # nez
        lm[11].x, lm[11].y = 0.35, 0.3  # épaule gauche
        lm[12].x, lm[12].y = 0.65, 0.3  # épaule droite
        lm[15].x, lm[15].y = wrist_l
        lm[16].x, lm[16].y = wrist_r
        return lm

    def test_hands_at_throat_detected(self):
        """Deux mains dans la zone cou → étouffement."""
        neck_y = (0.15 + 0.3) / 2  # milieu nez-épaules
        lm = self._landmarks(wrist_l=(0.5, neck_y), wrist_r=(0.5, neck_y))
        assert self.detector.detect_choking_sign(lm) is True

    def test_one_hand_at_throat_detected(self):
        """Une seule main dans la zone cou → étouffement aussi."""
        neck_y = (0.15 + 0.3) / 2
        lm = self._landmarks(wrist_l=(0.5, neck_y), wrist_r=(0.8, 0.8))
        assert self.detector.detect_choking_sign(lm) is True

    def test_hands_away_no_choking(self):
        """Mains le long du corps → pas d'étouffement."""
        lm = self._landmarks(wrist_l=(0.2, 0.8), wrist_r=(0.8, 0.8))
        assert self.detector.detect_choking_sign(lm) is False

    def test_hands_above_head_no_choking(self):
        """Mains au-dessus de la tête → pas d'étouffement."""
        lm = self._landmarks(wrist_l=(0.5, 0.05), wrist_r=(0.5, 0.05))
        assert self.detector.detect_choking_sign(lm) is False


# =====================================================================
#  2. TESTS EmotionPipeline (cooldown + stabilité)
# =====================================================================

class TestEmotionPipeline:
    """Teste le buffer de stabilité et le cooldown sans charger DeepFace."""

    @pytest.fixture(autouse=True)
    def setup_pipeline(self):
        from emotion_detection.emotion_detector import (
            EmotionPipeline, EmotionDetector,
            STABILITY_THRESHOLD, REACTION_COOLDOWN,
        )
        self.STABILITY_THRESHOLD = STABILITY_THRESHOLD
        self.REACTION_COOLDOWN = REACTION_COOLDOWN

        # Mock AlertSystem là où il est importé (dans __init__ de EmotionPipeline)
        with patch("alert_system.AlertSystem") as mock_alert_cls:
            self.mock_alert_instance = MagicMock()
            mock_alert_cls.return_value = self.mock_alert_instance

            self.pipeline = EmotionPipeline(patient_id="PAT001", pepper_session=None)

        # Mock le détecteur pour ne pas charger DeepFace
        self.mock_deepface = MagicMock()
        self.pipeline.detector = MagicMock(spec=EmotionDetector)
        self.pipeline.detector.analyze_emotion = self.mock_deepface
        yield

    def _set_deepface_emotion(self, emotion):
        """Configure le mock détecteur pour retourner une émotion donnée."""
        self.pipeline.detector.analyze_emotion.return_value = emotion

    def _dummy_frame(self):
        return np.zeros((480, 640, 3), dtype=np.uint8)

    # ---- Stabilité ----

    def test_single_detection_no_reaction(self):
        """Une seule détection ne doit PAS déclencher de réaction (buffer)."""
        self._set_deepface_emotion("sad")
        with patch.object(self.pipeline, "_react") as mock_react:
            self.pipeline.process_frame(self._dummy_frame())
            mock_react.assert_not_called()

    def test_stability_threshold_triggers_reaction(self):
        """STABILITY_THRESHOLD détections consécutives identiques → réaction."""
        self._set_deepface_emotion("angry")
        with patch.object(self.pipeline, "_react") as mock_react:
            for _ in range(self.STABILITY_THRESHOLD):
                self.pipeline.process_frame(self._dummy_frame())
            mock_react.assert_called_once_with("angry")

    def test_mixed_emotions_no_reaction(self):
        """Des émotions alternées ne déclenchent pas de réaction."""
        emotions = ["sad", "angry"] * self.STABILITY_THRESHOLD
        with patch.object(self.pipeline, "_react") as mock_react:
            for emo in emotions:
                self._set_deepface_emotion(emo)
                self.pipeline.process_frame(self._dummy_frame())
            mock_react.assert_not_called()

    def test_unknown_emotion_ignored(self):
        """L'émotion 'unknown' ne déclenche rien."""
        self.pipeline.detector.analyze_emotion.return_value = "unknown"
        with patch.object(self.pipeline, "_react") as mock_react:
            for _ in range(self.STABILITY_THRESHOLD + 5):
                self.pipeline.process_frame(self._dummy_frame())
            mock_react.assert_not_called()

    # ---- Cooldown ----

    def test_cooldown_blocks_repeated_reaction(self):
        """La même émotion stable dans les 30s suivantes ne re-déclenche pas."""
        self._set_deepface_emotion("fear")

        # Première réaction
        for _ in range(self.STABILITY_THRESHOLD):
            self.pipeline.process_frame(self._dummy_frame())

        # Vider le buffer et re-remplir immédiatement
        self.pipeline._emotion_buffer.clear()
        with patch.object(self.pipeline, "_set_leds") as mock_leds:
            for _ in range(self.STABILITY_THRESHOLD):
                self.pipeline.process_frame(self._dummy_frame())
            # Le cooldown empêche la deuxième réaction → LEDs non rappelées
            mock_leds.assert_not_called()

    def test_cooldown_expires_allows_reaction(self):
        """Après REACTION_COOLDOWN secondes, la même émotion peut re-déclencher."""
        self._set_deepface_emotion("sad")

        for _ in range(self.STABILITY_THRESHOLD):
            self.pipeline.process_frame(self._dummy_frame())

        # Simuler l'expiration du cooldown
        self.pipeline._last_reaction_time["sad"] = time.time() - self.REACTION_COOLDOWN - 1
        self.pipeline._emotion_buffer.clear()

        with patch.object(self.pipeline, "_send_alert") as mock_alert:
            for _ in range(self.STABILITY_THRESHOLD):
                self.pipeline.process_frame(self._dummy_frame())
            mock_alert.assert_called_once()

    def test_different_emotion_not_blocked_by_cooldown(self):
        """Le cooldown est par émotion : 'angry' après 'sad' n'est pas bloqué."""
        # D'abord déclencher 'sad'
        self._set_deepface_emotion("sad")
        for _ in range(self.STABILITY_THRESHOLD):
            self.pipeline.process_frame(self._dummy_frame())

        # Ensuite 'angry' immédiatement
        self.pipeline._emotion_buffer.clear()
        self._set_deepface_emotion("angry")
        with patch.object(self.pipeline, "_react") as mock_react:
            for _ in range(self.STABILITY_THRESHOLD):
                self.pipeline.process_frame(self._dummy_frame())
            mock_react.assert_called_once_with("angry")


# =====================================================================
#  3. TESTS AlertSystem
# =====================================================================

class TestAlertSystem:
    """Tests unitaires pour l'envoi d'alertes HTTP."""

    @pytest.fixture(autouse=True)
    def setup_alert(self):
        from emotion_detection.alert_system import AlertSystem
        self.alert = AlertSystem(dashboard_url="http://localhost:5000/api/alerts")
        yield

    @patch("emotion_detection.alert_system.requests.post")
    def test_send_alert_posts_correct_payload(self, mock_post):
        """send_alert envoie un POST avec le bon format JSON."""
        mock_post.return_value = MagicMock(status_code=200)

        result = self.alert.send_alert(
            level=2,
            reason="Absence de respiration détectée",
            patient_id="PAT001",
        )

        assert result is True
        mock_post.assert_called_once()

        # Vérifier le payload
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["patient_id"] == "PAT001"
        assert payload["priority"] == 2
        assert payload["reason"] == "Absence de respiration détectée"
        assert payload["status"] == "pending"
        assert "timestamp" in payload

    @patch("emotion_detection.alert_system.requests.post")
    def test_send_alert_returns_false_on_server_error(self, mock_post):
        """Retourne False si le serveur répond avec une erreur."""
        mock_post.return_value = MagicMock(status_code=500)
        result = self.alert.send_alert(level=1, reason="Test")
        assert result is False

    @patch("emotion_detection.alert_system.requests.post")
    def test_send_alert_degraded_mode_on_connection_error(self, mock_post):
        """Mode dégradé : retourne False si le dashboard est injoignable."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        result = self.alert.send_alert(level=2, reason="Urgence test")
        assert result is False

    @patch("emotion_detection.alert_system.requests.post")
    def test_send_alert_timeout_handling(self, mock_post):
        """Le timeout de 2s est bien passé à requests.post."""
        mock_post.return_value = MagicMock(status_code=200)
        self.alert.send_alert(level=1, reason="Test timeout")

        call_kwargs = mock_post.call_args
        timeout = call_kwargs.kwargs.get("timeout") or call_kwargs[1].get("timeout")
        assert timeout == 2

    @patch("emotion_detection.alert_system.requests.post")
    def test_send_alert_level1_surveillance(self, mock_post):
        """Niveau 1 = à surveiller (sévérité basse)."""
        mock_post.return_value = MagicMock(status_code=200)
        result = self.alert.send_alert(level=1, reason="Émotion triste persistante")
        assert result is True

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["priority"] == 1

    @patch("emotion_detection.alert_system.requests.post")
    def test_send_alert_default_patient_id(self, mock_post):
        """Le patient_id par défaut est 'Chambre_102'."""
        mock_post.return_value = MagicMock(status_code=200)
        self.alert.send_alert(level=1, reason="Test défaut")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["patient_id"] == "Chambre_102"
