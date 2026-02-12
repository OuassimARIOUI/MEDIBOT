import numpy as np

def normalize_audio(audio_data):
    """Augmente le volume si le signal est trop faible."""
    max_val = np.max(np.abs(audio_data))
    if max_val > 0:
        return audio_data / max_val
    return audio_data

def is_silent(audio_data, threshold=0.01):
    """Détecte si l'utilisateur parle ou non."""
    return np.max(np.abs(audio_data)) < threshold

def clean_audio(audio_data):
    # Normalisation du volume pour éviter les distorsions
    return audio_data / np.max(np.abs(audio_data)) if np.max(np.abs(audio_data)) > 0 else audio_data