#!/usr/bin/env python3
"""
Script de test pour vérifier la base de données - VERSION OPTIMISÉE
"""
import os
import sys
from pathlib import Path

# Ajouter le dossier rasa_bot/actions au path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'rasa_bot' / 'actions'))

from db_utils import (
    get_patient_by_name, 
    get_patient_medicines, 
    get_medicine_next_time,
    get_patient_discharge_date
)

def test_identification():
    print("=== TEST IDENTIFICATION (Prénom + Nom) ===")
    
    # Test Jean Dupont
    result = get_patient_by_name("Jean", "Dupont")
    if result:
        patient_id, first_name, last_name, discharge_date = result
        print(f"✓ Patient trouvé: {first_name} {last_name} (ID: {patient_id}) - Sortie: {discharge_date}")
    else:
        print("✗ Patient Jean Dupont non trouvé")
    
    # Test Marie Martin
    result = get_patient_by_name("Marie", "Martin")
    if result:
        patient_id, first_name, last_name, discharge_date = result
        print(f"✓ Patient trouvé: {first_name} {last_name} (ID: {patient_id}) - Sortie: {discharge_date}")
    else:
        print("✗ Patient Marie Martin non trouvé")
    
    print()

def test_medications():
    print("=== TEST MÉDICAMENTS ===")
    
    # Médicaments de PAT001 (Dupont)
    medicines = get_patient_medicines("PAT001")
    print(f"Médicaments de Jean Dupont (PAT001):")
    for med_name, next_time in medicines:
        print(f"  • {med_name} à {next_time}")
    
    print()
    
    # Médicaments de PAT002 (Martin)
    medicines = get_patient_medicines("PAT002")
    print(f"Médicaments de Marie Martin (PAT002):")
    for med_name, next_time in medicines:
        print(f"  • {med_name} à {next_time}")
    
    print()

def test_specific_medicine():
    print("=== TEST MÉDICAMENT SPÉCIFIQUE ===")
    
    # Test doliprane pour PAT001
    next_time = get_medicine_next_time("PAT001", "doliprane")
    if next_time:
        print(f"✓ Doliprane pour Jean Dupont: {next_time}")
    else:
        print("✗ Doliprane non trouvé")
    
    # Test insuline pour PAT001
    next_time = get_medicine_next_time("PAT001", "insuline")
    if next_time:
        print(f"✓ Insuline pour Jean Dupont: {next_time}")
    else:
        print("✗ Insuline non trouvée")
    
    print()

def test_discharge():
    print("=== TEST DATE DE SORTIE ===")
    
    # Date de sortie PAT001
    discharge = get_patient_discharge_date("PAT001")
    if discharge:
        print(f"✓ Date de sortie Jean Dupont: {discharge}")
    else:
        print("✗ Pas de date de sortie pour PAT001")
    
    # Date de sortie PAT002
    discharge = get_patient_discharge_date("PAT002")
    if discharge:
        print(f"✓ Date de sortie Marie Martin: {discharge}")
    else:
        print("✗ Pas de date de sortie pour PAT002")
    
    print()

if __name__ == "__main__":
    print("=" * 60)
    print("TEST BASE DE DONNÉES MEDIBOT - VERSION OPTIMISÉE")
    print("=" * 60)
    print()
    
    test_identification()
    test_medications()
    test_specific_medicine()
    test_discharge()
    
    print("=" * 60)
    print("TESTS TERMINÉS")
    print("=" * 60)
