#!/bin/bash
# Script de redémarrage rapide des serveurs Rasa
# Usage: ./restart_rasa.sh

echo ""
echo "=========================================="
echo "  🔄 Redémarrage Serveurs Rasa"
echo "=========================================="
echo ""

# Trouver et tuer les processus Rasa existants
echo "🛑 Arrêt des serveurs Rasa existants..."

pkill -f "rasa run actions" 2>/dev/null
pkill -f "rasa run --enable-api" 2>/dev/null
pkill -f "rasa_sdk" 2>/dev/null

sleep 2

echo "✅ Serveurs arrêtés"
echo ""

# Demander si l'utilisateur veut relancer
echo "Voulez-vous relancer les serveurs ? (o/n)"
read -r response

if [ "$response" != "o" ]; then
    echo "👋 Arrêt du script"
    exit 0
fi

echo ""
echo "🚀 Lancement des serveurs..."
echo ""

# Aller dans le dossier rasa_bot
cd "$(dirname "$0")" || exit 1

# Vérifier que nous sommes dans le bon dossier
if [ ! -f "domain.yml" ]; then
    echo "❌ Erreur: domain.yml introuvable"
    echo "   Assurez-vous d'être dans le dossier rasa_bot/"
    exit 1
fi

# Lancer Rasa Actions en arrière-plan
echo "📦 Terminal 1: Lancement Rasa Actions (port 5055)..."
gnome-terminal --tab --title="Rasa Actions" -- bash -c "rasa run actions; exec bash" 2>/dev/null || \
xterm -e "rasa run actions" 2>/dev/null || \
konsole -e "rasa run actions" 2>/dev/null || \
echo "⚠️  Impossible d'ouvrir terminal automatiquement. Lancez manuellement:"
echo "   Terminal 1: rasa run actions"

sleep 3

# Lancer Rasa Server en arrière-plan
echo "📦 Terminal 2: Lancement Rasa Server (port 5005)..."
gnome-terminal --tab --title="Rasa Server" -- bash -c "rasa run --enable-api --cors '*'; exec bash" 2>/dev/null || \
xterm -e "rasa run --enable-api --cors '*'" 2>/dev/null || \
konsole -e "rasa run --enable-api --cors '*'" 2>/dev/null || \
echo "⚠️  Impossible d'ouvrir terminal automatiquement. Lancez manuellement:"
echo "   Terminal 2: rasa run --enable-api --cors '*'"

echo ""
echo "=========================================="
echo "✅ Serveurs lancés !"
echo "=========================================="
echo ""
echo "📊 Vérification des services :"
echo ""
echo "Attendez 10-15 secondes que les serveurs démarrent..."
echo "Puis testez avec:"
echo ""
echo "  curl http://localhost:5055/health"
echo "  curl http://localhost:5005"
echo ""
echo "🎤 Pour lancer voice_bridge:"
echo ""
echo "  cd ../stt_whisper"
echo "  python3 voice_bridge.py"
echo ""
