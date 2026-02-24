def get_behavior_for_emotion(emotion):
    rules = {
        "happy": {"leds": "green", "gesture": "happy_wave", "message": "Je suis ravi de vous voir de bonne humeur !"},
        "sad": {"leds": "blue", "gesture": "comforting_hand", "message": "Je sens que vous êtes triste. Voulez-vous parler ou que j'appelle quelqu'un ?"},
        "fear": {"leds": "yellow", "gesture": "reassurance", "message": "Ne vous inquiétez pas, tout va bien se passer. Je suis là."},
        "angry": {"leds": "red", "gesture": "calm_down", "message": "Je comprends votre frustration. Restons calmes ensemble."},
        "neutral": {"leds": "white", "gesture": "standard", "message": None}
    }
    return rules.get(emotion, rules["neutral"])