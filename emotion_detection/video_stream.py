import cv2
import logging

logger = logging.getLogger(__name__)


class VideoStream:
    """
    Video stream source for emotion detection.
    
    Supports two modes:
      - Local webcam (default, for PC testing): source=0
      - Pepper camera (robot deployment): source="pepper"
    
    Usage PC:
        stream = VideoStream(source=0)
    
    Usage Pepper:
        stream = VideoStream(source="pepper", pepper_session=session)
    """

    def __init__(self, source=0, pepper_session=None):
        self._mode = "local"
        self._cap = None
        self._pepper_camera = None

        if source == "pepper" and pepper_session is not None:
            # Mode Pepper: use NAOqi ALVideoDevice via PepperCamera
            try:
                from robot_control.pepper_camera import PepperCamera
                self._pepper_camera = PepperCamera(pepper_session)
                self._pepper_camera.subscribe(
                    name="MediBot_Emotion",
                    resolution=2,    # VGA 640x480
                    colorspace=13,   # BGR
                    fps=10
                )
                self._mode = "pepper"
                logger.info("VideoStream: using Pepper camera (NAOqi)")
            except Exception as e:
                logger.warning(f"Pepper camera init failed ({e}), falling back to local webcam")
                self._cap = cv2.VideoCapture(0)
                self._mode = "local"
        else:
            # Mode local: webcam PC
            self._cap = cv2.VideoCapture(source if isinstance(source, int) else 0)
            self._mode = "local"
            logger.info(f"VideoStream: using local webcam (source={source})")

    def get_frame(self):
        """Return a BGR numpy frame, or None on failure."""
        if self._mode == "pepper" and self._pepper_camera is not None:
            try:
                frame_array = self._pepper_camera.get_frame_as_array()
                return frame_array
            except Exception as e:
                logger.error(f"Pepper frame capture error: {e}")
                return None
        else:
            if self._cap is None:
                return None
            ret, frame = self._cap.read()
            if not ret:
                return None
            return frame

    def release(self):
        """Release camera resources."""
        if self._pepper_camera is not None:
            try:
                self._pepper_camera.release()
            except Exception:
                pass
        if self._cap is not None:
            self._cap.release()