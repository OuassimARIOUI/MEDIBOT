"""
pepper_behavior.py - Choregraphe behavior management for Pepper robot.

This module handles launching predefined Choregraphe behaviors/animations.
Behaviors are pre-created animations that can be triggered by name.

Author: MediBot Team
"""

import time
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PepperBehavior:
    """
    Behavior controller for launching Choregraphe animations on Pepper.
    
    This class manages predefined behaviors created in Choregraphe.
    Behaviors are complex animations that combine motion, speech, and LEDs.
    
    Attributes:
        session: NAOqi session connected to Pepper
        behavior_service: ALBehaviorManager proxy for behavior control
    
    Common Behavior Names (examples):
        - "animations/Stand/Gestures/Hey_1"
        - "animations/Stand/Emotions/Positive/Happy_4"
        - "animations/Stand/Emotions/Negative/Sad_1"
        - "animations/Stand/Waiting/WakeUp_1"
    """
    
    # Predefined behavior categories for medical context
    BEHAVIOR_CATEGORIES = {
        "greeting": [
            "animations/Stand/Gestures/Hey_1",
            "animations/Stand/Gestures/Hey_2",
            "animations/Stand/Gestures/Hey_3",
        ],
        "happy": [
            "animations/Stand/Emotions/Positive/Happy_4",
            "animations/Stand/Emotions/Positive/Enthusiastic_1",
        ],
        "calm": [
            "animations/Stand/Emotions/Neutral/Calm_1",
            "animations/Stand/Waiting/ScratchHead_1",
        ],
        "empathy": [
            "animations/Stand/Emotions/Negative/Sad_1",
            "animations/Stand/Emotions/Negative/Sorry_1",
        ],
        "thinking": [
            "animations/Stand/Gestures/Thinking_3",
            "animations/Stand/Gestures/Thinking_8",
        ],
        "acknowledge": [
            "animations/Stand/Gestures/Yes_1",
            "animations/Stand/Gestures/Yes_2",
        ],
        "attention": [
            "animations/Stand/Gestures/ShowSky_1",
            "animations/Stand/Gestures/ComeOn_1",
        ],
    }
    
    def __init__(self, session):
        """
        Initialize the behavior controller.
        
        Args:
            session: Active NAOqi session connected to Pepper robot
        
        Raises:
            RuntimeError: If ALBehaviorManager service cannot be accessed
        """
        self.session = session
        self.behavior_service = None
        self._installed_behaviors = []
        
        try:
            self.behavior_service = self.session.service("ALBehaviorManager")
            logger.info("ALBehaviorManager service connected successfully")
            
            # Cache installed behaviors
            self._refresh_installed_behaviors()
            
        except Exception as e:
            logger.error(f"Failed to connect to ALBehaviorManager: {e}")
            raise RuntimeError(f"Cannot initialize behavior service: {e}")
    
    def _refresh_installed_behaviors(self) -> None:
        """
        Refresh the cache of installed behaviors on the robot.
        """
        try:
            self._installed_behaviors = self.behavior_service.getInstalledBehaviors()
            logger.info(f"Found {len(self._installed_behaviors)} installed behaviors")
        except Exception as e:
            logger.warning(f"Could not refresh behaviors: {e}")
            self._installed_behaviors = []
    
    def run_behavior(self, name: str, wait: bool = True) -> bool:
        """
        Launch a Choregraphe behavior by name.
        
        This function checks if the behavior exists before attempting to launch.
        Behaviors run asynchronously by default but can block until complete.
        
        Args:
            name: Full behavior name/path (e.g., "animations/Stand/Gestures/Hey_1")
            wait: If True, wait for behavior to complete. If False, return immediately.
        
        Returns:
            bool: True if behavior was launched successfully, False otherwise
        
        Example:
            >>> behavior = PepperBehavior(session)
            >>> behavior.run_behavior("animations/Stand/Gestures/Hey_1")
            True
        """
        if not self.behavior_service:
            logger.error("Behavior service not available")
            return False
        
        # Check if behavior exists
        if not self.behavior_exists(name):
            logger.warning(f"Behavior not found: {name}")
            self._suggest_similar_behaviors(name)
            return False
        
        try:
            logger.info(f"Running behavior: {name}")
            
            if wait:
                # Blocking call - wait for behavior to complete
                self.behavior_service.runBehavior(name)
            else:
                # Non-blocking call - return immediately
                self.behavior_service.post.runBehavior(name)
            
            logger.info(f"Behavior completed: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error running behavior '{name}': {e}")
            return False
    
    def behavior_exists(self, name: str) -> bool:
        """
        Check if a behavior is installed on the robot.
        
        Args:
            name: Behavior name to check
        
        Returns:
            bool: True if behavior exists, False otherwise
        """
        if not self.behavior_service:
            return False
        
        try:
            return self.behavior_service.isBehaviorInstalled(name)
        except Exception:
            return False
    
    def _suggest_similar_behaviors(self, name: str) -> None:
        """
        Log suggestions for similar behavior names.
        """
        name_lower = name.lower()
        similar = []
        
        for behavior in self._installed_behaviors:
            if any(part in behavior.lower() for part in name_lower.split("/")):
                similar.append(behavior)
        
        if similar[:5]:
            logger.info(f"Similar behaviors available: {similar[:5]}")
    
    def stop_behavior(self, name: str) -> bool:
        """
        Stop a running behavior.
        
        Args:
            name: Behavior name to stop
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.behavior_service:
            return False
        
        try:
            self.behavior_service.stopBehavior(name)
            logger.info(f"Stopped behavior: {name}")
            return True
        except Exception as e:
            logger.error(f"Error stopping behavior: {e}")
            return False
    
    def stop_all_behaviors(self) -> bool:
        """
        Stop all currently running behaviors.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.behavior_service:
            return False
        
        try:
            self.behavior_service.stopAllBehaviors()
            logger.info("Stopped all behaviors")
            return True
        except Exception as e:
            logger.error(f"Error stopping all behaviors: {e}")
            return False
    
    def get_running_behaviors(self) -> List[str]:
        """
        Get list of currently running behaviors.
        
        Returns:
            List of running behavior names
        """
        if not self.behavior_service:
            return []
        
        try:
            return self.behavior_service.getRunningBehaviors()
        except Exception:
            return []
    
    def get_installed_behaviors(self) -> List[str]:
        """
        Get list of all installed behaviors on the robot.
        
        Returns:
            List of installed behavior names
        """
        return self._installed_behaviors.copy()
    
    def run_by_category(self, category: str, wait: bool = True) -> bool:
        """
        Run a behavior from a predefined category.
        
        This is useful for running contextually appropriate behaviors
        without knowing exact behavior names.
        
        Args:
            category: Category name (greeting, happy, calm, empathy, thinking, etc.)
            wait: If True, wait for behavior to complete
        
        Returns:
            bool: True if a behavior was run, False otherwise
        
        Example:
            >>> behavior.run_by_category("greeting")  # Run a greeting animation
            True
        """
        category_lower = category.lower()
        
        if category_lower not in self.BEHAVIOR_CATEGORIES:
            logger.warning(f"Unknown category: {category}")
            logger.info(f"Available categories: {list(self.BEHAVIOR_CATEGORIES.keys())}")
            return False
        
        # Try behaviors from the category until one works
        for behavior_name in self.BEHAVIOR_CATEGORIES[category_lower]:
            if self.behavior_exists(behavior_name):
                return self.run_behavior(behavior_name, wait)
        
        logger.warning(f"No behaviors available for category: {category}")
        return False
    
    def play_animation(self, emotion: str, wait: bool = True) -> bool:
        """
        Play an animation appropriate for an emotional context.
        
        Maps emotions to behavior categories and runs an appropriate animation.
        
        Args:
            emotion: Emotion name (happy, calm, stress, etc.)
            wait: If True, wait for animation to complete
        
        Returns:
            bool: True if animation was played, False otherwise
        """
        # Map emotions to behavior categories
        emotion_to_category = {
            "happy": "happy",
            "calm": "calm",
            "good": "happy",
            "neutral": "calm",
            "stress": "empathy",
            "anxious": "empathy",
            "sad": "empathy",
            "greeting": "greeting",
            "thinking": "thinking",
            "yes": "acknowledge",
            "acknowledge": "acknowledge",
        }
        
        emotion_lower = emotion.lower()
        category = emotion_to_category.get(emotion_lower, "calm")
        
        return self.run_by_category(category, wait)
    
    def is_behavior_running(self, name: str = None) -> bool:
        """
        Check if a behavior (or any behavior) is currently running.
        
        Args:
            name: Specific behavior to check. If None, checks if any is running.
        
        Returns:
            bool: True if behavior is running, False otherwise
        """
        running = self.get_running_behaviors()
        
        if name is None:
            return len(running) > 0
        else:
            return name in running


# Convenience function for simple usage
def run_behavior(name: str, session=None, wait: bool = True) -> bool:
    """
    Simple function to run a Choregraphe behavior.
    
    Args:
        name: Behavior name/path
        session: NAOqi session
        wait: If True, wait for behavior to complete
    
    Returns:
        bool: True if successful, False otherwise
    """
    if session is None:
        logger.error("No session provided. Cannot run behavior without connection to Pepper.")
        return False
    
    try:
        behavior = PepperBehavior(session)
        return behavior.run_behavior(name, wait)
    except Exception as e:
        logger.error(f"run_behavior() failed: {e}")
        return False
