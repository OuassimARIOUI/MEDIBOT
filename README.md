# MEDIBOT

## Git Structure

```text
medibot/
│
├── README.md
├── requirements.txt
├── .env
│
├── rasa_bot/                     # Cerveau conversationnel RASA
│   ├── data/
│   │   ├── nlu.yml
│   │   ├── stories.yml
│   │   ├── rules.yml
│   │   └── lookup_tables.yml
│   ├── domain.yml
│   ├── config.yml
│   ├── endpoints.yml
│   ├── credentials.yml
│   ├── models/                   # Modèles entraînés
│   └── actions/
│       ├── actions.py            # Actions custom RASA
│       ├── db_utils.py           # Connexion BD
│       ├── alert_service.py      # Envoi alertes soignants
│       └── emotion_policy.py     # Réaction aux émotions
│
├── stt_whisper/                  # Module Speech-to-Text
│   ├── whisper_listener.py       # Convertit voix → texte
│   ├── audio_utils.py
│   └── stream_audio.py
│
├── robot_control/                # Contrôle Pepper (NAOqi)
│   ├── pepper_main.py            # Boucle principale du robot
│   ├── pepper_tts.py             # Text-to-speech NAOqi
│   ├── pepper_motion.py          # Gestuelle, hochement tête
│   ├── pepper_leds.py            # LEDs émotions
│   ├── pepper_behavior.py        # Lance animations Choregraphe
│   └── pepper_camera.py          # Accès caméra
│
├── emotion_detection/            # Module émotion caméra
│   ├── emotion_detector.py       # DeepFace / FER
│   ├── video_stream.py           # Récupération image Pepper
│   └── emotion_rules.py          # Décision selon émotion
│
├── api_server/                   # API d'alerte soignants
│   ├── app.py                    # Flask API REST
│   ├── alert_routes.py           # Routes /alert
│   ├── patient_routes.py         # Routes patient / médicaments
│   └── utils/
│       └── mail_service.py       # Module email / webhook
│
├── database/                     # Base de données factice
│   ├── medibot.db                # SQLite
│   └── schema.sql
│
├── reinforcement_learning/       # Optionnel
│   ├── rl_agent.py               # DQN / Actor-Critic
│   ├── rl_training.py
│   └── rasa_data_export.py
│
└── docs/                         # Documentation / cahier charges
    ├── Cahier_Des_Charges.pdf
    ├── Architecture_MediBot.pdf
    └── run.py
```