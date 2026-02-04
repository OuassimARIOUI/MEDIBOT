"""
Unit Tests for Emotion Policy Module
=====================================

Tests the emotional decision logic for MediBot.
"""

import unittest
import sys
from pathlib import Path

# Add rasa_bot/actions to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "rasa_bot" / "actions"))

from emotion_policy import (
    handle_emotion,
    assess_severity,
    should_escalate,
    get_reassurance_message,
    POSITIVE_EMOTIONS,
    MILD_NEGATIVE_EMOTIONS,
    SEVERE_NEGATIVE_EMOTIONS
)


class TestHandleEmotion(unittest.TestCase):
    """Test the main handle_emotion function."""
    
    def test_positive_emotion_good(self):
        """Test handling of 'good' emotion."""
        result = handle_emotion("good")
        self.assertIsInstance(result, dict)
        self.assertIn("response", result)
        self.assertIn("suggest_nurse", result)
        self.assertIn("trigger_alert", result)
        self.assertFalse(result["suggest_nurse"])
        self.assertFalse(result["trigger_alert"])
    
    def test_positive_emotion_fine(self):
        """Test handling of 'fine' emotion."""
        result = handle_emotion("fine")
        self.assertFalse(result["suggest_nurse"])
        self.assertFalse(result["trigger_alert"])
        self.assertIsInstance(result["response"], str)
    
    def test_positive_emotion_case_insensitive(self):
        """Test that emotion detection is case-insensitive."""
        result1 = handle_emotion("GOOD")
        result2 = handle_emotion("Good")
        result3 = handle_emotion("good")
        self.assertEqual(result1["suggest_nurse"], result2["suggest_nurse"])
        self.assertEqual(result2["suggest_nurse"], result3["suggest_nurse"])
    
    def test_mild_negative_emotion_anxious(self):
        """Test handling of 'anxious' emotion."""
        result = handle_emotion("anxious")
        self.assertTrue(result["suggest_nurse"])
        self.assertFalse(result["trigger_alert"])
        self.assertIsInstance(result["response"], str)
    
    def test_mild_negative_emotion_worried(self):
        """Test handling of 'worried' emotion."""
        result = handle_emotion("worried")
        self.assertTrue(result["suggest_nurse"])
        self.assertFalse(result["trigger_alert"])
    
    def test_severe_negative_emotion_distressed(self):
        """Test handling of 'distressed' emotion."""
        result = handle_emotion("distressed")
        self.assertTrue(result["suggest_nurse"])
        self.assertTrue(result["trigger_alert"])
        self.assertIsInstance(result["response"], str)
    
    def test_severe_negative_emotion_panic(self):
        """Test handling of 'panic' emotion."""
        result = handle_emotion("panic")
        self.assertTrue(result["suggest_nurse"])
        self.assertTrue(result["trigger_alert"])
    
    def test_severe_negative_emotion_bad(self):
        """Test handling of 'bad' emotion."""
        result = handle_emotion("bad")
        self.assertTrue(result["suggest_nurse"])
        self.assertTrue(result["trigger_alert"])
    
    def test_unknown_emotion(self):
        """Test handling of unknown emotion (default behavior)."""
        result = handle_emotion("neutral")
        self.assertTrue(result["suggest_nurse"])
        self.assertFalse(result["trigger_alert"])
        self.assertIsInstance(result["response"], str)
    
    def test_emotion_with_whitespace(self):
        """Test that emotions with leading/trailing whitespace are handled."""
        result = handle_emotion("  anxious  ")
        self.assertTrue(result["suggest_nurse"])
        self.assertFalse(result["trigger_alert"])


