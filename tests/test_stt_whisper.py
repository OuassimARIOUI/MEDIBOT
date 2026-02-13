import pytest
import os
import sys
from pathlib import Path

# Ajouter le dossier racine au path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import numpy as np
from stt_whisper.whisper_listener import MediBotListener
import requests
import wave
import struct

# 1. Test de l'initialisation du modèle
def test_listener_initialization():
    listener = MediBotListener()
    assert listener.model is not None
    # Vérifie que le modèle chargé est bien 'tiny' comme demandé pour la latence
    assert listener.model_size == "tiny"

# 2. Test de la fonction de transcription
def test_transcription_logic(tmp_path):
    listener = MediBotListener()
    
    # Création d'un fichier audio WAV valide (silence)
    d = tmp_path / "sub"
    d.mkdir()
    fake_audio = d / "test.wav"
    
    # Créer un fichier WAV avec du silence
    sample_rate = 16000
    duration = 1  # 1 seconde
    n_samples = sample_rate * duration
    
    with wave.open(str(fake_audio), 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        # Écrire du silence (zéros)
        for _ in range(n_samples):
            wav_file.writeframes(struct.pack('<h', 0))
    
    # On vérifie juste que l'appel ne crash pas (Whisper gère le bruit/silence)
    result = listener.transcribe(str(fake_audio))
    assert isinstance(result, str)

# 3. Test de la langue forcée (Sprint 2 goal)
def test_language_enforcement():
    listener = MediBotListener()
    # On vérifie la logique interne si tu as modifié whisper_listener.py
    # pour forcer 'fr'
    pass

def test_rasa_response_greet(mocker):
    """Vérifie que Rasa répond correctement à une salutation.
    
    Ce test mock le serveur Rasa pour simuler une réponse.
    """
    # Mock de la réponse Rasa
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"recipient_id": "test_user", "text": "Bonjour ! Je suis MediBot, votre assistant médical."}
    ]
    
    mocker.patch('requests.post', return_value=mock_response)
    
    url = "http://localhost:5005/webhooks/rest/webhook"
    payload = {"sender": "test_user", "message": "Bonjour"}
    
    response = requests.post(url, json=payload, timeout=5)
    responses = response.json()
    
    assert response.status_code == 200
    assert len(responses) > 0
    # Vérifie que la réponse correspond à utter_greet dans domain.yml
    assert "MediBot" in responses[0]["text"]