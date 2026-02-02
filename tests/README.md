# 🧪 Tests MediBot

Ce dossier contient les scripts de test pour le projet MediBot.

## Fichiers

### `test_db.py`
Test complet de la base de données :
-  Identification des patients (prénom + nom)
-  Récupération des médicaments
-  Recherche de médicaments spécifiques
-  Date de sortie

**Exécution** :
```bash
cd D:\M1_S2\AmsProjet\MEDIBOT
python test\test_db.py
```

### `test_db_path.py`
Test du chemin de la base de données depuis le contexte du serveur d'actions Rasa.
Vérifie que le chemin absolu fonctionne correctement.

**Exécution** :
```bash
cd D:\M1_S2\AmsProjet\MEDIBOT 
python test\test_db_path.py
```

---

## Utilisation

Les tests doivent être exécutés depuis la racine du projet (`MEDIBOT/`).

Tous les tests doivent afficher ✅ SUCCESS pour confirmer que la configuration est correcte.
