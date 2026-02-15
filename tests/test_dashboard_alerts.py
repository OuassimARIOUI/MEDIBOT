#!/usr/bin/env python3
"""
Script de test pour vérifier pourquoi les alertes ne s'affichent pas dans le dashboard
"""

import sqlite3
import requests
import sys
import os
from datetime import datetime

print("\n" + "="*70)
print("🔍 DIAGNOSTIC: Alertes Dashboard")
print("="*70)

# 1. Vérifier la base de données
print("\n1️⃣ Vérification Base de Données...")
print("-" * 70)

db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'medibot.db')
if not os.path.exists(db_path):
    print(f"❌ Base de données introuvable: {db_path}")
    sys.exit(1)

print(f"✅ DB trouvée: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Compter les alertes
    cursor.execute("SELECT COUNT(*) FROM alerts")
    total_alerts = cursor.fetchone()[0]
    print(f"📊 Total alertes dans la DB: {total_alerts}")
    
    # Afficher les 5 dernières alertes
    cursor.execute("""
        SELECT id, patient_id, message, created_at, acknowledged
        FROM alerts 
        ORDER BY id DESC 
        LIMIT 5
    """)
    recent_alerts = cursor.fetchall()
    
    if recent_alerts:
        print(f"\n📋 5 dernières alertes:")
        for alert in recent_alerts:
            alert_id, patient_id, message, created_at, ack = alert
            status = "✅ Traitée" if ack else "⏳ Non traitée"
            print(f"   [{alert_id}] {status} - Patient: {patient_id}")
            print(f"        Message: {message[:60]}...")
            print(f"        Date: {created_at}\n")
    else:
        print("⚠️  Aucune alerte dans la base de données!")
        print("   Problème: Les alertes ne sont pas enregistrées du tout.")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Erreur DB: {e}")
    import traceback
    traceback.print_exc()

# 2. Vérifier le backend Flask
print("\n2️⃣ Vérification Backend Flask (API)...")
print("-" * 70)

backend_url = "http://localhost:5000"

try:
    # Test health check
    response = requests.get(f"{backend_url}/api/health", timeout=3)
    if response.status_code == 200:
        print(f"✅ Backend Flask: EN LIGNE ({backend_url})")
        health_data = response.json()
        print(f"   Version: {health_data.get('version', 'unknown')}")
    else:
        print(f"⚠️  Backend Flask répond avec code {response.status_code}")
except requests.exceptions.ConnectionError:
    print(f"❌ Backend Flask: HORS LIGNE")
    print(f"\n💡 Solution: Lancez le backend Flask")
    print(f"   cd api_server")
    print(f"   python3 app.py")
    print(f"\n⚠️  Sans le backend, les alertes ne peuvent pas être récupérées par le frontend!")

except Exception as e:
    print(f"❌ Erreur: {e}")

# 3. Test de récupération des alertes via API
print("\n3️⃣ Test API /api/alerts...")
print("-" * 70)

try:
    response = requests.get(f"{backend_url}/api/alerts", timeout=3)
    if response.status_code == 200:
        alerts_api = response.json()
        print(f"✅ API accessible: {len(alerts_api)} alertes retournées")
        
        if len(alerts_api) > 0:
            print(f"\n📋 Première alerte via API:")
            first = alerts_api[0]
            print(f"   ID: {first.get('id')}")
            print(f"   Patient: {first.get('patient_name', 'N/A')}")
            print(f"   Chambre: {first.get('room_number', 'N/A')}")
            print(f"   Message: {first.get('message', '')[:60]}...")
            print(f"   Date: {first.get('created_at', 'N/A')}")
        else:
            print("⚠️  L'API retourne 0 alertes (alors que la DB en contient?)")
            print("   Vérifiez la logique de filtrage dans alert_routes.py")
    else:
        print(f"❌ API retourne code {response.status_code}")
        print(f"   Réponse: {response.text[:200]}")
except requests.exceptions.ConnectionError:
    print(f"❌ API non accessible (Backend Flask non lancé)")
except Exception as e:
    print(f"❌ Erreur: {e}")

# 4. Vérifier l'URL du dashboard dans alert_service.py
print("\n4️⃣ Vérification Configuration DASHBOARD_URL...")
print("-" * 70)

alert_service_path = os.path.join(
    os.path.dirname(__file__), '..', 'rasa_bot', 'actions', 'alert_service.py'
)

if os.path.exists(alert_service_path):
    with open(alert_service_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'DASHBOARD_URL' in content:
            for line in content.split('\n'):
                if 'DASHBOARD_URL' in line and not line.strip().startswith('#'):
                    print(f"📝 Configuré: {line.strip()}")
                    if 'localhost:5000' in line:
                        print("   ✅ URL correcte")
                    else:
                        print("   ⚠️  Vérifiez que l'URL correspond au backend")
        else:
            print("⚠️  DASHBOARD_URL non trouvé dans alert_service.py")
else:
    print("⚠️  alert_service.py non trouvé")

# 5. Résumé et diagnostic
print("\n" + "="*70)
print("📋 DIAGNOSTIC FINAL")
print("="*70)

print("\n🔍 Causes possibles si alertes ne s'affichent pas:")
print("\n1. ❌ Backend Flask non lancé")
print("   → Solution: cd api_server && python3 app.py")

print("\n2. ❌ Patient non identifié avant de dire SOS")
print("   → L'alerte basique est enregistrée dans la DB mais pas notifiée")
print("   → Solution: Dire 'Je suis [nom]' AVANT de dire 'SOS'")

print("\n3. ❌ Frontend ne rafraîchit pas automatiquement")
print("   → Rafraîchissez la page du dashboard (F5)")
print("   → Vérifiez la console du navigateur pour erreurs JS")

print("\n4. ❌ CORS bloque les requêtes")
print("   → Vérifiez la console du navigateur")
print("   → Le backend doit autoriser l'origine du frontend")

print("\n" + "="*70)
print("✅ PROCHAINES ÉTAPES:")
print("="*70)
print("\n1. Lancez le backend Flask:")
print("   cd api_server")
print("   python3 app.py")

print("\n2. Ouvrez le dashboard dans le navigateur:")
print("   http://localhost:5173")

print("\n3. Testez la conversation complète:")
print("   - Dire: 'Je suis Wassim' (identification)")
print("   - Dire: 'SOS urgence' (alerte)")
print("   - Vérifier le dashboard")

print("\n4. Si toujours pas visible, vérifiez:")
print("   - Console du navigateur (F12)")
print("   - Logs du backend Flask")
print("   - Relancez ce script pour voir si l'alerte est dans la DB")

print("\n" + "="*70 + "\n")
