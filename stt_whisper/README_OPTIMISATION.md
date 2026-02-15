# 🎤 Guide d'Optimisation de la Reconnaissance Vocale

## 📊 Problèmes Identifiés

Votre log montre une transcription très mauvaise :
```
段 endure
Arriver moinson bête Salut !
je suis à relie moi bah de
```

**Causes principales :**
1. ❌ Modèle Whisper `tiny` (39M paramètres) trop petit
2. ❌ Pas de détection d'activité vocale (VAD)
3. ❌ Bruit ambiant non filtré
4. ❌ Durée d'écoute trop courte (4s)

---

## ✅ Solutions Implémentées

### 1. **Modèle Whisper Amélioré**
```python
# AVANT : tiny (39M, rapide mais imprécis)
listener = MediBotListener()

# APRÈS : base (74M, meilleur compromis vitesse/précision)
listener = MediBotListener(model_size="base")
```

**Comparaison des modèles :**
| Modèle | Taille | WER* | Vitesse | Recommandation |
|--------|--------|------|---------|----------------|
| tiny   | 39M    | ~15% | Très rapide | ❌ Trop d'erreurs |
| base   | 74M    | ~8%  | Rapide | ✅ **OPTIMAL** |
| small  | 244M   | ~5%  | Moyen | ⚠️ Si PC puissant |
| medium | 769M   | ~4%  | Lent | ❌ Trop lourd |

*WER = Word Error Rate (pourcentage d'erreurs)

### 2. **Détection d'Activité Vocale (VAD)**
```python
def has_speech(audio_data, threshold=MIN_ENERGY_THRESHOLD):
    """Détecte si l'audio contient de la parole."""
    energy = np.sqrt(np.mean(audio_data**2))
    return energy > threshold
```
- Évite de transcrire le silence ou les bruits parasites
- Économise les ressources CPU/GPU

### 3. **Durée d'Écoute Augmentée**
```python
# AVANT : 4 secondes (trop court pour phrases complètes)
DURATION = 4

# APRÈS : 6 secondes (permet phrases complètes)
DURATION = 6
```

### 4. **Feedback Utilisateur Amélioré**
- 🎤 Icônes pour indiquer l'état (écoute, transcription)
- ✅ Confirmation du texte reconnu
- ❌ Messages d'erreur clairs

---

## 🚀 Utilisation

### Étape 1 : Calibration du Microphone
```bash
cd stt_whisper
python audio_calibration.py
```

**Suivez les instructions :**
1. Restez silencieux 3 secondes (mesure bruit ambiant)
2. Parlez 3 secondes : "Bonjour je suis [votre nom]"
3. Notez la valeur `MIN_ENERGY_THRESHOLD` affichée

**Exemple de sortie :**
```
✅ Énergie du bruit ambiant : 0.002351
✅ Énergie de votre voix : 0.015432
🎯 Seuil optimal : 0.006273
✅ Qualité : BONNE (conditions optimales)
```

### Étape 2 : Mise à Jour du Seuil
Modifiez [voice_bridge.py](voice_bridge.py) :
```python
MIN_ENERGY_THRESHOLD = 0.006273  # Remplacer par votre valeur calibrée
```

### Étape 3 : Test en Temps Réel
```bash
python audio_calibration.py --test
```
Parlez et vérifiez que les barres s'affichent correctement.

### Étape 4 : Lancement
```bash
# Terminal 1
cd ../rasa_bot
rasa run actions

# Terminal 2
cd ../rasa_bot
rasa run --enable-api --cors "*"

# Terminal 3
cd ../stt_whisper
python voice_bridge.py
```

---

## 💡 Conseils d'Utilisation

### ✅ BONNES PRATIQUES
- 🎙️ **Distance** : 15-30 cm du microphone
- 🔊 **Volume** : Parlez clairement et fort
- ⏸️ **Pause** : Attendez le symbole 🎤 avant de parler
- 🗣️ **Phrase complète** : "Bonjour je suis Ouassim Arioui" (pas de mots coupés)
- 🔇 **Silence** : Réduisez les bruits de fond (TV, ventilateur)

### ❌ À ÉVITER
- ❌ Parler trop vite
- ❌ Parler pendant la transcription (⏳)
- ❌ Mots techniques/rares (privilégiez vocabulaire courant)
- ❌ Microphone intégré trop loin (préférez casque/micro USB)

---

## 🧪 Test de Reconnaissance de Nom

### Phrases à Tester

**Identification simple :**
```
"Je suis Ouassim Arioui"
"Mon nom est Ouassim Arioui"
"Bonjour je suis Ouassim Arioui"
```

**Autres commandes :**
```
"SOS j'ai besoin d'aide"              → Urgence
"Je ne me sens pas bien"              → État
"Quelle heure est-il ?"               → Temps
"Est-ce que l'infirmière peut venir ?" → Assistance
```

---

## 🔧 Dépannage Avancé

### Problème : Transcription en Chinois/Russe
**Cause** : Whisper détecte mal la langue  
**Solution** : Vérifiez dans [whisper_listener.py](whisper_listener.py) :
```python
result = self.model.transcribe(audio_path, language="fr", fp16=False)
```

### Problème : Latence élevée (>5s)
**Causes** :
- CPU trop faible pour modèle `base`
- Pas de GPU détecté

**Solutions** :
```bash
# Vérifier si GPU utilisé
python -c "import torch; print(torch.cuda.is_available())"

# Si False, installer CUDA : https://pytorch.org/get-started/locally/
```

### Problème : "... Aucune voix détectée ..."
**Causes** :
- Microphone trop faible
- Seuil `MIN_ENERGY_THRESHOLD` trop élevé

**Solutions** :
1. Refaire la calibration
2. Réduire manuellement le seuil :
```python
MIN_ENERGY_THRESHOLD = 0.005  # Essayez 0.005, 0.008, 0.01
```

---

## 📈 Améliorations Futures Possibles

### Court terme (facile)
- [ ] Ajouter un bip sonore pour indiquer le début d'écoute
- [ ] Enregistrer les transcriptions dans un fichier de log
- [ ] Afficher un score de confiance Whisper

### Moyen terme (modéré)
- [ ] Utiliser `webrtcvad` pour VAD plus précis
- [ ] Ajouter réduction de bruit (scipy signal processing)
- [ ] Mode push-to-talk (appui touche pour parler)

### Long terme (complexe)
- [ ] Fine-tuning Whisper sur vocabulaire médical
- [ ] Intégration avec microphone directionnel Pepper
- [ ] Reconnaissance du locuteur (speaker diarization)

---

## 📞 Support

Si la reconnaissance reste mauvaise après ces optimisations :
1. ✅ Vérifiez votre configuration micro dans Windows (Paramètres > Son)
2. ✅ Testez avec un autre micro (casque USB recommandé)
3. ✅ Vérifiez les logs Rasa pour voir les intents détectés
4. ✅ Consultez les logs de transcription dans le terminal

---

**Auteur** : Configuration optimisée pour MEDIBOT  
**Date** : 2026-02-15  
**Modèle Whisper** : OpenAI Whisper (base)
