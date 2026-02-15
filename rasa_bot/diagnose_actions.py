#!/usr/bin/env python3
"""
Script de diagnostic des actions Rasa
Teste si Rasa SDK peut trouver et charger les actions
"""

import sys
import os

# Ajouter le dossier actions au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'actions'))

print("="*60)
print("🔍 DIAGNOSTIC DES ACTIONS RASA")
print("="*60)

print("\n1️⃣ Vérification du chemin Python...")
print(f"   Dossier courant: {os.getcwd()}")
actions_path = os.path.join(os.getcwd(), 'actions')
print(f"   Dossier actions: {actions_path}")
print(f"   Existe: {os.path.exists(actions_path)}")

print("\n2️⃣ Test d'import du module actions...")
try:
    import actions
    print(f"   ✅ Module 'actions' importé")
    print(f"   Chemin: {actions.__file__}")
except Exception as e:
    print(f"   ❌ Erreur d'import: {e}")
    sys.exit(1)

print("\n3️⃣ Recherche des classes Action...")
from rasa_sdk import Action

action_classes = []
for name in dir(actions):
    obj = getattr(actions, name)
    try:
        if isinstance(obj, type) and issubclass(obj, Action) and obj is not Action:
            action_classes.append(obj)
    except:
        pass

print(f"   Trouvées: {len(action_classes)} classes Action")

print("\n4️⃣ Liste des actions enregistrables:")
for cls in action_classes:
    try:
        instance = cls()
        action_name = instance.name()
        print(f"   ✅ {action_name:<30} ({cls.__name__})")
    except Exception as e:
        print(f"   ❌ {cls.__name__:<30} Erreur: {e}")

print("\n5️⃣ Test spécifique ActionTriggerAlert...")
try:
    from actions import ActionTriggerAlert
    alert_action = ActionTriggerAlert()
    print(f"   ✅ ActionTriggerAlert importée")
    print(f"   Nom: {alert_action.name()}")
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    import traceback
    traceback.print_exc()

print("\n6️⃣ Test des dépendances (db_utils, alert_service)...")
try:
    from actions import db_utils
    print(f"   ✅ db_utils importé")
except Exception as e:
    print(f"   ⚠️  db_utils: {e}")

try:
    from actions import alert_service
    print(f"   ✅ alert_service importé")
except Exception as e:
    print(f"   ⚠️  alert_service: {e}")

print("\n" + "="*60)
print("📋 RÉSUMÉ")
print("="*60)

if len(action_classes) >= 10:
    print(f"✅ {len(action_classes)} actions détectées - Le système devrait fonctionner")
    print("\n🚀 INSTRUCTIONS:")
    print("   1. Arrêtez rasa run actions (CTRL+C)")
    print("   2. Relancez: rasa run actions")
    print("   3. Vérifiez que les actions apparaissent dans les logs")
else:
    print(f"❌ Seulement {len(action_classes)} actions détectées - Problème d'import")
    print("\n🔧 SOLUTIONS:")
    print("   1. Vérifiez les erreurs ci-dessus")
    print("   2. Corrigez les imports dans actions.py")
    print("   3. Relancez ce script")

print("="*60)
