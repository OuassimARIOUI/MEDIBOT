#!/usr/bin/env python3
"""
generate_melodies.py — Génère des fichiers WAV instrumentaux pour MediBot.

Chaque chanson est une vraie mélodie jouée avec des ondes sinusoïdales
(piano-like), avec harmoniques pour un son plus riche.

Usage :
    python scripts/generate_melodies.py

Génère les fichiers dans rasa_bot/actions/songs/
"""

import os
import numpy as np
from scipy.io.wavfile import write

# Fréquence d'échantillonnage
SAMPLE_RATE = 44100

# Dossier de sortie
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "rasa_bot", "actions", "songs"
)


# =====================================================================
# Utilitaires audio
# =====================================================================

def note_freq(name: str) -> float:
    """Retourne la fréquence d'une note (ex: 'C4', 'A#3', 'Bb5')."""
    note_map = {
        'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
        'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
        'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11,
    }
    # Parse note name and octave
    if len(name) == 2:
        n, octave = name[0], int(name[1])
    elif len(name) == 3:
        n, octave = name[:2], int(name[2])
    else:
        raise ValueError(f"Invalid note: {name}")
    
    semitone = note_map[n] + (octave + 1) * 12
    # A4 = 440 Hz = semitone 69
    return 440.0 * (2.0 ** ((semitone - 69) / 12.0))


def synth_note(freq: float, duration: float, volume: float = 0.5,
               attack: float = 0.02, release: float = 0.08) -> np.ndarray:
    """
    Synthétise une note avec harmoniques et enveloppe ADSR simplifiée.
    Donne un son de type piano/celesta — agréable pour un hôpital.
    """
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    
    # Fondamentale + harmoniques (son riche mais doux)
    wave = (
        1.0   * np.sin(2 * np.pi * freq * t) +       # fondamentale
        0.4   * np.sin(2 * np.pi * freq * 2 * t) +    # octave
        0.15  * np.sin(2 * np.pi * freq * 3 * t) +    # quinte
        0.08  * np.sin(2 * np.pi * freq * 4 * t) +    # double octave
        0.03  * np.sin(2 * np.pi * freq * 5 * t)      # tierce
    )
    
    # Normaliser
    wave = wave / np.max(np.abs(wave) + 1e-9)
    
    # Enveloppe ADSR
    envelope = np.ones_like(t)
    attack_samples = int(SAMPLE_RATE * attack)
    release_samples = int(SAMPLE_RATE * release)
    
    if attack_samples > 0:
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
    if release_samples > 0 and release_samples < len(t):
        envelope[-release_samples:] = np.linspace(1, 0, release_samples)
    
    # Decay exponentiel naturel (comme un piano)
    decay = np.exp(-t * 2.5 / duration)
    
    return wave * envelope * decay * volume


def rest(duration: float) -> np.ndarray:
    """Silence (pause)."""
    return np.zeros(int(SAMPLE_RATE * duration))


def build_melody(notes_sequence: list, default_duration: float = 0.4,
                 volume: float = 0.5) -> np.ndarray:
    """
    Construit une mélodie à partir d'une séquence de (note, durée).
    - note = "C4" ou None pour silence
    - durée en secondes
    """
    audio = np.array([], dtype=np.float64)
    for item in notes_sequence:
        if isinstance(item, tuple):
            note, dur = item
        else:
            note, dur = item, default_duration
        
        if note is None or note == "":
            audio = np.concatenate([audio, rest(dur)])
        else:
            freq = note_freq(note)
            audio = np.concatenate([audio, synth_note(freq, dur, volume)])
    
    return audio


def add_reverb(audio: np.ndarray, delay: float = 0.05, decay: float = 0.3) -> np.ndarray:
    """Ajoute un léger écho/reverb pour un son plus spatial."""
    delay_samples = int(SAMPLE_RATE * delay)
    result = audio.copy()
    if delay_samples < len(audio):
        result[delay_samples:] += audio[:-delay_samples] * decay
    return result


def normalize_and_convert(audio: np.ndarray) -> np.ndarray:
    """Normalise et convertit en int16 pour WAV."""
    audio = audio / (np.max(np.abs(audio)) + 1e-9)
    audio = add_reverb(audio)
    audio = audio / (np.max(np.abs(audio)) + 1e-9)
    return (audio * 32000).astype(np.int16)


