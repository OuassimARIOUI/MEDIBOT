def test_emotion_logic():
    from emotion_detection.emotion_rules import get_medibot_reaction
    behavior = get_medibot_reaction("sad")
    assert "BLEU" in behavior["leds"]