MediBot - Documentation Module emotion_detection
Ce module constitue le "système nerveux" visuel du Pepper. Il permet de transformer le flux vidéo de la caméra frontale en données exploitables : émotions du patient, détection d'étouffement et surveillance respiratoire.

1. Environnement & Dépendances Critiques
Nous avons dû stabiliser l'environnement car Rasa 3.6.20 impose des contraintes strictes sur les versions de librairies de calcul. Ne pas modifier ces versions.

Versions obligatoires
Python : 3.10.x

Numpy : 1.23.5 (Cible < 1.25.0)

Protobuf : 4.23.3 (Indispensable pour le moteur Rasa)

Joblib : 1.4.0 (Compromis pour MTCNN et Rasa)

MediPipe : 0.10.9

Installation propre
PowerShell
# 1. Activation de l'environnement
.\venv\Scripts\activate

# 2. Installation des moteurs IA
pip install opencv-python deepface mediapipe==0.10.9 pytest requests

# 3. Correction des conflits de versions (CRITIQUE)
pip install "protobuf>=4.23.3,<4.23.4" "joblib>=1.3.0,<1.4.2" "numpy<1.25.0"
🛠 2. Architecture Technique : Comment ça marche ?
A. Détection d'Émotions (emotion_detector.py)
Utilise la librairie DeepFace pour analyser le visage.

Procédé : Capture d'une frame -> Extraction du visage -> Analyse du vecteur d'émotion (dominant_emotion).

Réactions : Les résultats sont envoyés à emotion_rules.py qui définit si Pepper doit changer ses LEDs (Bleu pour la tristesse, Rouge pour la colère).

B. Détection d'Urgence (emergency_detector.py)
C'est le module de sécurité vitale du Pepper.

Étouffement : Utilise MediaPipe Pose pour localiser les poignets (points 15, 16) par rapport au cou (entre le nez et les épaules).

Respiration : Utilise le flux optique (Farneback) sur une zone d'intérêt (ROI) située au niveau du thorax. Si la moyenne du mouvement (magnitude) descend sous 0.03 pendant une durée prolongée, une alerte est levée.

C. Système d'Alerte (alert_system.py)
Centralise les défaillances.

Niveau 1 : État émotionnel instable à surveiller.

Niveau 2 : Urgence vitale (étouffement ou arrêt respiratoire).

Envoi : Les alertes sont envoyées via une requête POST JSON à http://localhost:5000/alerts.

3. Procédure de Test (Le "All Green")
Nous avons automatisé les tests pour garantir que la logique de décision fonctionne à 100%, même sans le robot Pepper physique.

Lancer le diagnostic de l'environnement
Vérifie que tous les modèles IA se chargent correctement :

PowerShell
python emotion_detection/check_env.py
Lancer les tests unitaires (Logique de Vision)
Valide que Pepper prend la bonne décision en cas d'étouffement ou d'immobilité :

PowerShell
python -m pytest tests/test_vision_logic.py -v
Lancer les tests de dialogue & émotions
Valide 32 scénarios de conversation (Anxiété, Joie, Panique) :

PowerShell
python -m pytest tests/test_emotion.py tests/test_emotion_policy.py -v
4. Lancement en conditions réelles (Démonstration)
Tester la détection d'étouffement (Webcam)
Lance ce script et mets tes mains au niveau de ton cou :

PowerShell
python -m emotion_detection.test_mediapipe
Lancer le système complet (Vision + Émotion)
PowerShell
python emotion_detection/live_test.py
'q' pour quitter.

Affiche l'émotion dominante et le statut d'urgence en temps réel sur l'image.