class TestAssessSeverity(unittest.TestCase):
    """Test the assess_severity function."""
    
    def test_low_severity_emotions(self):
        """Test that positive emotions return 'low' severity."""
        for emotion in ["good", "fine", "ok", "great"]:
            with self.subTest(emotion=emotion):
                severity = assess_severity(emotion)
                self.assertEqual(severity, "low")
    
    def test_medium_severity_emotions(self):
        """Test that mild negative emotions return 'medium' severity."""
        for emotion in ["anxious", "worried", "uncomfortable"]:
            with self.subTest(emotion=emotion):
                severity = assess_severity(emotion)
                self.assertEqual(severity, "medium")
    
    def test_high_severity_emotions(self):
        """Test that severe negative emotions return 'high' severity."""
        for emotion in ["distressed", "panic", "severe_pain", "emergency"]:
            with self.subTest(emotion=emotion):
                severity = assess_severity(emotion)
                self.assertEqual(severity, "high")
    
    def test_unknown_emotion_default_medium(self):
        """Test that unknown emotions default to 'medium' severity."""
        severity = assess_severity("unknown_emotion")
        self.assertEqual(severity, "medium")
    
    def test_severity_case_insensitive(self):
        """Test that severity assessment is case-insensitive."""
        severity1 = assess_severity("PANIC")
        severity2 = assess_severity("panic")
        self.assertEqual(severity1, severity2)
        self.assertEqual(severity1, "high")


class TestShouldEscalate(unittest.TestCase):
    """Test the should_escalate function."""
    
    def test_escalate_high_severity(self):
        """Test that high severity emotions always escalate."""
        self.assertTrue(should_escalate("panic"))
        self.assertTrue(should_escalate("distressed"))
        self.assertTrue(should_escalate("emergency"))
    
    def test_no_escalate_medium_severity(self):
        """Test that medium severity emotions don't escalate by default."""
        self.assertFalse(should_escalate("anxious"))
        self.assertFalse(should_escalate("worried"))
    
    def test_no_escalate_low_severity(self):
        """Test that low severity emotions don't escalate."""
        self.assertFalse(should_escalate("good"))
        self.assertFalse(should_escalate("fine"))
    
    def test_escalate_with_context(self):
        """Test escalation with context (future feature)."""
        # Currently context doesn't change behavior, but function accepts it
        result = should_escalate("anxious", context={"repeated": True})
        self.assertFalse(result)  # Current behavior
    
    def test_escalate_unknown_emotion(self):
        """Test that unknown emotions don't escalate by default."""
        self.assertFalse(should_escalate("neutral"))


class TestGetReassuranceMessage(unittest.TestCase):
    """Test the get_reassurance_message function."""
    
    def test_message_for_known_emotions(self):
        """Test that known emotions return appropriate messages."""
        emotions = ["good", "fine", "anxious", "worried", "distressed", "panic"]
        for emotion in emotions:
            with self.subTest(emotion=emotion):
                message = get_reassurance_message(emotion)
                self.assertIsInstance(message, str)
                self.assertGreater(len(message), 0)
    
    def test_message_for_unknown_emotion(self):
        """Test that unknown emotions return a default message."""
        message = get_reassurance_message("unknown")
        self.assertIsInstance(message, str)
        self.assertGreater(len(message), 0)
    
    def test_message_case_insensitive(self):
        """Test that message retrieval is case-insensitive."""
        message1 = get_reassurance_message("GOOD")
        message2 = get_reassurance_message("good")
        self.assertEqual(message1, message2)
    
    def test_messages_in_french(self):
        """Test that all messages are in French (contain French characters)."""
        emotions = ["good", "anxious", "panic"]
        for emotion in emotions:
            message = get_reassurance_message(emotion)
            # Check for common French words or patterns
            self.assertTrue(
                any(word in message.lower() for word in ["je", "vous", "pour", "est", "suis", "là"]),
                f"Message for '{emotion}' should be in French"
            )


