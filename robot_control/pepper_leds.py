"""
pepper_leds.py - LED control for Pepper robot emotions.

This module manages Pepper's LED system to express emotions visually.
LEDs are mapped to emotional states for intuitive patient interaction.

Author: MediBot Team
"""

import time
import logging
from typing import Tuple, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PepperLEDs:
    """
    LED controller for Pepper robot's emotional expressions.
    
    This class manages Pepper's eye and body LEDs to visually communicate
    emotional states. Color mappings are designed for medical contexts.
    
    Attributes:
        session: NAOqi session connected to Pepper
        leds_service: ALLeds proxy for LED control
    
    Emotion Color Mapping:
        - calm: Blue (0x0066CC) - Peaceful, reassuring
        - happy: Green (0x00CC66) - Positive, encouraging  
        - stress: Orange (0xFF9933) - Attention needed
        - emergency: Red (0xFF0000) - Urgent, immediate attention
        - neutral: White (0xFFFFFF) - Default state
        - listening: Cyan (0x00CCCC) - Active listening
    """
    
    # Emotion to color mapping (RGB hex values)
    EMOTION_COLORS = {
        "calm": 0x0066CC,       # Blue - peaceful and reassuring
        "happy": 0x00CC66,      # Green - positive and encouraging
        "stress": 0xFF9933,     # Orange - attention needed
        "emergency": 0xFF0000,  # Red - urgent, immediate attention
        "neutral": 0xFFFFFF,    # White - default state
        "listening": 0x00CCCC,  # Cyan - actively listening
        "thinking": 0x9933FF,   # Purple - processing information
        "sad": 0x3366FF,        # Soft blue - empathetic
        "alert": 0xFFCC00,      # Yellow - mild alert
    }
    
    # LED group names on Pepper
    LED_GROUPS = {
        "eyes": "FaceLeds",
        "chest": "ChestLeds",
        "ears": "EarLeds",
        "all_face": "FaceLeds",
    }
    
    # Animation durations (in seconds)
    FADE_DURATION = 0.5
    BLINK_DURATION = 0.3
    
    def __init__(self, session):
        """
        Initialize the LED controller.
        
        Args:
            session: Active NAOqi session connected to Pepper robot
        
        Raises:
            RuntimeError: If ALLeds service cannot be accessed
        """
        self.session = session
        self.leds_service = None
        self._current_emotion = "neutral"
        
        try:
            self.leds_service = self.session.service("ALLeds")
            logger.info("ALLeds service connected successfully")
            
            # Set initial neutral state
            self.set_emotion_led("neutral")
            
        except Exception as e:
            logger.error(f"Failed to connect to ALLeds: {e}")
            raise RuntimeError(f"Cannot initialize LED service: {e}")
    
    def _hex_to_rgb(self, hex_color: int) -> Tuple[float, float, float]:
        """
        Convert hex color to RGB tuple (0.0-1.0 range).
        
        Args:
            hex_color: Color as hex integer (e.g., 0xFF0000)
        
        Returns:
            Tuple of (red, green, blue) values from 0.0 to 1.0
        """
        r = ((hex_color >> 16) & 0xFF) / 255.0
        g = ((hex_color >> 8) & 0xFF) / 255.0
        b = (hex_color & 0xFF) / 255.0
        return (r, g, b)
    
    def set_emotion_led(self, emotion: str, fade: bool = True) -> bool:
        """
        Set LED colors to reflect an emotional state.
        
        This is the main function for emotional LED feedback.
        Colors are designed to be intuitive in medical contexts.
        
        Args:
            emotion: Emotion name (calm, happy, stress, emergency, etc.)
            fade: If True, fade to color. If False, change immediately.
        
        Returns:
            bool: True if successful, False otherwise
        
        Example:
            >>> leds = PepperLEDs(session)
            >>> leds.set_emotion_led("calm")      # Soothing blue
            >>> leds.set_emotion_led("emergency") # Alert red
        """
        if not self.leds_service:
            logger.error("LED service not available")
            return False
        
        emotion_lower = emotion.lower().strip()
        
        # Map unknown emotions to closest known emotion
        if emotion_lower not in self.EMOTION_COLORS:
            logger.warning(f"Unknown emotion '{emotion}', defaulting to neutral")
            emotion_lower = "neutral"
        
        try:
            color = self.EMOTION_COLORS[emotion_lower]
            
            logger.info(f"Setting emotion LED: {emotion_lower} (color: {hex(color)})")
            
            if fade:
                # Smooth fade transition
                self.leds_service.fadeRGB(
                    "FaceLeds",
                    color,
                    self.FADE_DURATION
                )
            else:
                # Immediate color change
                r, g, b = self._hex_to_rgb(color)
                self.leds_service.setIntensity("FaceLeds", 1.0)
                self.leds_service.fadeRGB("FaceLeds", color, 0.01)
            
            self._current_emotion = emotion_lower
            
            # Special handling for emergency - add blinking
            if emotion_lower == "emergency":
                self._start_emergency_blink()
            
            return True
            
        except Exception as e:
            logger.error(f"Set emotion LED error: {e}")
            return False
    
    def _start_emergency_blink(self) -> None:
        """
        Start emergency blinking pattern (non-blocking).
        
        Creates an urgent visual signal for critical situations.
        """
        try:
            # Create blinking pattern using rotateEyes
            # This runs asynchronously on the robot
            self.leds_service.post.rotateEyes(
                0xFF0000,  # Red color
                1.0,       # Rotation time
                3.0        # Total duration in seconds
            )
        except Exception as e:
            logger.warning(f"Could not start emergency blink: {e}")
    
    def set_color_rgb(self, r: float, g: float, b: float, 
                      group: str = "eyes") -> bool:
        """
        Set LED color using RGB values.
        
        Args:
            r: Red component (0.0 to 1.0)
            g: Green component (0.0 to 1.0)
            b: Blue component (0.0 to 1.0)
            group: LED group ("eyes", "chest", "ears")
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.leds_service:
            logger.error("LED service not available")
            return False
        
        # Validate inputs
        r = max(0.0, min(1.0, r))
        g = max(0.0, min(1.0, g))
        b = max(0.0, min(1.0, b))
        
        led_group = self.LED_GROUPS.get(group, "FaceLeds")
        
        try:
            # Convert to hex
            color = (int(r * 255) << 16) | (int(g * 255) << 8) | int(b * 255)
            
            self.leds_service.fadeRGB(led_group, color, self.FADE_DURATION)
            
            logger.info(f"Set {group} color to RGB({r:.2f}, {g:.2f}, {b:.2f})")
            return True
            
        except Exception as e:
            logger.error(f"Set color RGB error: {e}")
            return False
    
    def set_intensity(self, intensity: float, group: str = "eyes") -> bool:
        """
        Set LED brightness/intensity.
        
        Args:
            intensity: Brightness level (0.0 to 1.0)
            group: LED group to adjust
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.leds_service:
            logger.error("LED service not available")
            return False
        
        intensity = max(0.0, min(1.0, intensity))
        led_group = self.LED_GROUPS.get(group, "FaceLeds")
        
        try:
            self.leds_service.setIntensity(led_group, intensity)
            logger.info(f"Set {group} intensity to {intensity:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Set intensity error: {e}")
            return False
    
    def blink(self, color: int = None, times: int = 2) -> bool:
        """
        Make LEDs blink a specified number of times.
        
        Args:
            color: Optional hex color for blink. Uses current if None.
            times: Number of blinks
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.leds_service:
            logger.error("LED service not available")
            return False
        
        try:
            # Use current emotion color if not specified
            if color is None:
                color = self.EMOTION_COLORS.get(self._current_emotion, 0xFFFFFF)
            
            logger.info(f"Blinking {times} time(s)")
            
            for _ in range(times):
                # Fade out
                self.leds_service.fadeRGB("FaceLeds", 0x000000, self.BLINK_DURATION)
                time.sleep(self.BLINK_DURATION)
                
                # Fade in
                self.leds_service.fadeRGB("FaceLeds", color, self.BLINK_DURATION)
                time.sleep(self.BLINK_DURATION)
            
            return True
            
        except Exception as e:
            logger.error(f"Blink error: {e}")
            return False
    
    def pulse(self, emotion: str, duration: float = 3.0) -> bool:
        """
        Create a gentle pulsing effect for an emotion.
        
        Good for indicating active listening or processing.
        
        Args:
            emotion: Emotion to pulse
            duration: Total duration of pulsing effect
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.leds_service:
            logger.error("LED service not available")
            return False
        
        emotion_lower = emotion.lower().strip()
        color = self.EMOTION_COLORS.get(emotion_lower, 0xFFFFFF)
        
        try:
            logger.info(f"Starting pulse effect for {emotion}")
            
            start_time = time.time()
            pulse_duration = 0.8
            
            while time.time() - start_time < duration:
                # Dim
                self.set_intensity(0.3)
                time.sleep(pulse_duration)
                
                # Bright
                self.set_intensity(1.0)
                time.sleep(pulse_duration)
            
            # Reset to normal
            self.set_intensity(1.0)
            
            return True
            
        except Exception as e:
            logger.error(f"Pulse error: {e}")
            return False
    
    def turn_off(self) -> bool:
        """
        Turn off all LEDs.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.leds_service.fadeRGB("FaceLeds", 0x000000, self.FADE_DURATION)
            logger.info("LEDs turned off")
            return True
            
        except Exception as e:
            logger.error(f"Turn off error: {e}")
            return False
    
    def reset(self) -> bool:
        """
        Reset LEDs to neutral/default state.
        
        Returns:
            bool: True if successful, False otherwise
        """
        return self.set_emotion_led("neutral")
    
    def get_current_emotion(self) -> str:
        """
        Get the currently displayed emotion.
        
        Returns:
            str: Current emotion name
        """
        return self._current_emotion


# Convenience function for simple usage
def set_emotion_led(emotion: str, session=None) -> bool:
    """
    Simple function to set emotion LED color.
    
    Args:
        emotion: Emotion name (calm, happy, stress, emergency, etc.)
        session: NAOqi session
    
    Returns:
        bool: True if successful, False otherwise
    """
    if session is None:
        logger.error("No session provided. Cannot set LEDs without connection to Pepper.")
        return False
    
    try:
        leds = PepperLEDs(session)
        return leds.set_emotion_led(emotion)
    except Exception as e:
        logger.error(f"set_emotion_led() failed: {e}")
        return False
