#!/usr/bin/env python3
"""
Test du chemin DB depuis le répertoire rasa_bot (comme le serveur d'actions)
"""
import sys
import os
from pathlib import Path
import pytest

# Ajouter le chemin vers les actions
sys.path.insert(0, str(Path(__file__).parent.parent / "rasa_bot" / "actions"))

from db_utils import DB_PATH, get_patient_by_name


@pytest.fixture(autouse=True)
def setup_cwd():
    """Change le répertoire courant pour simuler l'exécution depuis rasa_bot/"""
    original_cwd = os.getcwd()
    os.chdir(Path(__file__).parent.parent / "rasa_bot")
    yield
    os.chdir(original_cwd)


def test_db_path_exists():
    """Vérifie que le fichier DB existe"""
    print(f"📂 Répertoire courant: {os.getcwd()}")
    print(f"🗄️  Chemin DB: {DB_PATH}")
    assert Path(DB_PATH).exists(), f"Database file not found: {DB_PATH}"


@pytest.mark.skipif(not Path(DB_PATH).exists(), reason="Database file not found")
def test_get_patient_by_name():
    """Test d'identification Jean Dupont"""
    print("🧪 Test identification Jean Dupont...")
    result = get_patient_by_name("Jean", "Dupont")
    # Le patient peut exister ou non selon les données de test
    print(f"Résultat: {result}")
