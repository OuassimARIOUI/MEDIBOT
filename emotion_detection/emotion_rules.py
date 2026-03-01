def get_medibot_reaction(emotion):
    """Définit le comportement du robot selon l'émotion détectée."""
    reactions = {
        "happy": {
            "msg": "Je vois que vous allez bien aujourd'hui !",
            "leds": "VERT (Clignotant)",
            "gesture": "Animation de salut joyeux"
        },
        "sad": {
            "msg": "Oh, vous semblez triste... Est-ce que je peux faire quelque chose ?",
            "leds": "BLEU (Doux)",
            "gesture": "Inclinaison de la tête (Empathie)"
        },
        "angry": {
            "msg": "Je sens de la frustration. Voulez-vous que j'appelle une infirmière ?",
            "leds": "ROUGE (Fixe)",
            "gesture": "Recul léger (Sécurité)"
        },
        "fear": {
            "msg": "Ne vous inquiétez pas, vous êtes en sécurité ici.",
            "leds": "JAUNE (Respiration)",
            "gesture": "Bras ouverts (Rassurance)"
        },
        "neutral": {
            "msg": None,
            "leds": "BLANC (Standard)",
            "gesture": "Posture d'attente"
        }
    }
    return reactions.get(emotion, reactions["neutral"])