def save_wav(filename: str, audio: np.ndarray):
    """Sauvegarde en WAV 16-bit mono."""
    path = os.path.join(OUTPUT_DIR, filename)
    data = normalize_and_convert(audio)
    write(path, SAMPLE_RATE, data)
    duration = len(audio) / SAMPLE_RATE
    print(f"  ✅ {filename} ({duration:.1f}s)")


# =====================================================================
# Mélodies des chansons
# =====================================================================

def generate_au_clair_de_la_lune():
    """Au Clair de la Lune — mélodie instrumentale douce."""
    # Do Do Do Ré Mi- Ré- Do Mi Ré Ré Do---
    # Tempo lent et doux pour berceuse
    d = 0.5  # durée d'une noire
    melody = [
        # Phrase 1: "Au clair de la lune"
        ("C4", d), ("C4", d), ("C4", d), ("D4", d),
        ("E4", d*2), ("D4", d*2),
        # Phrase 2: "mon ami Pierrot"
        ("C4", d), ("E4", d), ("D4", d), ("D4", d),
        ("C4", d*3), (None, d),
        # Phrase 3: "Prête-moi ta plume"
        ("C4", d), ("C4", d), ("C4", d), ("D4", d),
        ("E4", d*2), ("D4", d*2),
        # Phrase 4: "pour écrire un mot"
        ("C4", d), ("E4", d), ("D4", d), ("D4", d),
        ("C4", d*3), (None, d),
        # Couplet 2 - répétition douce
        ("D4", d), ("D4", d), ("D4", d), ("D4", d),
        ("A3", d*2), ("A3", d*2),
        ("D4", d), ("C4", d), ("B3", d), ("A3", d),
        ("G3", d*3), (None, d),
        # Fin douce
        ("C4", d), ("C4", d), ("C4", d), ("D4", d),
        ("E4", d*2), ("D4", d*2),
        ("C4", d), ("E4", d), ("D4", d), ("D4", d),
        ("C4", d*4),
    ]
    return build_melody(melody, volume=0.45)


def generate_frere_jacques():
    """Frère Jacques — mélodie joyeuse et rythmée."""
    d = 0.35  # noire (tempo modéré-rapide)
    melody = [
        # "Frère Jacques" x2
        ("C4", d), ("D4", d), ("E4", d), ("C4", d),
        ("C4", d), ("D4", d), ("E4", d), ("C4", d),
        # "Dormez-vous?" x2
        ("E4", d), ("F4", d), ("G4", d*2),
        ("E4", d), ("F4", d), ("G4", d*2),
        # "Sonnez les matines" x2
        ("G4", d*0.5), ("A4", d*0.5), ("G4", d*0.5), ("F4", d*0.5), ("E4", d), ("C4", d),
        ("G4", d*0.5), ("A4", d*0.5), ("G4", d*0.5), ("F4", d*0.5), ("E4", d), ("C4", d),
        # "Din din don" x2
        ("C4", d), ("G3", d), ("C4", d*2),
        ("C4", d), ("G3", d), ("C4", d*2),
        # Reprise complète (canon-style, une octave plus haut pour variété)
        (None, d),
        ("C5", d), ("D5", d), ("E5", d), ("C5", d),
        ("C5", d), ("D5", d), ("E5", d), ("C5", d),
        ("E5", d), ("F5", d), ("G5", d*2),
        ("E5", d), ("F5", d), ("G5", d*2),
        ("C5", d), ("G4", d), ("C5", d*3),
    ]
    return build_melody(melody, volume=0.5)


def generate_la_vie_en_rose():
    """La Vie en Rose — mélodie romantique."""
    d = 0.45  # noire (tempo modéré, romantique)
    melody = [
        # Intro instrumentale
        ("C4", d*2), ("E4", d), ("G4", d),
        ("A4", d*2), ("G4", d*2),
        (None, d),
        # "Des yeux qui font baisser les miens"
        ("G4", d), ("G4", d), ("A4", d), ("G4", d),
        ("F4", d), ("E4", d), ("D4", d), ("E4", d),
        ("C4", d*3), (None, d),
        # "Un rire qui se perd sur sa bouche"
        ("G4", d), ("G4", d), ("A4", d), ("G4", d),
        ("F4", d), ("E4", d), ("F4", d), ("D4", d),
        ("E4", d*3), (None, d),
        # "Quand il me prend dans ses bras"
        ("C4", d), ("E4", d), ("G4", d), ("C5", d),
        ("B4", d*2), ("A4", d*2),
        # "Il me parle tout bas"
        ("A4", d), ("G4", d), ("F4", d), ("E4", d),
        ("F4", d*2), ("E4", d*2),
        # "Je vois la vie en rose"
        ("E4", d), ("D4", d), ("E4", d), ("F4", d),
        ("G4", d*2), ("C4", d*2),
        ("E4", d), ("D4", d), ("C4", d*3),
        (None, d),
        # Outro - reprise douce
        ("C4", d*2), ("E4", d), ("G4", d),
        ("A4", d*2), ("G4", d*2),
        ("E4", d), ("D4", d), ("C4", d*4),
    ]
    return build_melody(melody, volume=0.45)


