"""
pepper_main.py - Main orchestration loop for Pepper robot.

This module serves as the central coordinator for all robot actions.
It connects to Pepper and dispatches high-level commands to appropriate modules.

Author: MediBot Team
"""

import os
import time
import logging
import threading
from typing import Optional, Dict, Any, Callable
from queue import Queue, Empty

# Import robot control modules
from .pepper_tts import PepperTTS
from .pepper_motion import PepperMotion
from .pepper_leds import PepperLEDs
from .pepper_behavior import PepperBehavior
from .pepper_camera import PepperCamera

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PepperController:
    """
    Main controller for Pepper robot orchestration.
    
    This class coordinates all robot subsystems (TTS, motion, LEDs, behaviors).
    It receives high-level commands and dispatches them to appropriate modules.
    
    The controller does NOT connect to RASA directly - it receives commands
    from an external source (API, queue, etc.) and executes them.
    
    Attributes:
        session: NAOqi session connected to Pepper
        tts: Text-to-speech controller
        motion: Motion and gesture controller
        leds: LED emotion controller
        behavior: Choregraphe behavior controller
        camera: Camera access controller
    
    Environment Variables:
        PEPPER_IP: Robot IP address (default: "127.0.0.1")
        PEPPER_PORT: Robot port (default: 9559)
    
    Example:
        >>> controller = PepperController()
        >>> controller.connect()
        >>> controller.execute_command({
        ...     "text": "Bonjour, comment allez-vous?",
        ...     "emotion": "happy",
        ...     "gesture": "nod"
        ... })
    """
    
    # Default connection settings
    DEFAULT_IP = "127.0.0.1"
    DEFAULT_PORT = 9559
    
    # Gesture name to function mapping
    GESTURE_MAP = {
        "nod": "nod_head",
        "shake": "shake_head",
        "wave": "wave_hand",
        "look_left": "look_at_direction",
        "look_right": "look_at_direction",
        "look_up": "look_at_direction",
        "look_down": "look_at_direction",
        "idle": "idle_motion",
        "reset": "reset_posture",
    }
    
    def __init__(self, ip: str = None, port: int = None):
        """
        Initialize the Pepper controller.
        
        Args:
            ip: Robot IP address. Uses PEPPER_IP env var if not provided.
            port: Robot port. Uses PEPPER_PORT env var if not provided.
        """
        # Get connection settings from environment or use defaults
        self.ip = ip or os.getenv("PEPPER_IP", self.DEFAULT_IP)
        self.port = port or int(os.getenv("PEPPER_PORT", self.DEFAULT_PORT))
        
        # NAOqi session
        self.session = None
        
        # Subsystem controllers (initialized on connect)
        self.tts: Optional[PepperTTS] = None
        self.motion: Optional[PepperMotion] = None
        self.leds: Optional[PepperLEDs] = None
        self.behavior: Optional[PepperBehavior] = None
        self.camera: Optional[PepperCamera] = None
        
        # Command queue for async processing
        self._command_queue: Queue = Queue()
        self._running = False
        self._loop_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self._on_command_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        
        logger.info(f"PepperController initialized (target: {self.ip}:{self.port})")
    
    def connect(self) -> bool:
        """
        Connect to Pepper robot and initialize all subsystems.
        
        Establishes NAOqi session and creates controller instances
        for all robot subsystems (TTS, motion, LEDs, behaviors, camera).
        
        Returns:
            bool: True if connection successful, False otherwise
        
        Example:
            >>> controller = PepperController()
            >>> if controller.connect():
            ...     print("Connected to Pepper!")
        """
        try:
            logger.info(f"Connecting to Pepper at {self.ip}:{self.port}...")
            
            # Import qi here to avoid import errors when NAOqi not installed
            import qi
            
            # Create NAOqi session
            self.session = qi.Session()
            self.session.connect(f"tcp://{self.ip}:{self.port}")
            
            logger.info("NAOqi session established")
            
            # Initialize subsystems
            self._init_subsystems()
            
            logger.info("All subsystems initialized successfully")
            return True
            
        except ImportError:
            logger.error("NAOqi SDK (qi module) not found. Cannot connect to Pepper.")
            return False
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._handle_connection_error(e)
            return False
    
    def _init_subsystems(self) -> None:
        """
        Initialize all robot subsystem controllers.
        
        Called after successful NAOqi session connection.
        Each subsystem is initialized independently for fault tolerance.
        """
        # Initialize TTS
        try:
            self.tts = PepperTTS(self.session)
            logger.info("TTS subsystem ready")
        except Exception as e:
            logger.warning(f"TTS init failed: {e}")
        
        # Initialize Motion
        try:
            self.motion = PepperMotion(self.session)
            logger.info("Motion subsystem ready")
        except Exception as e:
            logger.warning(f"Motion init failed: {e}")
        
        # Initialize LEDs
        try:
            self.leds = PepperLEDs(self.session)
            logger.info("LEDs subsystem ready")
        except Exception as e:
            logger.warning(f"LEDs init failed: {e}")
        
        # Initialize Behavior
        try:
            self.behavior = PepperBehavior(self.session)
            logger.info("Behavior subsystem ready")
        except Exception as e:
            logger.warning(f"Behavior init failed: {e}")
        
        # Initialize Camera
        try:
            self.camera = PepperCamera(self.session)
            logger.info("Camera subsystem ready")
        except Exception as e:
            logger.warning(f"Camera init failed: {e}")
    
    def _handle_connection_error(self, error: Exception) -> None:
        """
        Handle connection failures gracefully.
        
        Args:
            error: The exception that occurred
        """
        logger.error("=" * 50)
        logger.error("PEPPER CONNECTION FAILED")
        logger.error(f"Target: {self.ip}:{self.port}")
        logger.error(f"Error: {error}")
        logger.error("")
        logger.error("Possible causes:")
        logger.error("  1. Pepper robot is not powered on")
        logger.error("  2. Incorrect IP address or port")
        logger.error("  3. Network connectivity issues")
        logger.error("  4. NAOqi not running on robot")
        logger.error("")
        logger.error("To configure connection, set environment variables:")
        logger.error("  PEPPER_IP=<robot_ip>")
        logger.error("  PEPPER_PORT=<robot_port>")
        logger.error("=" * 50)
        
        if self._on_error:
            self._on_error(error)
    
    def disconnect(self) -> None:
        """
        Disconnect from Pepper and cleanup resources.
        """
        logger.info("Disconnecting from Pepper...")
        
        # Stop main loop if running
        self.stop()
        
        # Release camera resources
        if self.camera:
            self.camera.release()
        
        # Reset LEDs to neutral
        if self.leds:
            try:
                self.leds.reset()
            except Exception:
                pass
        
        # Close session
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
        
        self.session = None
        logger.info("Disconnected from Pepper")
    
    def is_connected(self) -> bool:
        """
        Check if connected to Pepper.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self.session is not None
    
    def execute_command(self, command: Dict[str, Any]) -> bool:
        """
        Execute a high-level robot command.
        
        This is the main entry point for robot actions. Commands are
        dictionaries containing instructions for various subsystems.
        
        Args:
            command: Dictionary with command parameters:
                - text (str): Text for TTS to speak
                - emotion (str): Emotion for LED display
                - gesture (str): Gesture to perform
                - behavior (str): Choregraphe behavior to run
                - wait (bool): Wait for actions to complete (default True)
        
        Returns:
            bool: True if command executed successfully
        
        Example:
            >>> controller.execute_command({
            ...     "text": "Bonjour!",
            ...     "emotion": "happy",
            ...     "gesture": "nod"
            ... })
        """
        if not self.is_connected():
            logger.error("Not connected to Pepper")
            return False
        
        logger.info(f"Executing command: {command}")
        
        try:
            wait = command.get("wait", True)
            success = True
            
            # 1. Set emotion LED first (visual feedback is immediate)
            emotion = command.get("emotion")
            if emotion and self.leds:
                if not self.leds.set_emotion_led(emotion):
                    logger.warning(f"Failed to set emotion: {emotion}")
            
            # 2. Perform gesture (can be concurrent with speech)
            gesture = command.get("gesture")
            if gesture and self.motion:
                self._execute_gesture(gesture)
            
            # 3. Speak text (usually the main action)
            text = command.get("text")
            if text and self.tts:
                if wait:
                    success = self.tts.speak(text) and success
                else:
                    self.tts.speak_async(text)
            
            # 4. Run behavior if specified
            behavior_name = command.get("behavior")
            if behavior_name and self.behavior:
                if not self.behavior.run_behavior(behavior_name, wait):
                    logger.warning(f"Failed to run behavior: {behavior_name}")
            
            # Notify completion
            if self._on_command_complete:
                self._on_command_complete(command, success)
            
            return success
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            if self._on_error:
                self._on_error(e)
            return False
    
    def _execute_gesture(self, gesture: str) -> bool:
        """
        Execute a gesture by name.
        
        Args:
            gesture: Gesture name (nod, shake, wave, etc.)
        
        Returns:
            bool: True if successful
        """
        gesture_lower = gesture.lower()
        
        if gesture_lower == "nod":
            return self.motion.nod_head()
        elif gesture_lower == "shake":
            return self.motion.shake_head()
        elif gesture_lower == "wave":
            return self.motion.wave_hand()
        elif gesture_lower.startswith("look_"):
            direction = gesture_lower.replace("look_", "")
            return self.motion.look_at_direction(direction)
        elif gesture_lower == "idle":
            return self.motion.idle_motion(duration=3.0)
        elif gesture_lower == "reset":
            return self.motion.reset_posture()
        else:
            logger.warning(f"Unknown gesture: {gesture}")
            return False
    
    def speak(self, text: str, emotion: str = None) -> bool:
        """
        Convenience method to make Pepper speak.
        
        Args:
            text: Text to speak
            emotion: Optional emotion to display
        
        Returns:
            bool: True if successful
        """
        return self.execute_command({"text": text, "emotion": emotion})
    
    def react(self, emotion: str, text: str = None) -> bool:
        """
        React with an emotion (LED + optional speech).
        
        Args:
            emotion: Emotion to display
            text: Optional text to speak
        
        Returns:
            bool: True if successful
        """
        command = {"emotion": emotion}
        if text:
            command["text"] = text
        return self.execute_command(command)
    
    def greet(self, patient_name: str = None) -> bool:
        """
        Perform a greeting sequence.
        
        Args:
            patient_name: Optional patient name for personalization
        
        Returns:
            bool: True if successful
        """
        if patient_name:
            text = f"Bonjour {patient_name}, comment allez-vous aujourd'hui?"
        else:
            text = "Bonjour, comment allez-vous aujourd'hui?"
        
        return self.execute_command({
            "text": text,
            "emotion": "happy",
            "gesture": "nod"
        })
    
    # =========================================================================
    # ASYNC COMMAND LOOP
    # =========================================================================
    
    def start(self) -> None:
        """
        Start the asynchronous command processing loop.
        
        Commands can be queued via queue_command() and will be
        processed sequentially in a background thread.
        """
        if self._running:
            logger.warning("Command loop already running")
            return
        
        if not self.is_connected():
            logger.error("Not connected to Pepper. Call connect() first.")
            return
        
        self._running = True
        self._loop_thread = threading.Thread(target=self._command_loop, daemon=True)
        self._loop_thread.start()
        
        logger.info("Command loop started")
    
    def stop(self) -> None:
        """
        Stop the command processing loop.
        """
        self._running = False
        
        if self._loop_thread:
            self._loop_thread.join(timeout=2.0)
            self._loop_thread = None
        
        logger.info("Command loop stopped")
    
    def _command_loop(self) -> None:
        """
        Main command processing loop (runs in background thread).
        """
        logger.info("Command loop thread started")
        
        while self._running:
            try:
                # Wait for command with timeout (allows checking _running flag)
                command = self._command_queue.get(timeout=0.5)
                
                # Execute the command
                self.execute_command(command)
                
                self._command_queue.task_done()
                
            except Empty:
                # No command in queue, continue waiting
                continue
                
            except Exception as e:
                logger.error(f"Command loop error: {e}")
                if self._on_error:
                    self._on_error(e)
        
        logger.info("Command loop thread ended")
    
    def queue_command(self, command: Dict[str, Any]) -> None:
        """
        Queue a command for asynchronous execution.
        
        Args:
            command: Command dictionary to queue
        """
        self._command_queue.put(command)
        logger.debug(f"Command queued: {command}")
    
    def set_on_command_complete(self, callback: Callable) -> None:
        """
        Set callback for command completion.
        
        Args:
            callback: Function(command, success) called after each command
        """
        self._on_command_complete = callback
    
    def set_on_error(self, callback: Callable) -> None:
        """
        Set callback for error handling.
        
        Args:
            callback: Function(error) called on errors
        """
        self._on_error = callback
    
    # =========================================================================
    # CONTEXT MANAGER
    # =========================================================================
    
    def __enter__(self):
        """Context manager entry - connect to robot."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - disconnect from robot."""
        self.disconnect()
        return False


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_controller() -> PepperController:
    """
    Create and connect a PepperController instance.
    
    Uses environment variables for configuration:
        - PEPPER_IP: Robot IP address
        - PEPPER_PORT: Robot port
    
    Returns:
        PepperController: Connected controller (or unconnected if failed)
    """
    controller = PepperController()
    controller.connect()
    return controller


