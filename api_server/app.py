

from flask import Flask, jsonify
from flask_cors import CORS
import os
import sys

# Charger les variables d'environnement (.env) — même fichier que Rasa/voice_bridge
try:
    from dotenv import load_dotenv
    from pathlib import Path
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass

# Import route blueprints
from alert_routes import alerts_bp
from patient_routes import patients_bp
from extensions import socketio


def create_app():
    """
    Flask application factory.
    
    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Enable CORS for React frontend (development mode)
    CORS(app, resources={
        r"/*": {
            "origins": ["http://localhost:3000", "http://localhost:5173"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Initialize SocketIO with the app (CORS origins for WebSocket)
    socketio.init_app(app, cors_allowed_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ])
    
    # Configuration
    app.config['JSON_AS_ASCII'] = False  # Support French characters

    # Base de données : même logique que rasa_bot/actions/db_utils.py
    # pour éviter que Flask et Rasa lisent/écrivent dans des DB différentes.
    _base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _db_env = os.getenv("DB_PATH")
    if _db_env:
        if os.path.isabs(_db_env):
            app.config['DATABASE_PATH'] = _db_env
        else:
            app.config['DATABASE_PATH'] = os.path.join(_base_dir, _db_env)
    else:
        app.config['DATABASE_PATH'] = os.path.join(_base_dir, 'database', 'medibot.db')
    
    # Register blueprints
    app.register_blueprint(alerts_bp, url_prefix='/api/alerts')
    app.register_blueprint(patients_bp, url_prefix='/api/patients')
    
    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """API health check endpoint."""
        return jsonify({
            "status": "ok",
            "message": "MediBot API is running",
            "version": "1.0.0"
        })
    
    # Root endpoint
    @app.route('/')
    def index():
        """Root endpoint with API information."""
        return jsonify({
            "name": "MediBot API Server",
            "description": "REST API for nurse dashboard",
            "endpoints": {
                "health": "/api/health",
                "alerts": "/api/alerts",
                "patients": "/api/patients"
            }
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return jsonify({
            "error": "Not Found",
            "message": "The requested resource does not exist"
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }), 500
    
    return app


if __name__ == '__main__':
    # Create and run the application
    app = create_app()
    
    # Check if database exists
    db_path = app.config['DATABASE_PATH']
    if not os.path.exists(db_path):
        print(f"⚠️  Warning: Database not found at {db_path}")
        print("Make sure the RASA bot has created the database.")
    else:
        print(f"✓ Database found at {db_path}")
    
    print("\n" + "="*60)
    print("🏥 MediBot API Server Starting...")
    print("="*60)
    print(f"📍 API available at: http://localhost:5000")
    print(f"📊 Dashboard frontend should run on: http://localhost:3000")
    print("="*60 + "\n")
    
    # Run Flask + SocketIO server
    # debug=False : évite le rechargeur Werkzeug qui cause de faux "processus terminé"
    # quand lancé via subprocess (run.py).
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        allow_unsafe_werkzeug=True
    )
