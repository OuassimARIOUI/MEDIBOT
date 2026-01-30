#!/usr/bin/env python3
"""
Test du chemin DB depuis le répertoire rasa_bot (comme le serveur d'actions)
"""
import sys
import os
from pathlib import Path

# Simuler l'exécution depuis rasa_bot/
os.chdir(Path(__file__).parent.parent / "rasa_bot")
print(f"📂 Répertoire courant: {os.getcwd()}")

# Importer db_utils
sys.path.insert(0, "actions")
from db_utils import DB_PATH, get_patient_by_name

print(f"🗄️  Chemin DB: {DB_PATH}")
print(f"✓ Fichier existe: {Path(DB_PATH).exists()}")
print()

# Test d'identification
print("🧪 Test identification Jean Dupont...")
result = get_patient_by_name("Jean", "Dupont")
if result:
    print(f"✅ SUCCESS: {result}")
else:
    print("❌ FAILED: Patient non trouvé")
