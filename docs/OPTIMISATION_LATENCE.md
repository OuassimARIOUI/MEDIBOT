# Optimisation Latence MediBot - Guide Technique

## Problème Initial

Depuis l'intégration du module de vision (OpenCV + DeepFace), le robot Pepper était extrêmement lent. La cause : **traitement 100% synchrone** sur le CPU limité de Pepper (Intel Atom).

### Diagnostic des Goulots d'Étranglement

| Module | Temps/frame | Impact |
|--------|-------------|--------|
| DeepFace (emotion) | 500ms - 2s | **CRITIQUE** - Bloque tout le pipeline |
| MediaPipe (urgences) | 50-100ms | Modéré |
| Whisper STT | 500ms - 1s | Élevé (partage CPU avec DeepFace) |
| Caméra Pepper (réseau) | 20-50ms | Faible |

## Solution Implémentée

### 1. Architecture Asynchrone (`async_vision_pipeline.py`)

```
┌─────────────────────────────────────────────────────────────┐
│                      PEPPER CAMERA                          │
└─────────────────────────┬───────────────────────────────────┘
                          │ frames (10 FPS)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 FRAME BUFFER (Thread-safe)                  │
│                    (3 frames max, drop oldest)              │
└───────┬─────────────────────────────────────┬───────────────┘
        │                                     │
        ▼                                     ▼
┌───────────────────┐               ┌───────────────────────┐
│  EMOTION WORKER   │               │   EMERGENCY WORKER    │
│  (DeepFace)       │               │   (MediaPipe)         │
│  ~1 frame / 2.5s  │               │   ~2-3 frames / sec   │
└─────────┬─────────┘               └───────────┬───────────┘
          │                                     │
          ▼                                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     RESULT QUEUE                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│    ALERT DISPATCHER (LEDs + TTS + Dashboard HTTP)          │
└─────────────────────────────────────────────────────────────┘
```

**Avantages :**
- Capture vidéo indépendante de l'analyse
- DeepFace ne bloque plus Whisper/Rasa
- Buffer circulaire évite l'accumulation de frames
- Urgences traitées 5x plus vite que les émotions

### 2. Déportation sur Serveur (`vision_routes.py`)

Le serveur Flask peut maintenant analyser les frames à la place de Pepper :

```bash
# Sur Pepper (allégé)
python run_emotion_optimized.py --server

# Le serveur Flask reçoit les frames et retourne les résultats
POST /api/vision/emotion    → {"emotion": "happy", "confidence": 0.87}
POST /api/vision/emergency  → {"is_emergency": false}
POST /api/vision/analyze    → Analyse complète en une requête
```

**Avantages :**
- Libère le CPU de Pepper pour Whisper/Rasa
- Peut utiliser un GPU sur le serveur
- Latence réseau (~50ms) < latence DeepFace sur Pepper (~2s)

### 3. Mode Dégradé Automatique (`failover_manager.py`)

Surveillance des ressources et adaptation automatique :

| Niveau | Condition | Actions |
|--------|-----------|---------|
| NORMAL | CPU < 70% | Tout actif |
| MODERATE | CPU 70-85% | DeepFace désactivé |
| CRITICAL | CPU 85-95% | Urgences uniquement |
| MINIMAL | CPU > 95% | Vision arrêtée, audio seul |

```python
from failover_manager import get_failover_manager, is_emotion_enabled

manager = get_failover_manager()
manager.start()

# Dans votre code :
if is_emotion_enabled():
    analyze_emotion(frame)
```

## Utilisation

### Mode Recommandé (Production Pepper)

```bash
# Lancer tout avec vision déportée sur serveur
python run.py
```

Le launcher `run.py` démarre automatiquement :
- Rasa Actions (port 5055)
- Rasa Server (port 5005)
- Flask API avec vision routes (port 5000)
- Voice Bridge (Whisper → Rasa → TTS)
- **Emotion Detection OPTIMISÉE** avec `--server`

### Mode Développement (PC avec GPU)

```bash
# Vision locale avec GPU CUDA
cd emotion_detection
python run_emotion_optimized.py --local --debug
```

### Mode Legacy (Déconseillé)

```bash
# Ancien code synchrone (pour debug uniquement)
python run_emotion_optimized.py --legacy
```

## Configuration `.env`

```env
# Pepper
PEPPER_IP=192.168.1.100
PEPPER_PORT=9559

# Patient
PATIENT_ID=PAT001

# URLs
DASHBOARD_URL=http://localhost:5000/api/alerts
VISION_SERVER_URL=http://localhost:5000/api/vision/emotion

# Venv séparé pour DeepFace (optionnel)
EMOTION_VENV_PYTHON=/path/to/venv/bin/python
```

## Dépendances Supplémentaires

```bash
# Pour le serveur (si utilisation GPU)
pip install deepface tensorflow-gpu

# Pour le monitoring failover
pip install psutil

# Pour le transfert audio Pepper
pip install paramiko
```

## Performances Attendues

| Métrique | Avant | Après |
|----------|-------|-------|
| Latence réponse vocale | 3-5s | < 1s |
| Analyse émotion | Bloque 2s | Non-bloquant |
| Détection urgence | 500ms | < 200ms |
| Utilisation CPU Pepper | 100% | ~50-60% |

## Fichiers Créés

- `emotion_detection/async_vision_pipeline.py` - Pipeline asynchrone 3 threads
- `emotion_detection/failover_manager.py` - Gestion mode dégradé
- `emotion_detection/run_emotion_optimized.py` - Point d'entrée optimisé
- `api_server/vision_routes.py` - Endpoints Flask pour déportation

## Fichiers Modifiés

- `api_server/app.py` - Import routes vision
- `run.py` - Lancement version optimisée

## Auteur

MediBot Team - Optimisation Latence