def generate_douce_france():
    """Douce France — mélodie nostalgique."""
    d = 0.45  # noire
    melody = [
        # "Douce France"
        ("E4", d*2), ("D4", d), ("C4", d),
        ("E4", d*3), (None, d),
        # "Cher pays de mon enfance"
        ("G4", d), ("F4", d), ("E4", d), ("D4", d),
        ("C4", d), ("D4", d), ("E4", d*2),
        (None, d*0.5),
        # "Bercée de tendre insouciance"
        ("A4", d), ("G4", d), ("F4", d), ("E4", d),
        ("D4", d), ("E4", d), ("F4", d), ("D4", d),
        ("E4", d*3), (None, d),
        # "Je t'ai gardée dans mon cœur"
        ("C4", d), ("E4", d), ("G4", d), ("A4", d),
        ("G4", d*2), ("E4", d*2),
        ("D4", d), ("C4", d*3),
        (None, d*2),
        # Reprise instrumentale douce
        ("E4", d*2), ("D4", d), ("C4", d),
        ("E4", d*2), ("G4", d*2),
        ("A4", d), ("G4", d), ("F4", d), ("E4", d),
        ("D4", d), ("C4", d*4),
    ]
    return build_melody(melody, volume=0.45)


def generate_promenons_nous():
    """Promenons-nous dans les bois — mélodie vive et enjouée."""
    d = 0.3  # noire rapide
    melody = [
        # "Promenons-nous dans les bois"
        ("G4", d), ("G4", d), ("A4", d), ("B4", d),
        ("C5", d), ("B4", d), ("A4", d), ("G4", d),
        # "Pendant que le loup n'y est pas"
        ("A4", d), ("A4", d), ("B4", d), ("C5", d),
        ("D5", d*2), ("B4", d*2),
        # "Si le loup y était"
        ("G4", d), ("A4", d), ("B4", d), ("C5", d),
        ("D5", d*2), (None, d),
        # "Il nous mangerait"
        ("E5", d), ("D5", d), ("C5", d), ("B4", d),
        ("C5", d*3), (None, d),
        # "Mais comme il n'y est pas"
        ("C5", d), ("B4", d), ("A4", d), ("G4", d),
        ("A4", d), ("B4", d), ("G4", d*2),
        # "Il nous mangera pas!"
        ("G4", d), ("A4", d), ("B4", d), ("C5", d),
        ("D5", d), ("C5", d), ("B4", d), ("A4", d),
        ("G4", d*3),
        (None, d),
        # Reprise joyeuse (octave haute)
        ("G4", d), ("G4", d), ("A4", d), ("B4", d),
        ("C5", d), ("D5", d), ("E5", d), ("D5", d),
        ("C5", d), ("B4", d), ("A4", d), ("G4", d),
        ("G4", d*4),
    ]
    return build_melody(melody, volume=0.5)


# =====================================================================
# Main
# =====================================================================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n🎵 Génération des mélodies instrumentales...")
    print(f"   Dossier : {os.path.abspath(OUTPUT_DIR)}\n")

    generators = {
        "au_clair_de_la_lune.wav": generate_au_clair_de_la_lune,
        "frere_jacques.wav": generate_frere_jacques,
        "la_vie_en_rose.wav": generate_la_vie_en_rose,
        "douce_france.wav": generate_douce_france,
        "promenons_nous.wav": generate_promenons_nous,
    }

    for filename, gen_fn in generators.items():
        audio = gen_fn()
        save_wav(filename, audio)

    print(f"\n✅ {len(generators)} mélodies générées avec succès !")
    print(f"   → {os.path.abspath(OUTPUT_DIR)}")


if __name__ == "__main__":
    main()
