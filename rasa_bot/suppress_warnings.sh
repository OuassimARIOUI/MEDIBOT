# Variables d'environnement pour réduire les warnings
# Usage: source suppress_warnings.sh (Linux/WSL) ou . .\suppress_warnings.ps1 (PowerShell)

# Supprimer le warning SQLAlchemy
export SQLALCHEMY_SILENCE_UBER_WARNING=1

# Réduire les warnings de compatibilité
export PYTHONWARNINGS="ignore::DeprecationWarning,ignore::MovedIn20Warning"

echo "✅ Warnings supprimés pour cette session"
