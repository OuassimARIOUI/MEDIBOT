# 🔧 Dépannage : Actions Rasa Non Trouvées

## ❌ Erreur Rencontrée

```
ERROR rasa_sdk.endpoint - No registered action found for name 'action_identify_patient'
ERROR rasa_sdk.endpoint - No registered action found for name 'action_trigger_alert'
ERROR rasa_sdk.endpoint - No registered action found for name 'action_propose_activity'
```

---

## ✅ Solution Appliquée

Le problème était dans le fichier [__init__.py](d:\M1_S2\AmsProjet\MEDIBOT\rasa_bot\actions\__init__.py) qui n'exportait pas les classes d'actions.

**Correction :** Toutes les 13 classes d'actions sont maintenant exportées correctement.

---

## 🚀 Redémarrage Obligatoire

**IMPORTANT :** Vous **DEVEZ redémarrer** le serveur Rasa Actions pour que les changements prennent effet !

### Méthode 1 : Arrêt/Relance Manuel

**Étape 1 :** Arrêter les serveurs existants

Dans chaque terminal où Rasa tourne, faites **CTRL+C** puis :

```bash
# Terminal 1 - Actions
cd d:\M1_S2\AmsProjet\MEDIBOT\rasa_bot
rasa run actions
```

**Attendez ce message :**
```
✅ Registered actions:
   - action_get_time
   - action_get_date
   - action_identify_patient    ← Doit apparaître maintenant !
   - action_trigger_alert        ← Doit apparaître maintenant !
   - action_propose_activity     ← Doit apparaître maintenant !
   - ... (10 autres actions)
Action endpoint is up and running on http://localhost:5055
```

```bash
# Terminal 2 - Server
cd d:\M1_S2\AmsProjet\MEDIBOT\rasa_bot
rasa run --enable-api --cors "*"
```

**Attendez :**
```
Rasa server is up and running on http://localhost:5005
```

---

### Méthode 2 : Script Automatique (WSL/Linux)

```bash
cd d:\M1_S2\AmsProjet\MEDIBOT\rasa_bot
chmod +x restart_rasa.sh
./restart_rasa.sh
```

---

## 🧪 Vérification

### Test 1 : Vérifier les Actions Enregistrées

```bash
curl http://localhost:5055/health
```

**Réponse attendue :** `{"status": "ok"}`

### Test 2 : Lister les Actions

Regardez les logs du terminal où `rasa run actions` tourne. Vous devriez voir :

```
Registered actions:
  - action_get_time
  - action_get_date
  - action_identify_patient    ✅
  - action_get_discharge
  - action_session_start
  - action_propose_activity    ✅
  - action_ask_help
  - action_handle_affirm
  - action_handle_deny         ✅
  - action_play_song
  - action_tell_joke
  - action_get_medicine
  - action_trigger_alert       ✅
```

### Test 3 : Conversation Complète

```bash
cd ../stt_whisper
python3 voice_bridge.py
```

**Testez :**
1. "Je suis Wassim" → Doit vous identifier ✅
2. "SOS urgence" → Doit déclencher l'alerte ✅
3. Le bot devrait demander : "Voulez-vous que je vous propose une activité ?" ✅

---

## 🐛 Si Ça Ne Marche Toujours Pas

### Vérifier les Imports Python

```bash
cd rasa_bot/actions
python3 -c "from actions import ActionTriggerAlert; print('✅ Import OK')"
```

**Si erreur :** Vérifiez que [actions.py](d:\M1_S2\AmsProjet\MEDIBOT\rasa_bot\actions\actions.py) n'a pas d'erreurs de syntaxe.

### Vérifier la DB

```bash
cd ../..
python3 tests/test_db.py
```

### Logs Détaillés

Relancez avec mode debug :

```bash
# Terminal Actions
rasa run actions --debug

# Terminal Server  
rasa run --enable-api --cors "*" --debug
```

---

## 📋 Checklist de Dépannage

- [ ] **Serveurs redémarrés** après modification du `__init__.py`
- [ ] **13 actions affichées** dans les logs `rasa run actions`
- [ ] **Aucune erreur d'import** au démarrage
- [ ] **Base de données** contient les patients (test_db.py)
- [ ] **Modèle Rasa entraîné** récemment (`rasa train`)
- [ ] **Ports libres** : 5055 (actions) et 5005 (server)

---

## ⚠️ Note : Problème Audio WSL

Je remarque que vous utilisez encore **WSL** (erreur `sh: 1: aplay: not found`).

**Rappel :** Pour que le microphone fonctionne correctement, utilisez **PowerShell Windows** au lieu de WSL bash.

Voir [README_WINDOWS.md](d:\M1_S2\AmsProjet\MEDIBOT\stt_whisper\README_WINDOWS.md) pour les instructions.

---

## 🎯 Résumé

| Problème | Solution | Statut |
|----------|----------|--------|
| Actions non trouvées | ✅ Corrigé dans `__init__.py` | ✅ Résolu |
| Serveurs pas redémarrés | ⚠️ **REDÉMARRER** maintenant | ⏳ À faire |
| Audio WSL | ⚠️ Utiliser PowerShell Windows | ℹ️ Recommandé |

**Prochaine étape :** Redémarrez les serveurs Rasa !
