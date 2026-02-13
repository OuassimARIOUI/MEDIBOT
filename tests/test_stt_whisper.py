import pytest
import os
import numpy as np
from stt_whisper.whisper_listener import MediBotListener
import requests

# 1. Test de l'initialisation du modèle
def test_listener_initialization():
    listener = MediBotListener()
    assert listener.model is not None
    # Vérifie que le modèle chargé est bien 'tiny' comme demandé pour la latence
    assert listener.model.name == "tiny"

# 2. Test de la fonction de transcription
def test_transcription_logic(tmp_path):
    listener = MediBotListener()
    
    # Création d'un fichier audio vide factice pour tester si la fonction tourne
    d = tmp_path / "sub"
    d.mkdir()
    fake_audio = d / "test.wav"
    
    # On vérifie juste que l'appel ne crash pas (Whisper gère le bruit/silence)
    # Pour un vrai test unitaire, on testerait un fichier avec une voix connue
    try:
        result = listener.transcribe(str(fake_audio))
        assert isinstance(result, str)
    except Exception:
        pytest.fail("La transcription a planté sur un fichier vide")

# 3. Test de la langue forcée (Sprint 2 goal)
def test_language_enforcement():
    listener = MediBotListener()
    # On vérifie la logique interne si tu as modifié whisper_listener.py
    # pour forcer 'fr'
    pass

def test_rasa_response_greet():
    """Vérifie que Rasa répond correctement à une salutation."""
    url = "http://localhost:5005/webhooks/rest/webhook"
    payload = {"sender": "test_user", "message": "Bonjour"}
    
    response = requests.post(url, json=payload)
    responses = response.json()
    
    assert response.status_code == 200
    assert len(responses) > 0
    # Vérifie que la réponse correspond à utter_greet dans domain.yml
    assert "MediBot" in responses[0]["text"]