def quick_speak(text: str, emotion: str = None) -> bool:
    """
    Quick function to make Pepper speak once.
    
    Connects, speaks, and disconnects. Use for one-off messages.
    
    Args:
        text: Text to speak
        emotion: Optional emotion
    
    Returns:
        bool: True if successful
    """
    try:
        with PepperController() as controller:
            return controller.speak(text, emotion)
    except Exception as e:
        logger.error(f"quick_speak failed: {e}")
        return False


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Demo/test entry point.
    
    Run directly to test connection and basic functionality.
    """
    print("=" * 60)
    print("MEDIBOT - Pepper Robot Controller")
    print("=" * 60)
    print()
    
    # Check environment configuration
    pepper_ip = os.getenv("PEPPER_IP", "NOT SET")
    pepper_port = os.getenv("PEPPER_PORT", "NOT SET")
    
    print(f"Configuration:")
    print(f"  PEPPER_IP:   {pepper_ip}")
    print(f"  PEPPER_PORT: {pepper_port}")
    print()
    
    if pepper_ip == "NOT SET":
        print("Warning: PEPPER_IP not configured!")
        print("  Set environment variable: PEPPER_IP=<robot_ip>")
        print()
    
    # Attempt connection
    print("Attempting to connect to Pepper...")
    controller = PepperController()
    
    if controller.connect():
        print("Connected successfully!")
        print()
        
        # Demo sequence
        print("Running demo sequence...")
        
        # Greeting
        controller.speak("Bonjour, je suis MediBot, votre assistant médical.", "happy")
        time.sleep(1)
        
        # Nod
        if controller.motion:
            controller.motion.nod_head()
        
        # Different emotions
        for emotion in ["calm", "happy", "neutral"]:
            controller.react(emotion)
            time.sleep(0.5)
        
        print("Demo complete!")
        
        # Cleanup
        controller.disconnect()
        
    else:
        print("Connection failed. Check configuration and robot status.")
    
    print()
    print("=" * 60)
