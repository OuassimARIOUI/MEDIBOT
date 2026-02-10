"""
pepper_tts.py - Text-to-Speech module for Pepper robot.

This module provides speech synthesis capabilities using NAOqi's ALTextToSpeech.
It handles voice output, language configuration, and connection error management.

Author: MediBot Team
"""

import os
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PepperTTS:
    """
    Text-to-Speech controller for Pepper robot.
    
    This class manages speech synthesis using NAOqi's ALTextToSpeech service.
    It provides methods to speak text, configure voice parameters, and handle
    connection errors gracefully.
    
    Attributes:
        session: NAOqi session connected to Pepper
        tts_service: ALTextToSpeech proxy for speech synthesis
        language: Current language setting (default: French)
    """
    
    # Supported languages mapping
    SUPPORTED_LANGUAGES = {
        "fr": "French",
        "en": "English",
        "es": "Spanish",
        "de": "German",
        "it": "Italian",
        "ja": "Japanese",
        "zh": "Chinese"
    }
    
    def __init__(self, session):
        """
        Initialize the TTS controller.
        
        Args:
            session: Active NAOqi session connected to Pepper robot
        
        Raises:
            RuntimeError: If ALTextToSpeech service cannot be accessed
        """
        self.session = session
        self.tts_service = None
        self.language = "French"  # Default language for medical context
        
        try:
            self.tts_service = self.session.service("ALTextToSpeech")
            logger.info("ALTextToSpeech service connected successfully")
            
            # Set default parameters for medical context (clear and calm voice)
            self._configure_default_voice()
            
        except Exception as e:
            logger.error(f"Failed to connect to ALTextToSpeech: {e}")
            raise RuntimeError(f"Cannot initialize TTS service: {e}")
    
    def _configure_default_voice(self) -> None:
        """
        Configure default voice parameters optimized for medical environment.
        
        Sets moderate speed and volume for clear communication with patients.
        """
        try:
            # Set moderate speech speed (100 = normal, lower = slower)
            self.tts_service.setParameter("speed", 85)
            
            # Set comfortable volume for hospital environment
            self.tts_service.setParameter("volume", 0.8)
            
            # Set language
            self.tts_service.setLanguage(self.language)
            
            logger.info(f"Voice configured: language={self.language}, speed=85, volume=0.8")
            
        except Exception as e:
            logger.warning(f"Could not configure voice parameters: {e}")
    
    def speak(self, text: str) -> bool:
        """
        Make Pepper speak the given text.
        
        Args:
            text: The text to be spoken by Pepper
        
        Returns:
            bool: True if speech was successful, False otherwise
        
        Example:
            >>> tts = PepperTTS(session)
            >>> tts.speak("Bonjour, comment vous sentez-vous aujourd'hui ?")
            True
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to speak()")
            return False
        
        if not self.tts_service:
            logger.error("TTS service not available")
            return False
        
        try:
            # Clean and prepare text
            clean_text = text.strip()
            
            logger.info(f"Speaking: '{clean_text[:50]}{'...' if len(clean_text) > 50 else ''}'")
            
            # Synchronous speech (blocking until complete)
            self.tts_service.say(clean_text)
            
            return True
            
        except Exception as e:
            logger.error(f"Speech error: {e}")
            return False
    
    def speak_async(self, text: str) -> Optional[int]:
        """
        Make Pepper speak the given text asynchronously (non-blocking).
        
        Args:
            text: The text to be spoken by Pepper
        
        Returns:
            int: Task ID if successful, None otherwise
        
        Example:
            >>> task_id = tts.speak_async("Je vérifie vos informations...")
            >>> # Robot speaks while other operations continue
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to speak_async()")
            return None
        
        if not self.tts_service:
            logger.error("TTS service not available")
            return None
        
        try:
            clean_text = text.strip()
            
            logger.info(f"Speaking (async): '{clean_text[:50]}{'...' if len(clean_text) > 50 else ''}'")
            
            # Asynchronous speech (non-blocking)
            task_id = self.tts_service.post.say(clean_text)
            
            return task_id
            
        except Exception as e:
            logger.error(f"Async speech error: {e}")
            return None
    
    def stop_speaking(self) -> bool:
        """
        Stop any ongoing speech immediately.
        
        Returns:
            bool: True if stop was successful, False otherwise
        """
        try:
            if self.tts_service:
                self.tts_service.stopAll()
                logger.info("Speech stopped")
                return True
        except Exception as e:
            logger.error(f"Error stopping speech: {e}")
        
        return False
    
    def set_language(self, language_code: str) -> bool:
        """
        Change the speech language.
        
        Args:
            language_code: Language code (e.g., "fr", "en", "es")
        
        Returns:
            bool: True if language was changed, False otherwise
        
        Example:
            >>> tts.set_language("en")
            True
            >>> tts.speak("Hello, how are you feeling today?")
        """
        if language_code not in self.SUPPORTED_LANGUAGES:
            logger.warning(f"Unsupported language: {language_code}")
            logger.info(f"Supported languages: {list(self.SUPPORTED_LANGUAGES.keys())}")
            return False
        
        try:
            language_name = self.SUPPORTED_LANGUAGES[language_code]
            self.tts_service.setLanguage(language_name)
            self.language = language_name
            
            logger.info(f"Language changed to: {language_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error changing language: {e}")
            return False
    
    def set_volume(self, volume: float) -> bool:
        """
        Set the speech volume.
        
        Args:
            volume: Volume level between 0.0 (mute) and 1.0 (max)
        
        Returns:
            bool: True if volume was set, False otherwise
        """
        if not 0.0 <= volume <= 1.0:
            logger.warning(f"Invalid volume: {volume}. Must be between 0.0 and 1.0")
            return False
        
        try:
            self.tts_service.setParameter("volume", volume)
            logger.info(f"Volume set to: {volume}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting volume: {e}")
            return False
    
    def set_speed(self, speed: int) -> bool:
        """
        Set the speech speed.
        
        Args:
            speed: Speech speed (50=slow, 100=normal, 150=fast)
        
        Returns:
            bool: True if speed was set, False otherwise
        """
        if not 50 <= speed <= 200:
            logger.warning(f"Invalid speed: {speed}. Must be between 50 and 200")
            return False
        
        try:
            self.tts_service.setParameter("speed", speed)
            logger.info(f"Speech speed set to: {speed}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting speed: {e}")
            return False


# Convenience function for simple usage
def speak(text: str, session=None) -> bool:
    """
    Simple function to make Pepper speak.
    
    This is a convenience wrapper that creates a TTS instance
    and speaks the given text.
    
    Args:
        text: Text to speak
        session: NAOqi session (will attempt to create if not provided)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if session is None:
        logger.error("No session provided. Cannot speak without connection to Pepper.")
        return False
    
    try:
        tts = PepperTTS(session)
        return tts.speak(text)
    except Exception as e:
        logger.error(f"speak() failed: {e}")
        return False
