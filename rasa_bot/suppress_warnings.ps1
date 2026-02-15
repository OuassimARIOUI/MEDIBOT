# Variables d'environnement pour réduire les warnings (PowerShell)
# Usage: . .\suppress_warnings.ps1

$env:SQLALCHEMY_SILENCE_UBER_WARNING = "1"
$env:PYTHONWARNINGS = "ignore::DeprecationWarning,ignore::MovedIn20Warning"

Write-Host "✅ Warnings supprimés pour cette session PowerShell" -ForegroundColor Green
