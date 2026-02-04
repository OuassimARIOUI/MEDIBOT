# MediBot API Server

Backend Flask REST API + Frontend React Dashboard pour le système MediBot.

## 📁 Structure du projet

```
api_server/
├── app.py                          # Point d'entrée Flask
├── alert_routes.py                 # Routes API pour les alertes
├── patient_routes.py               # Routes API pour les patients
├── utils/
│   └── mail_service.py            # Service de notifications
└── frontend/                       # Dashboard React
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js                  # Client API
        ├── pages/
        │   └── Dashboard.jsx
        ├── components/
        │   ├── AlertCard.jsx
        │   └── PatientCard.jsx
        └── styles/
            └── dashboard.css
```

## 🚀 Installation et démarrage

### Backend (Flask)

1. **Installer les dépendances Python** :
   ```bash
   pip install -r requirements.txt
   ```

2. **S'assurer que la base de données existe** :
   La base de données doit être dans `database/medibot.db` (créée par RASA).

3. **Démarrer le serveur Flask** :
   ```bash
   cd api_server
   python app.py
   ```

   Le serveur Flask démarre sur `http://localhost:5000`

### Frontend (React)

1. **Installer les dépendances npm** :
   ```bash
   cd api_server/frontend
   npm install
   ```

2. **Démarrer le serveur de développement Vite** :
   ```bash
   npm run dev
   ```

   Le dashboard React démarre sur `http://localhost:3000`

## 📡 API Endpoints

### Alertes

- `GET /api/health` - Health check de l'API
- `GET /api/alerts` - Liste toutes les alertes
- `GET /api/alerts/unhandled` - Liste les alertes non traitées
- `GET /api/alerts/<id>` - Détails d'une alerte
- `POST /api/alerts/<id>/acknowledge` - Marquer une alerte comme traitée
- `GET /api/alerts/stats` - Statistiques des alertes

### Patients

- `GET /api/patients` - Liste tous les patients
- `GET /api/patients/<id>` - Détails d'un patient avec médicaments
- `GET /api/patients/<id>/medications` - Médicaments d'un patient
- `GET /api/patients/<id>/alerts` - Alertes d'un patient
- `GET /api/patients/stats` - Statistiques des patients

## 💊 Fonctionnalités du Dashboard

### Interface infirmière

✅ **Visualisation des alertes** :
- Liste des alertes actives en temps réel
- Tri par sévérité (critique, moyenne, basse)
- Informations patient (nom, chambre, âge, condition)
- Bouton de prise en charge

✅ **Gestion des patients** :
- Liste de tous les patients
- Indicateur d'alertes actives
- Médicaments prescrits
- Historique des alertes récentes

✅ **Statistiques en temps réel** :
- Nombre d'alertes actives
- Nombre d'alertes traitées
- Nombre de patients
- Patients avec alertes actives

✅ **Actualisation automatique** :
- Polling toutes les 30 secondes
- Bouton d'actualisation manuelle
- Horodatage de la dernière mise à jour

## 🎨 Interface utilisateur

L'interface est conçue pour être :
- **Claire et lisible** : Cartes avec codes couleur selon la sévérité
- **Moderne** : Design épuré avec ombres et animations subtiles
- **Responsive** : Compatible mobile, tablette et desktop
- **Accessible** : Couleurs contrastées, icônes explicites

## 🔐 Sécurité (Sprint 02)

⚠️ **Note importante** : Ce système est un projet académique (Sprint 02).

**Non implémenté dans cette version** :
- Authentification des utilisateurs
- Autorisation par rôle
- Chiffrement des données sensibles
- Rate limiting
- HTTPS

Pour un déploiement en production, ces fonctionnalités doivent être ajoutées.

## 🔧 Configuration

### Variables d'environnement

Créer un fichier `.env` dans `api_server/` :

```env
FLASK_ENV=development
DATABASE_PATH=../medibot.db
API_PORT=5000
FRONTEND_URL=http://localhost:3000
```

Créer un fichier `.env` dans `api_server/frontend/` :

```env
VITE_API_URL=http://localhost:5000/api
```

## 🧪 Tests

### Tester l'API avec curl

```bash
# Health check
curl http://localhost:5000/api/health

# Liste des alertes non traitées
curl http://localhost:5000/api/alerts/unhandled

# Prendre en charge une alerte
curl -X POST http://localhost:5000/api/alerts/1/acknowledge \
  -H "Content-Type: application/json" \
  -d '{"handled_by": "Infirmière Marie"}'

# Liste des patients
curl http://localhost:5000/api/patients
```

## 📊 Base de données

Le système se connecte à la base SQLite `medibot.db` créée par le bot RASA.

**Tables utilisées** :
- `alerts` - Alertes générées par MediBot
- `patients` - Informations sur les patients
- `medications` - Médicaments disponibles
- `patient_medications` - Relation patients-médicaments

## 🛠️ Technologies utilisées

### Backend
- **Flask** - Framework web Python
- **Flask-CORS** - Gestion CORS pour API
- **SQLite3** - Base de données

### Frontend
- **React 18** - Framework UI
- **Vite** - Build tool moderne
- **Axios** - Client HTTP
- **CSS3** - Styling moderne

## 📝 Notes de développement

### Architecture

Le système suit une architecture REST classique :
1. **Séparation claire** : Backend et Frontend indépendants
2. **Blueprints Flask** : Routes organisées par domaine
3. **Composants React** : Modulaires et réutilisables
4. **API client centralisé** : Tous les appels API passent par `api.js`

### Améliorations futures

- [ ] WebSocket pour mises à jour en temps réel
- [ ] Authentification avec JWT
- [ ] Filtres avancés (date, sévérité, chambre)
- [ ] Export des rapports en PDF
- [ ] Notifications push
- [ ] Historique complet des alertes
- [ ] Graphiques et analytics
- [ ] Mode sombre

## 👥 Équipe

Projet académique M1 S2 - MediBot
