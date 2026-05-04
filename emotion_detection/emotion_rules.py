def get_medibot_reaction(emotion):
    """
    Définit le comportement du robot selon l'émotion détectée.

    Code couleur LEDs (FaceLeds Pepper) :
      - VERT   : patient en bonne forme (happy)
      - ORANGE : émotion négative (sad / angry / fear) → alerte soignant
      - ROUGE  : RÉSERVÉ aux urgences vitales (étouffement, arrêt respiratoire)
                 — voir async_vision_pipeline._handle_emergency
      - BLANC  : neutre / standard

    Champs :
      msg       : texte à prononcer (None = silence)
      leds      : couleur lisible pour les logs
      led_hex   : entier hex NAOqi pour ALLeds.fadeRGB("FaceLeds", hex, duration)
      gesture   : description du geste (pour les logs / animations futures)
      alert     : True si l'émotion justifie une alerte soignant
      severity  : sévérité de l'alerte ("medium" | "high")
    """
    reactions = {
        "happy": {
            "msg": "Je vois que vous allez bien aujourd'hui !",
            "leds": "VERT",
            "led_hex": 0x00FF00,
            "gesture": "Animation de salut joyeux",
            "alert": False,
            "severity": None
        },
        "sad": {
            "msg": "Oh, vous semblez triste... Est-ce que je peux faire quelque chose ?",
            "leds": "ORANGE",
            "led_hex": 0xFF9933,
            "gesture": "Inclinaison de la tête (Empathie)",
            "alert": True,
            "severity": "medium"
        },
        "angry": {
            # ROUGE est réservé aux urgences vitales (étouffement) → ORANGE pour la colère
            "msg": "Je sens de la frustration. Voulez-vous que j'appelle une infirmière ?",
            "leds": "ORANGE",
            "led_hex": 0xFF6600,
            "gesture": "Recul léger (Sécurité)",
            "alert": True,
            "severity": "high"
        },
        "fear": {
            "msg": "Ne vous inquiétez pas, vous êtes en sécurité ici.",
            "leds": "ORANGE",
            "led_hex": 0xFF9933,
            "gesture": "Bras ouverts (Rassurance)",
            "alert": True,
            "severity": "medium"
        },
        "neutral": {
            "msg": None,
            "leds": "BLANC",
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
            # Aligné sur la palette demandée (orange pour émotions négatives)
            "msg": "Je vois que quelque chose vous dérange. Puis-je vous aider ?",
            "leds": "ORANGE",
            "led_hex": 0xFF9933,
            "gesture": "Posture neutre",
            "alert": False,
            "severity": None
        }
    }
    return reactions.get(emotion, reactions["neutral"])