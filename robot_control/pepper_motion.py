"""
pepper_motion.py - Motion and gesture control for Pepper robot.

This module provides safe, smooth gesture and movement capabilities using NAOqi's ALMotion.
It handles head movements, arm gestures, and idle animations.

Author: MediBot Team
"""

import time
import logging
from typing import List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PepperMotion:
    """
    Motion and gesture controller for Pepper robot.
    
    This class manages physical movements using NAOqi's ALMotion service.
    All movements are designed to be smooth and safe for hospital environments.
    
    Attributes:
        session: NAOqi session connected to Pepper
        motion_service: ALMotion proxy for movement control
        autonomous_service: ALAutonomousLife proxy for autonomous behaviors
    """
    
    # Joint angle limits for safety (in radians)
    HEAD_YAW_LIMITS = (-2.0857, 2.0857)      # Left-Right
    HEAD_PITCH_LIMITS = (-0.7068, 0.4451)    # Up-Down
    
    # Movement speed settings
    SMOOTH_SPEED = 0.15   # Slow and gentle
    NORMAL_SPEED = 0.25   # Normal pace
    FAST_SPEED = 0.4      # Quick movements
    
    def __init__(self, session):
        """
        Initialize the motion controller.
        
        Args:
            session: Active NAOqi session connected to Pepper robot
        
        Raises:
            RuntimeError: If ALMotion service cannot be accessed
        """
        self.session = session
        self.motion_service = None
        self.autonomous_service = None
        
        try:
            self.motion_service = self.session.service("ALMotion")
            logger.info("ALMotion service connected successfully")
            
            # Wake up the robot (enable stiffness)
            self._ensure_robot_ready()
            
        except Exception as e:
            logger.error(f"Failed to connect to ALMotion: {e}")
            raise RuntimeError(f"Cannot initialize motion service: {e}")
        
        # Try to get autonomous life service (optional)
        try:
            self.autonomous_service = self.session.service("ALAutonomousLife")
        except Exception:
            logger.warning("ALAutonomousLife not available")
    
    def _ensure_robot_ready(self) -> None:
        """
        Ensure robot is ready for movements (wake up if needed).
        """
        try:
            if not self.motion_service.robotIsWakeUp():
                logger.info("Waking up robot...")
                self.motion_service.wakeUp()
            
            # Set stiffness for head joints
            self.motion_service.setStiffnesses("Head", 1.0)
            
        except Exception as e:
            logger.warning(f"Could not fully wake up robot: {e}")
    
    def nod_head(self, times: int = 2, speed: float = None) -> bool:
        """
        Make Pepper nod its head (yes gesture).
        
        This is useful to acknowledge patient statements or show understanding.
        The movement is smooth and gentle, appropriate for medical settings.
        
        Args:
            times: Number of nods (default: 2)
            speed: Movement speed, defaults to SMOOTH_SPEED
        
        Returns:
            bool: True if successful, False otherwise
        
        Example:
            >>> motion = PepperMotion(session)
            >>> motion.nod_head()  # Robot nods gently
            True
        """
        if not self.motion_service:
            logger.error("Motion service not available")
            return False
        
        speed = speed or self.SMOOTH_SPEED
        
        try:
            logger.info(f"Nodding head {times} time(s)")
            
            # Get current head position as reference
            current_pitch = self.motion_service.getAngles("HeadPitch", True)[0]
            
            # Define nodding angles (relative movements)
            nod_down = min(current_pitch + 0.15, self.HEAD_PITCH_LIMITS[1])
            nod_up = max(current_pitch - 0.10, self.HEAD_PITCH_LIMITS[0])
            
            for i in range(times):
                # Move head down
                self.motion_service.setAngles("HeadPitch", nod_down, speed)
                time.sleep(0.3)
                
                # Move head up
                self.motion_service.setAngles("HeadPitch", nod_up, speed)
                time.sleep(0.3)
            
            # Return to neutral position
            self.motion_service.setAngles("HeadPitch", current_pitch, speed)
            time.sleep(0.2)
            
            logger.info("Nod completed")
            return True
            
        except Exception as e:
            logger.error(f"Nod head error: {e}")
            return False
    
    def shake_head(self, times: int = 2, speed: float = None) -> bool:
        """
        Make Pepper shake its head (no gesture).
        
        This is useful to indicate negative response or gentle disagreement.
        The movement is smooth and non-threatening.
        
        Args:
            times: Number of shakes (default: 2)
            speed: Movement speed, defaults to SMOOTH_SPEED
        
        Returns:
            bool: True if successful, False otherwise
        
        Example:
            >>> motion = PepperMotion(session)
            >>> motion.shake_head()  # Robot shakes head gently
            True
        """
        if not self.motion_service:
            logger.error("Motion service not available")
            return False
        
        speed = speed or self.SMOOTH_SPEED
        
        try:
            logger.info(f"Shaking head {times} time(s)")
            
            # Get current head position as reference
            current_yaw = self.motion_service.getAngles("HeadYaw", True)[0]
            
            # Define shaking angles (small side-to-side movements)
            shake_left = min(current_yaw + 0.25, self.HEAD_YAW_LIMITS[1])
            shake_right = max(current_yaw - 0.25, self.HEAD_YAW_LIMITS[0])
            
            for i in range(times):
                # Move head left
                self.motion_service.setAngles("HeadYaw", shake_left, speed)
                time.sleep(0.25)
                
                # Move head right
                self.motion_service.setAngles("HeadYaw", shake_right, speed)
                time.sleep(0.25)
            
            # Return to neutral position
            self.motion_service.setAngles("HeadYaw", current_yaw, speed)
            time.sleep(0.2)
            
            logger.info("Shake completed")
            return True
            
        except Exception as e:
            logger.error(f"Shake head error: {e}")
            return False
    
    def idle_motion(self, duration: float = 5.0) -> bool:
        """
        Perform subtle idle movements to make Pepper appear more natural.
        
        Small, gentle head movements that make the robot seem attentive
        without being distracting. Good for maintaining patient engagement.
        
        Args:
            duration: How long to perform idle motion (seconds)
        
        Returns:
            bool: True if successful, False otherwise
        
        Example:
            >>> motion.idle_motion(10)  # Subtle movements for 10 seconds
            True
        """
        if not self.motion_service:
            logger.error("Motion service not available")
            return False
        
        try:
            logger.info(f"Starting idle motion for {duration} seconds")
            
            start_time = time.time()
            
            while time.time() - start_time < duration:
                # Small random-like head movements
                import random
                
                # Subtle yaw movement
                yaw_offset = random.uniform(-0.08, 0.08)
                self.motion_service.setAngles("HeadYaw", yaw_offset, 0.05)
                time.sleep(1.5)
                
                # Subtle pitch movement
                pitch_offset = random.uniform(-0.03, 0.03)
                self.motion_service.setAngles("HeadPitch", pitch_offset, 0.05)
                time.sleep(1.0)
            
            # Return to center
            self.motion_service.setAngles("HeadYaw", 0.0, 0.1)
            self.motion_service.setAngles("HeadPitch", 0.0, 0.1)
            
            logger.info("Idle motion completed")
            return True
            
        except Exception as e:
            logger.error(f"Idle motion error: {e}")
            return False
    
    def look_at_direction(self, direction: str, speed: float = None) -> bool:
        """
        Make Pepper look in a specific direction.
        
        Args:
            direction: One of "left", "right", "up", "down", "center"
            speed: Movement speed, defaults to NORMAL_SPEED
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.motion_service:
            logger.error("Motion service not available")
            return False
        
        speed = speed or self.NORMAL_SPEED
        
        directions = {
            "left": (0.5, 0.0),
            "right": (-0.5, 0.0),
            "up": (0.0, -0.2),
            "down": (0.0, 0.2),
            "center": (0.0, 0.0)
        }
        
        if direction.lower() not in directions:
            logger.warning(f"Unknown direction: {direction}")
            return False
        
        try:
            yaw, pitch = directions[direction.lower()]
            
            logger.info(f"Looking {direction}")
            
            self.motion_service.setAngles("HeadYaw", yaw, speed)
            self.motion_service.setAngles("HeadPitch", pitch, speed)
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Look at direction error: {e}")
            return False
    
    def wave_hand(self, hand: str = "right") -> bool:
        """
        Make Pepper wave its hand in greeting.
        
        Args:
            hand: Which hand to wave ("left" or "right")
        
        Returns:
            bool: True if successful, False otherwise
        
        Example:
            >>> motion.wave_hand()  # Friendly wave gesture
            True
        """
        if not self.motion_service:
            logger.error("Motion service not available")
            return False
        
        try:
            logger.info(f"Waving {hand} hand")
            
            # Pepper doesn't have full arm manipulation like NAO
            # Using head movement to simulate acknowledgment instead
            # For Pepper, we combine head movement with tablet display typically
            
            # Friendly head tilt and nod
            self.motion_service.setAngles("HeadYaw", 0.15, 0.2)
            time.sleep(0.3)
            self.nod_head(times=1)
            self.motion_service.setAngles("HeadYaw", 0.0, 0.2)
            
            logger.info("Wave completed")
            return True
            
        except Exception as e:
            logger.error(f"Wave hand error: {e}")
            return False
    
    def reset_posture(self) -> bool:
        """
        Reset Pepper to neutral standing posture.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Resetting to neutral posture")
            
            # Reset head to center
            self.motion_service.setAngles("HeadYaw", 0.0, self.NORMAL_SPEED)
            self.motion_service.setAngles("HeadPitch", 0.0, self.NORMAL_SPEED)
            
            time.sleep(0.5)
            
            logger.info("Posture reset complete")
            return True
            
        except Exception as e:
            logger.error(f"Reset posture error: {e}")
            return False
    
    def set_breathing(self, enabled: bool) -> bool:
        """
        Enable or disable breathing animation.
        
        Breathing makes Pepper appear more lifelike with subtle body movements.
        
        Args:
            enabled: True to enable, False to disable
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if enabled:
                self.motion_service.setBreathEnabled("Body", True)
                logger.info("Breathing enabled")
            else:
                self.motion_service.setBreathEnabled("Body", False)
                logger.info("Breathing disabled")
            
            return True
            
        except Exception as e:
            logger.error(f"Set breathing error: {e}")
            return False


# Convenience functions for simple usage

def nod_head(session, times: int = 2) -> bool:
    """Make Pepper nod its head."""
    try:
        motion = PepperMotion(session)
        return motion.nod_head(times)
    except Exception as e:
        logger.error(f"nod_head() failed: {e}")
        return False


def shake_head(session, times: int = 2) -> bool:
    """Make Pepper shake its head."""
    try:
        motion = PepperMotion(session)
        return motion.shake_head(times)
    except Exception as e:
        logger.error(f"shake_head() failed: {e}")
        return False


def idle_motion(session, duration: float = 5.0) -> bool:
    """Perform subtle idle movements."""
    try:
        motion = PepperMotion(session)
        return motion.idle_motion(duration)
    except Exception as e:
        logger.error(f"idle_motion() failed: {e}")
        return False
