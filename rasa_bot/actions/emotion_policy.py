
from typing import Dict, Any


def handle_emotion(emotion: str) -> Dict[str, Any]:
    """
    Process patient emotion and return a structured decision.
    
    Args:
        emotion (str): The detected emotion state. Expected values:
                      - "good" / "fine" / "ok"
                      - "anxious" / "worried" / "uncomfortable"
                      - "distressed" / "panic" / "severe_pain"
    
    Returns:
        dict: A structured decision containing:
            - response (str): Message to send to the patient
            - suggest_nurse (bool): Whether to propose calling a nurse
            - trigger_alert (bool): Whether to escalate to an emergency alert
    
    Examples:
        >>> handle_emotion("good")
        {'response': '...', 'suggest_nurse': False, 'trigger_alert': False}
        
        >>> handle_emotion("anxious")
        {'response': '...', 'suggest_nurse': True, 'trigger_alert': False}
        
        >>> handle_emotion("distressed")
        {'response': '...', 'suggest_nurse': True, 'trigger_alert': True}
    """
    emotion_lower = emotion.lower().strip()
    
    # Positive emotions: Patient is fine
    if emotion_lower in ["good", "fine", "ok", "great", "well", "better"]:
        return {
            "response": "Je suis content(e) de l'apprendre ! N'hésitez pas à me contacter si vous avez besoin de quoi que ce soit.",
            "suggest_nurse": False,
            "trigger_alert": False
        }
    
    # Mild negative emotions: Discomfort, anxiety
    elif emotion_lower in ["anxious", "worried", "uncomfortable", "nervous", "stressed", "uneasy"]:
        return {
            "response": "Je comprends votre inquiétude. Voulez-vous que j'appelle une infirmière pour vous ?",
            "suggest_nurse": True,
            "trigger_alert": False
        }
    
    # Severe negative emotions: Distress, panic, emergency
    elif emotion_lower in ["distressed", "panic", "severe_pain", "emergency", "critical", "help", "bad", "terrible"]:
        return {
            "response": "Je comprends que vous ne vous sentez pas bien. Je vais immédiatement alerter l'équipe médicale.",
            "suggest_nurse": True,
            "trigger_alert": True
        }
    
    # Unknown/Neutral emotion: Default cautious response
    else:
        return {
            "response": "Je vois. Comment puis-je vous aider ? Souhaitez-vous parler à une infirmière ?",
            "suggest_nurse": True,
            "trigger_alert": False
        }


def assess_severity(emotion: str) -> str:
    """
    Assess the severity level of a patient's emotional state.
    
    Args:
        emotion (str): The detected emotion state
    
    Returns:
        str: Severity level - "low", "medium", or "high"
    
    Examples:
        >>> assess_severity("good")
        'low'
        
        >>> assess_severity("anxious")
        'medium'
        
        >>> assess_severity("panic")
        'high'
    """
    emotion_lower = emotion.lower().strip()
    
    if emotion_lower in ["good", "fine", "ok", "great", "well", "better"]:
        return "low"
    
    elif emotion_lower in ["anxious", "worried", "uncomfortable", "nervous", "stressed", "uneasy"]:
        return "medium"
    
    elif emotion_lower in ["distressed", "panic", "severe_pain", "emergency", "critical", "help", "bad", "terrible"]:
        return "high"
    
    else:
        # Default to medium for unknown states (cautious approach)
        return "medium"


def should_escalate(emotion: str, context: Dict[str, Any] = None) -> bool:
    """
    Determine if the situation requires escalation to medical staff.
    
    Args:
        emotion (str): The detected emotion state
        context (dict, optional): Additional contextual information
                                 (e.g., patient history, time of day)
    
    Returns:
        bool: True if escalation is needed, False otherwise
    
    Note:
        This function is designed to be extensible for future sprints
        where context-aware decisions can be implemented.
    """
    severity = assess_severity(emotion)
    
    # High severity always escalates
    if severity == "high":
        return True
    
    # Medium severity: check context (future enhancement)
    if severity == "medium":
        if context:
            # Future: Add contextual rules here
            # e.g., repeated complaints, time since last check
            pass
        return False
    
    # Low severity: no escalation needed
    return False


def get_reassurance_message(emotion: str) -> str:
    """
    Get an appropriate reassurance message based on emotion.
    
    Args:
        emotion (str): The detected emotion state
    
    Returns:
        str: A reassuring message tailored to the emotion
    """
    emotion_lower = emotion.lower().strip()
    
    reassurance_map = {
        "good": "C'est merveilleux ! Continuez ainsi.",
        "fine": "Parfait ! Je suis là si vous avez besoin.",
        "anxious": "Ne vous inquiétez pas, l'équipe médicale est là pour vous.",
        "worried": "Tout va bien se passer. Vous êtes entre de bonnes mains.",
        "uncomfortable": "Je comprends. Nous allons trouver une solution ensemble.",
        "distressed": "Restez calme, l'aide arrive immédiatement.",
        "panic": "Respirez profondément. L'équipe médicale est en route."
    }
    
    return reassurance_map.get(
        emotion_lower,
        "Je suis là pour vous aider. N'hésitez pas à me parler."
    )


# Constants for emotion categories (useful for future extensions)
POSITIVE_EMOTIONS = ["good", "fine", "ok", "great", "well", "better"]
MILD_NEGATIVE_EMOTIONS = ["anxious", "worried", "uncomfortable", "nervous", "stressed", "uneasy"]
SEVERE_NEGATIVE_EMOTIONS = ["distressed", "panic", "severe_pain", "emergency", "critical", "help", "bad", "terrible"]
