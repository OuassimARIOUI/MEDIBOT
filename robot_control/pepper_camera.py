"""
pepper_camera.py - Camera access for Pepper robot.

This module provides camera frame capture from Pepper's cameras.
It handles video subscription and raw image retrieval (no processing).

Author: MediBot Team
"""

import logging
from typing import Optional, Tuple, Dict, Any
import struct

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PepperCamera:
    """
    Camera controller for accessing Pepper's video streams.
    
    This class provides raw image access from Pepper's cameras.
    Image processing (like emotion detection) should be done elsewhere.
    
    Attributes:
        session: NAOqi session connected to Pepper
        video_service: ALVideoDevice proxy for camera access
    
    Camera IDs:
        - 0: Top camera (forehead)
        - 1: Bottom camera (mouth level)
        - 2: Depth camera (if available)
    
    Resolutions:
        - 0: 160x120 (QQVGA)
        - 1: 320x240 (QVGA)
        - 2: 640x480 (VGA)
        - 3: 1280x960 (4VGA)
    
    Color Spaces:
        - 0: Yuv
        - 9: YUV422
        - 11: RGB
        - 13: BGR
    """
    
    # Camera configuration constants
    CAMERA_TOP = 0
    CAMERA_BOTTOM = 1
    CAMERA_DEPTH = 2
    
    RESOLUTION_QQVGA = 0  # 160x120
    RESOLUTION_QVGA = 1   # 320x240
    RESOLUTION_VGA = 2    # 640x480
    RESOLUTION_4VGA = 3   # 1280x960
    
    COLORSPACE_YUV = 0
    COLORSPACE_YUV422 = 9
    COLORSPACE_RGB = 11
    COLORSPACE_BGR = 13
    
    # Resolution dimensions lookup
    RESOLUTION_DIMENSIONS = {
        0: (160, 120),
        1: (320, 240),
        2: (640, 480),
        3: (1280, 960),
    }
    
    def __init__(self, session):
        """
        Initialize the camera controller.
        
        Args:
            session: Active NAOqi session connected to Pepper robot
        
        Raises:
            RuntimeError: If ALVideoDevice service cannot be accessed
        """
        self.session = session
        self.video_service = None
        self._subscriber_id = None
        
        # Default camera settings
        self._camera_id = self.CAMERA_TOP
        self._resolution = self.RESOLUTION_VGA
        self._colorspace = self.COLORSPACE_BGR
        self._fps = 10
        
        try:
            self.video_service = self.session.service("ALVideoDevice")
            logger.info("ALVideoDevice service connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to ALVideoDevice: {e}")
            raise RuntimeError(f"Cannot initialize camera service: {e}")
    
    def subscribe(self, name: str = "MediBot_Camera", 
                  camera_id: int = None,
                  resolution: int = None,
                  colorspace: int = None,
                  fps: int = None) -> bool:
        """
        Subscribe to camera video stream.
        
        Must be called before getting frames. Creates a video subscription
        with the specified parameters.
        
        Args:
            name: Unique subscriber name
            camera_id: Camera to use (0=top, 1=bottom)
            resolution: Image resolution (0-3)
            colorspace: Color format (11=RGB, 13=BGR)
            fps: Frames per second (1-30)
        
        Returns:
            bool: True if subscription successful, False otherwise
        
        Example:
            >>> camera = PepperCamera(session)
            >>> camera.subscribe("MyApp")
            True
            >>> frame = camera.get_frame()
        """
        if not self.video_service:
            logger.error("Video service not available")
            return False
        
        # Use provided values or defaults
        camera_id = camera_id if camera_id is not None else self._camera_id
        resolution = resolution if resolution is not None else self._resolution
        colorspace = colorspace if colorspace is not None else self._colorspace
        fps = fps if fps is not None else self._fps
        
        try:
            # Unsubscribe if already subscribed
            if self._subscriber_id:
                self.unsubscribe()
            
            # Create new subscription
            self._subscriber_id = self.video_service.subscribeCamera(
                name,
                camera_id,
                resolution,
                colorspace,
                fps
            )
            
            # Store current settings
            self._camera_id = camera_id
            self._resolution = resolution
            self._colorspace = colorspace
            self._fps = fps
            
            logger.info(f"Camera subscribed: {self._subscriber_id}")
            logger.info(f"Settings: camera={camera_id}, resolution={resolution}, "
                       f"colorspace={colorspace}, fps={fps}")
            
            return True
            
        except Exception as e:
            logger.error(f"Camera subscription error: {e}")
            return False
    
    def unsubscribe(self) -> bool:
        """
        Unsubscribe from camera video stream.
        
        Should be called when camera is no longer needed to free resources.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.video_service or not self._subscriber_id:
            return False
        
        try:
            self.video_service.unsubscribe(self._subscriber_id)
            logger.info(f"Camera unsubscribed: {self._subscriber_id}")
            self._subscriber_id = None
            return True
            
        except Exception as e:
            logger.error(f"Camera unsubscribe error: {e}")
            return False
    
    def get_frame(self) -> Optional[Dict[str, Any]]:
        """
        Get a single frame from the camera.
        
        Returns raw image data without any processing.
        The image can be used by other modules (e.g., emotion detection).
        
        Returns:
            dict: Frame data containing:
                - width: Image width in pixels
                - height: Image height in pixels
                - channels: Number of color channels
                - data: Raw image bytes
                - timestamp: Capture timestamp
            None: If capture failed
        
        Example:
            >>> camera = PepperCamera(session)
            >>> camera.subscribe()
            >>> frame = camera.get_frame()
            >>> if frame:
            ...     print(f"Got {frame['width']}x{frame['height']} image")
        """
        if not self.video_service:
            logger.error("Video service not available")
            return None
        
        if not self._subscriber_id:
            logger.warning("Not subscribed to camera. Call subscribe() first.")
            # Auto-subscribe with defaults
            if not self.subscribe():
                return None
        
        try:
            # Get image from camera
            # Returns: [width, height, layers, colorspace, timestamp, 
            #           camera_id, left_angle, top_angle, right_angle, 
            #           bottom_angle, data_bytes]
            image_data = self.video_service.getImageRemote(self._subscriber_id)
            
            if image_data is None:
                logger.warning("No image data received")
                return None
            
            # Extract image information
            width = image_data[0]
            height = image_data[1]
            channels = image_data[2]
            colorspace = image_data[3]
            timestamp_s = image_data[4]
            timestamp_us = image_data[5]
            raw_data = image_data[6]
            
            # Calculate timestamp in seconds
            timestamp = timestamp_s + timestamp_us / 1000000.0
            
            frame = {
                "width": width,
                "height": height,
                "channels": channels,
                "colorspace": colorspace,
                "timestamp": timestamp,
                "data": raw_data,
            }
            
            logger.debug(f"Frame captured: {width}x{height}, {channels} channels")
            
            return frame
            
        except Exception as e:
            logger.error(f"Get frame error: {e}")
            return None
    
    def get_frame_as_array(self) -> Optional[Any]:
        """
        Get a frame as a numpy array (if numpy is available).
        
        Convenience method that converts raw bytes to numpy array.
        Requires numpy to be installed.
        
        Returns:
            numpy.ndarray: Image as numpy array (height, width, channels)
            None: If capture failed or numpy not available
        """
        try:
            import numpy as np
        except ImportError:
            logger.error("numpy is required for get_frame_as_array()")
            return None
        
        frame = self.get_frame()
        if frame is None:
            return None
        
        try:
            # Convert raw bytes to numpy array
            image_array = np.frombuffer(frame["data"], dtype=np.uint8)
            
            # Reshape based on dimensions
            if frame["channels"] == 3:
                image_array = image_array.reshape(
                    (frame["height"], frame["width"], 3)
                )
            else:
                image_array = image_array.reshape(
                    (frame["height"], frame["width"])
                )
            
            return image_array
            
        except Exception as e:
            logger.error(f"Array conversion error: {e}")
            return None
    
    def get_resolution(self) -> Tuple[int, int]:
        """
        Get current camera resolution.
        
        Returns:
            tuple: (width, height) in pixels
        """
        return self.RESOLUTION_DIMENSIONS.get(self._resolution, (640, 480))
    
    def set_camera(self, camera_id: int) -> bool:
        """
        Switch to a different camera.
        
        Args:
            camera_id: Camera to switch to (0=top, 1=bottom)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if camera_id not in [self.CAMERA_TOP, self.CAMERA_BOTTOM, self.CAMERA_DEPTH]:
            logger.warning(f"Invalid camera ID: {camera_id}")
            return False
        
        logger.info(f"Switching to camera {camera_id}")
        
        # Re-subscribe with new camera
        return self.subscribe(
            camera_id=camera_id,
            resolution=self._resolution,
            colorspace=self._colorspace,
            fps=self._fps
        )
    
    def set_resolution(self, resolution: int) -> bool:
        """
        Change camera resolution.
        
        Args:
            resolution: Resolution ID (0=QQVGA, 1=QVGA, 2=VGA, 3=4VGA)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if resolution not in self.RESOLUTION_DIMENSIONS:
            logger.warning(f"Invalid resolution: {resolution}")
            return False
        
        dims = self.RESOLUTION_DIMENSIONS[resolution]
        logger.info(f"Setting resolution to {dims[0]}x{dims[1]}")
        
        # Re-subscribe with new resolution
        return self.subscribe(
            camera_id=self._camera_id,
            resolution=resolution,
            colorspace=self._colorspace,
            fps=self._fps
        )
    
    def is_subscribed(self) -> bool:
        """
        Check if currently subscribed to camera.
        
        Returns:
            bool: True if subscribed, False otherwise
        """
        return self._subscriber_id is not None
    
    def release(self) -> None:
        """
        Release camera resources.
        
        Call this when done using the camera.
        """
        self.unsubscribe()
        logger.info("Camera resources released")
    
    def __enter__(self):
        """Context manager entry - auto subscribe."""
        self.subscribe()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - auto unsubscribe."""
        self.release()
        return False


# Convenience function for simple usage
def get_frame(session=None) -> Optional[Dict[str, Any]]:
    """
    Simple function to capture a single frame from Pepper's camera.
    
    Args:
        session: NAOqi session
    
    Returns:
        dict: Frame data or None if failed
    """
    if session is None:
        logger.error("No session provided. Cannot access camera without connection to Pepper.")
        return None
    
    try:
        camera = PepperCamera(session)
        camera.subscribe()
        frame = camera.get_frame()
        camera.unsubscribe()
        return frame
    except Exception as e:
        logger.error(f"get_frame() failed: {e}")
        return None
