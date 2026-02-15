"""
Module d'actions personnalisées pour Rasa
Compatible avec Rasa SDK qui charge automatiquement actions.py
"""

# Ce fichier permet d'utiliser le dossier actions comme un package Python
# Rasa SDK charge automatiquement les actions depuis actions.py

# Imports optionnels pour tests et compatibilité
try:
    from actions import (
        normalize_name,
        PRENOM_SYNONYMS,
        ActionGetTime,
        ActionGetDate,
        ActionIdentifyPatient,
        ActionGetDischarge,
        ActionSessionStart,
        ActionProposeActivity,
        ActionAskHelp,
        ActionHandleAffirm,
        ActionHandleDeny,
        ActionPlaySong,
        ActionTellJoke,
        ActionGetMedicine,
        ActionTriggerAlert,
    )
    
    __all__ = [
        "normalize_name",
        "PRENOM_SYNONYMS",
        "ActionGetTime",
        "ActionGetDate",
        "ActionIdentifyPatient",
        "ActionGetDischarge",
        "ActionSessionStart",
        "ActionProposeActivity",
        "ActionAskHelp",
        "ActionHandleAffirm",
        "ActionHandleDeny",
        "ActionPlaySong",
        "ActionTellJoke",
        "ActionGetMedicine",
        "ActionTriggerAlert",
    ]
except ImportError as e:
    # Ne pas bloquer si import échoue (Rasa SDK charge directement actions.py)
    pass