class TestEmotionConstants(unittest.TestCase):
    """Test the emotion category constants."""
    
    def test_positive_emotions_constant(self):
        """Test that POSITIVE_EMOTIONS constant is defined and valid."""
        self.assertIsInstance(POSITIVE_EMOTIONS, list)
        self.assertGreater(len(POSITIVE_EMOTIONS), 0)
        self.assertIn("good", POSITIVE_EMOTIONS)
        self.assertIn("fine", POSITIVE_EMOTIONS)
    
    def test_mild_negative_emotions_constant(self):
        """Test that MILD_NEGATIVE_EMOTIONS constant is defined and valid."""
        self.assertIsInstance(MILD_NEGATIVE_EMOTIONS, list)
        self.assertGreater(len(MILD_NEGATIVE_EMOTIONS), 0)
        self.assertIn("anxious", MILD_NEGATIVE_EMOTIONS)
        self.assertIn("worried", MILD_NEGATIVE_EMOTIONS)
    
    def test_severe_negative_emotions_constant(self):
        """Test that SEVERE_NEGATIVE_EMOTIONS constant is defined and valid."""
        self.assertIsInstance(SEVERE_NEGATIVE_EMOTIONS, list)
        self.assertGreater(len(SEVERE_NEGATIVE_EMOTIONS), 0)
        self.assertIn("distressed", SEVERE_NEGATIVE_EMOTIONS)
        self.assertIn("panic", SEVERE_NEGATIVE_EMOTIONS)
    
    def test_no_overlap_between_categories(self):
        """Test that emotion categories don't overlap."""
        positive_set = set(POSITIVE_EMOTIONS)
        mild_set = set(MILD_NEGATIVE_EMOTIONS)
        severe_set = set(SEVERE_NEGATIVE_EMOTIONS)
        
        self.assertEqual(len(positive_set & mild_set), 0, "Positive and mild negative should not overlap")
        self.assertEqual(len(positive_set & severe_set), 0, "Positive and severe negative should not overlap")
        self.assertEqual(len(mild_set & severe_set), 0, "Mild and severe negative should not overlap")


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for realistic scenarios."""
    
    def test_patient_feeling_good_workflow(self):
        """Test complete workflow for a patient feeling good."""
        emotion = "good"
        decision = handle_emotion(emotion)
        severity = assess_severity(emotion)
        escalate = should_escalate(emotion)
        message = get_reassurance_message(emotion)
        
        self.assertEqual(severity, "low")
        self.assertFalse(escalate)
        self.assertFalse(decision["trigger_alert"])
        self.assertFalse(decision["suggest_nurse"])
        self.assertIsInstance(message, str)
    
    def test_patient_anxious_workflow(self):
        """Test complete workflow for an anxious patient."""
        emotion = "anxious"
        decision = handle_emotion(emotion)
        severity = assess_severity(emotion)
        escalate = should_escalate(emotion)
        message = get_reassurance_message(emotion)
        
        self.assertEqual(severity, "medium")
        self.assertFalse(escalate)
        self.assertFalse(decision["trigger_alert"])
        self.assertTrue(decision["suggest_nurse"])
        self.assertIsInstance(message, str)
    
    def test_patient_in_panic_workflow(self):
        """Test complete workflow for a patient in panic."""
        emotion = "panic"
        decision = handle_emotion(emotion)
        severity = assess_severity(emotion)
        escalate = should_escalate(emotion)
        message = get_reassurance_message(emotion)
        
        self.assertEqual(severity, "high")
        self.assertTrue(escalate)
        self.assertTrue(decision["trigger_alert"])
        self.assertTrue(decision["suggest_nurse"])
        self.assertIsInstance(message, str)


def run_tests():
    """Run all tests and display results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestHandleEmotion))
    suite.addTests(loader.loadTestsFromTestCase(TestAssessSeverity))
    suite.addTests(loader.loadTestsFromTestCase(TestShouldEscalate))
    suite.addTests(loader.loadTestsFromTestCase(TestGetReassuranceMessage))
    suite.addTests(loader.loadTestsFromTestCase(TestEmotionConstants))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
