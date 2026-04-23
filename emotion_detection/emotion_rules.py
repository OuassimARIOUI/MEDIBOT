def get_medibot_reaction(emotion):
    """
    Définit le comportement du robot selon l'émotion détectée.

    Champs :
      msg       : texte à prononcer (None = silence)
      leds      : couleur lisible pour les logs
      led_hex   : entier hex NAOqi pour ALLeds.fadeRGB("FaceLeds", hex, duration)
      gesture   : description du geste (pour les logs / animations futures)
      alert     : True si l'émotion justifie une alerte soignant
      severity  : sévérité de l'alerte ("medium" | "high")

    BUG CORRIGE 8 : ajout de led_hex (entier NAOqi) et des champs alert/severity
    pour que l'intégration puisse faire des appels NAOqi réels.
    """
    reactions = {
        "happy": {
            "msg": None,
            "leds": "VERT (Clignotant)",
            "led_hex": 0x00FF00,
            "gesture": "Animation de salut joyeux",
            "alert": False,
            "severity": None
        },
        "sad": {
            "msg": "Oh, vous semblez triste... Est-ce que je peux faire quelque chose ?",
            "leds": "ORANGE (Doux)",
            "led_hex": 0xFF9933,
            "gesture": "Inclinaison de la tête (Empathie)",
            "alert": True,
            "severity": "medium"
        },
        "angry": {
            "msg": "Je sens de la frustration. Voulez-vous que j'appelle une infirmière ?",
            "leds": "ROUGE (Fixe)",
            "led_hex": 0xFF0000,
            "gesture": "Recul léger (Sécurité)",
            "alert": True,
            "severity": "high"
        },
        "fear": {
            "msg": "Ne vous inquiétez pas, vous êtes en sécurité ici.",
            "leds": "JAUNE (Respiration)",
            "led_hex": 0xFFAA00,
            "gesture": "Bras ouverts (Rassurance)",
            "alert": True,
            "severity": "medium"
        },
        "neutral": {
            "msg": None,
            "leds": "BLANC (Standard)",
            "led_hex": 0xFFFFFF,
            "gesture": "Posture d'attente",
            "alert": False,
            "severity": None
        },
        "surprise": {
            "msg": "Oh ! Vous semblez surpris. Tout va bien ?",
            "leds": "ORANGE (Bref)",
            "led_hex": 0xFF6600,
            "gesture": "Légère inclinaison de tête",
            "alert": False,
            "severity": None
        },
        "disgust": {
            "msg": "Je vois que quelque chose vous dérange. Puis-je vous aider ?",
            "leds": "VIOLET (Fixe)",
            "led_hex": 0x6600AA,
            "gesture": "Posture neutre",
            "alert": True,
            "severity": "medium"
        }
    }
    return reactions.get(emotion, reactions["neutral"])