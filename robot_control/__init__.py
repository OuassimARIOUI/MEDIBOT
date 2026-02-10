"""
robot_control - Pepper Robot Control Module for MediBot.

This package provides control interfaces for the Pepper robot using NAOqi SDK.
It handles all physical robot actions: speech, gestures, LEDs, animations, and camera.

Architecture:
    - pepper_main.py     : Central orchestration and command dispatch
    - pepper_tts.py      : Text-to-speech (ALTextToSpeech)
    - pepper_motion.py   : Gestures and movements (ALMotion)
    - pepper_leds.py     : LED emotion display (ALLeds)
    - pepper_behavior.py : Choregraphe behaviors (ALBehaviorManager)
    - pepper_camera.py   : Camera access (ALVideoDevice)

Usage:
    from robot_control import PepperController
    
    # Using context manager (recommended)
    with PepperController() as pepper:
        pepper.speak("Bonjour!", emotion="happy")
        pepper.motion.nod_head()
    
    # Manual connection
    controller = PepperController()
    if controller.connect():
        controller.execute_command({
            "text": "Comment allez-vous?",
            "emotion": "calm",
            "gesture": "nod"
        })
        controller.disconnect()

Environment Variables:
    PEPPER_IP   : Robot IP address (default: 127.0.0.1)
    PEPPER_PORT : Robot port (default: 9559)

Author: MediBot Team
"""

# Main controller
from .pepper_main import (
    PepperController,
    create_controller,
    quick_speak,
)

# Individual subsystems (for advanced usage)
from .pepper_tts import PepperTTS, speak
from .pepper_motion import PepperMotion, nod_head, shake_head, idle_motion
from .pepper_leds import PepperLEDs, set_emotion_led
from .pepper_behavior import PepperBehavior, run_behavior
from .pepper_camera import PepperCamera, get_frame

# Version info
__version__ = "1.0.0"
__author__ = "MediBot Team"

# Public API
__all__ = [
    # Main controller
    "PepperController",
    "create_controller",
    "quick_speak",
    
    # Subsystem classes
    "PepperTTS",
    "PepperMotion",
    "PepperLEDs",
    "PepperBehavior",
    "PepperCamera",
    
    # Convenience functions
    "speak",
    "nod_head",
    "shake_head",
    "idle_motion",
    "set_emotion_led",
    "run_behavior",
    "get_frame",
]
