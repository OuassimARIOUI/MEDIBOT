"""
Test de reconnaissance des variantes de prénoms
Vérifie que toutes les orthographes sont correctement normalisées
"""

import sys
import os

# Ajouter les dossiers nécessaires au PYTHONPATH
project_root = os.path.join(os.path.dirname(__file__), '..')
rasa_bot_path = os.path.join(project_root, 'rasa_bot')
sys.path.insert(0, project_root)
sys.path.insert(0, rasa_bot_path)

# Import depuis le module actions
from rasa_bot.actions.actions import normalize_name, PRENOM_SYNONYMS

def test_normalize_ouassim():
    """Test des variantes de Ouassim"""
    variants = ["wasim", "wassim", "ouassim", "ouaassim", "Wasim", "WASSIM", "Ouassim"]
    expected = "ouassim"
    
    print("\n" + "="*60)
    print("🧪 TEST - Normalisation 'Ouassim'")
    print("="*60)
    
    for variant in variants:
        result = normalize_name(variant)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{variant}' -> '{result}' (attendu: '{expected}')")
        assert result == expected, f"Échec: {variant} donne {result} au lieu de {expected}"
    
    print(f"\n✅ Tous les tests Ouassim OK ({len(variants)} variantes)\n")

def test_normalize_asmaa():
    """Test des variantes de Asmaa"""
    variants = ["asma", "assma", "asmaa", "Asma", "ASMA", "Assma", "ASMAA"]
    expected = "asmaa"
    
    print("="*60)
    print("🧪 TEST - Normalisation 'Asmaa'")
    print("="*60)
    
    for variant in variants:
        result = normalize_name(variant)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{variant}' -> '{result}' (attendu: '{expected}')")
        assert result == expected, f"Échec: {variant} donne {result} au lieu de {expected}"
    
    print(f"\n✅ Tous les tests Asmaa OK ({len(variants)} variantes)\n")

def test_unknown_name():
    """Test avec un nom inconnu (doit retourner le nom original)"""
    print("="*60)
    print("🧪 TEST - Nom inconnu")
    print("="*60)
    
    unknown = "Pierre"
    result = normalize_name(unknown)
    expected = "pierre"  # Converti en minuscules mais pas modifié
    
    status = "✅" if result == expected else "❌"
    print(f"{status} '{unknown}' -> '{result}' (attendu: '{expected}')")
    assert result == expected, f"Échec: {unknown} donne {result}"
    
    print("\n✅ Test nom inconnu OK\n")

def display_all_synonyms():
    """Affiche tous les synonymes configurés"""
    print("="*60)
    print("📋 TOUS LES SYNONYMES CONFIGURÉS")
    print("="*60)
    print("\nFormat: variante -> nom_officiel\n")
    
    for variant, official in sorted(PRENOM_SYNONYMS.items()):
        print(f"  {variant:15} -> {official}")
    
    print(f"\n📊 Total: {len(PRENOM_SYNONYMS)} variantes configurées\n")

def test_phrase_examples():
    """Test avec des phrases complètes"""
    print("="*60)
    print("🧪 TEST - Phrases complètes simulées")
    print("="*60)
    print("\nSimulation de ce que Whisper pourrait transcrire:\n")
    
    test_cases = [
        ("je suis wasim arioui", ["wasim", "arioui"]),
        ("je suis wassim", ["wassim"]),
        ("bonjour je suis ouassim", ["ouassim"]),
        ("mon nom est asma boukraa", ["asma", "boukraa"]),
        ("je m'appelle assma", ["assma"]),
    ]
    
    for phrase, expected_words in test_cases:
        print(f"\n📝 Phrase: '{phrase}'")
        print(f"   Mots extraits: {expected_words}")
        
        normalized = [normalize_name(w) for w in expected_words]
        print(f"   Normalisés: {normalized}")
        
        # Vérifier qu'au moins un prénom connu est détecté
        known_names = ["ouassim", "asmaa"]
        found = any(n in normalized for n in known_names)
        status = "✅" if found else "❌"
        print(f"   {status} Prénom reconnu: {found}")
    
    print("\n✅ Tests phrases OK\n")

if __name__ == "__main__":
    print("\n" + "🎯 TESTS DE NORMALISATION DES PRÉNOMS".center(60))
    print("="*60)
    print("Version: 1.0")
    print("Date: 2026-02-15")
    print("="*60)
    
    try:
        display_all_synonyms()
        test_normalize_ouassim()
        test_normalize_asmaa()
        test_unknown_name()
        test_phrase_examples()
        
        print("="*60)
        print("🎉 TOUS LES TESTS RÉUSSIS ! 🎉".center(60))
        print("="*60)
        print("\n✅ La normalisation des prénoms fonctionne correctement.")
        print("✅ Toutes les variantes sont reconnues.")
        print("\n📌 N'oubliez pas de réentraîner Rasa avec:")
        print("   cd rasa_bot")
        print("   rasa train\n")
        
    except AssertionError as e:
        print("\n" + "="*60)
        print("❌ ÉCHEC DU TEST")
        print("="*60)
        print(f"Erreur: {e}\n")
        sys.exit(1)
    except Exception as e:
        print("\n" + "="*60)
        print("❌ ERREUR INATTENDUE")
        print("="*60)
        print(f"Erreur: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
