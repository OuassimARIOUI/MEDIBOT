def test_emotion_logic():
    from emotion_detection.emotion_rules import get_behavior_for_emotion
    behavior = get_behavior_for_emotion("sad")
    assert behavior["leds"] == "blue" # MediBot doit devenir bleu s'il détecte de la tristesse